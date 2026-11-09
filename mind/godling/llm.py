"""DeepSeek chat client (OpenAI-compatible endpoint) with JSON replies and cost accounting."""
import http.client
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# USD per million tokens, off-peak: cache hit, cache miss, output (api-docs.deepseek.com, 2026-11).
PRICES = {"deepseek-flash": (0.003, 0.15, 0.60), "deepseek-v4-pro": (0.022, 0.66, 1.98)}

DECIDE_TOKENS = 32768  # a decision's cap on reasoning and answer together; --reasoning-budget's default (ADR-030)
# Past the cap, the answer is given from the end of the reasoning, by a reply that does not think again (ADR-030).
ANSWER_TOKENS = 4096  # a decision's answer took about 1,100 tokens, at most 2,300 (run live)
ANSWER_FROM = 12000  # characters: the end of what it thought, about 3,500 tokens
FORCED_ANSWER = """Your thinking ran out of room before you gave your answer. This is how it ended:
{thoughts}
{began}Answer now, from what you have thought: reply with the JSON object only."""


def peak_multiplier(now=None):
    """DeepSeek doubles prices 01-04 and 06-10 UTC on weekdays."""
    now = now or datetime.now(timezone.utc)
    return 2 if now.weekday() < 5 and (1 <= now.hour < 4 or 6 <= now.hour < 10) else 1


def load_api_key():
    """DEEPSEEK_API_KEY, else the key tools/setup_deepseek.sh stored for Claude Code."""
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ["DEEPSEEK_API_KEY"]
    settings = Path.home() / ".claude-deepseek" / "settings.json"
    if settings.exists():
        key = json.loads(settings.read_text()).get("env", {}).get("ANTHROPIC_AUTH_TOKEN")
        if key:
            return key
    raise RuntimeError("No DeepSeek key: set DEEPSEEK_API_KEY or run tools/setup_deepseek.sh")


class LLM:
    def __init__(self, model="deepseek-flash", api_key=None, base="https://api.deepseek.com", log=None):
        self.model = model
        self.key = api_key or load_api_key()
        self.base = base
        self.log = log or (lambda **kw: None)
        self.calls = 0
        self.cost = 0.0
        self.forced = 0  # answers given from the reasoning so far, after the cap or a broken stream (ADR-030)

    def complete_json(self, system, user, purpose="decide", max_tokens=DECIDE_TOKENS, retries=2, on_reasoning=None,
                      effort=None):
        """One JSON reply, with reasoning on unless `effort` is "none".

        `effort` is DeepSeek's reasoning_effort ("low", "high" or "max"). None leaves it out, so the provider's default
        (high) applies, as it always has. `max_tokens` caps reasoning and answer together; DeepSeek has no separate
        reasoning budget. At 16000, about 1 decision in 25 spent the whole cap on reasoning (smokes s3, s4), and at
        32768 8 of 219 still did (run live). A reply that thought but gave no whole answer, because it hit the cap or
        its stream broke off, is answered from the end of what it thought, once and without thinking again (ADR-030).
        Before, it was asked again and thought the whole plan up afresh. Only a reply that was asked to think is
        answered so: an answer given that way is never forced in turn (review of #80, 80-AB1).
        The reply is streamed: `on_reasoning(new_text)` receives the reasoning in pieces, about one a second, as
        it arrives (for the thinking log that viewers read)."""
        body = self._body(system, user, max_tokens, effort, stream=True)
        last_error = None
        for attempt in range(retries + 1):
            started = time.time()
            req = urllib.request.Request(self.base + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                         headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=360) as resp:  # a full-cap reply takes about 4 minutes
                    data = self._read_stream(resp, on_reasoning)
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as err:
                last_error = err
                time.sleep(2 * (attempt + 1))
                continue
            latency = time.time() - started
            usage = data.get("usage") or {}
            hit = usage.get("prompt_cache_hit_tokens", 0)
            miss = usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0) - hit)
            out = usage.get("completion_tokens", 0)
            reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
            prices = PRICES.get(self.model, PRICES["deepseek-flash"])
            cost = (hit * prices[0] + miss * prices[1] + out * prices[2]) / 1e6 * peak_multiplier()
            self.calls += 1
            self.cost += cost
            choice = (data.get("choices") or [{}])[0]
            self.log(kind="llm", purpose=purpose, model=data.get("model", self.model), latency=round(latency, 2),
                     cache_hit=hit, cache_miss=miss, output=out, reasoning=reasoning,
                     finish=choice.get("finish_reason"), cost=round(cost, 6))
            text = choice.get("message", {}).get("content") or ""
            try:
                return json.loads(text)
            except json.JSONDecodeError as err:
                last_error = err
                if effort != "none" and data.get("reasoning") and choice.get("finish_reason") != "stop":
                    try:
                        return self._answer_from(system, user, data["reasoning"], text, purpose)
                    except RuntimeError as forced_error:  # then as before: ask again, thinking
                        last_error = forced_error
                body["messages"].append({"role": "assistant", "content": text[:2000]})
                body["messages"].append({"role": "user", "content": "That was not valid JSON. Reply with the JSON object only."})
        raise RuntimeError(f"LLM call failed after {retries + 1} attempts: {last_error}")

    def _answer_from(self, system, user, reasoning, began, purpose):
        """The answer to a reply that thought but did not answer, from the end of its reasoning (ADR-030). It is the
        same question with the thoughts added at the end, so the provider reads the prompt again from its cache.
        `forced` counts the answers given, and the log says whether this one was (80-CDE5)."""
        note = FORCED_ANSWER.format(thoughts=reasoning[-ANSWER_FROM:],
                                    began=f"You had begun your answer: {began[:2000]}\n" if began.strip() else "")
        try:
            answer = self.complete_json(system, f"{user}\n\n{note}", purpose=f"{purpose}:answer",
                                        max_tokens=ANSWER_TOKENS, retries=1, effort="none")
        except RuntimeError:
            self.log(kind="answer_forced", purpose=purpose, ok=False)
            raise
        self.forced += 1
        self.log(kind="answer_forced", purpose=purpose, ok=True)
        return answer

    def _body(self, system, user, max_tokens, effort=None, stream=False):
        """One request. Thinking off ("none"), the temperature counts, and it is 0.7; thinking on, the provider ignores
        it (DeepSeek's thinking mode)."""
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0.7 if effort == "none" else 0.9,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if effort == "none":
            body["thinking"] = {"type": "disabled"}
        elif effort:
            body["reasoning_effort"] = effort
        if stream:
            body.update(stream=True, stream_options={"include_usage": True})
        return body

    def quick_json(self, system, user, purpose, max_tokens=80):
        """One short JSON reply without reasoning: under a second, for small readings beside the mind (the thought
        bubble), never for the mind's own decisions."""
        body = self._body(system, user, max_tokens, effort="none")
        started = time.time()
        req = urllib.request.Request(self.base + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        usage = data.get("usage") or {}
        hit = usage.get("prompt_cache_hit_tokens", 0)
        miss = usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0) - hit)
        out = usage.get("completion_tokens", 0)
        prices = PRICES.get(self.model, PRICES["deepseek-flash"])
        cost = (hit * prices[0] + miss * prices[1] + out * prices[2]) / 1e6 * peak_multiplier()
        self.calls += 1
        self.cost += cost
        self.log(kind="llm", purpose=purpose, model=data.get("model", self.model), latency=round(time.time() - started, 2),
                 cache_hit=hit, cache_miss=miss, output=out, reasoning=0, cost=round(cost, 6))
        return json.loads((data.get("choices") or [{}])[0].get("message", {}).get("content") or "{}")

    @staticmethod
    def _read_stream(resp, on_reasoning=None):
        """Collect a streamed reply into the shape of a non-streamed one; pass the reasoning on as it arrives.

        A connection that breaks once something has come (IncompleteRead, a reset, a read timeout) ends the reply there,
        with no finish reason, as a stream that stops early does: what it thought is kept (80-AB2). One that breaks
        before anything came is raised, and the call is made again."""
        content, finish, model, usage = [], None, None, {}
        pending, passed, thought = [], time.time(), []

        def pass_on():
            nonlocal pending, passed
            if on_reasoning and pending:
                try:
                    on_reasoning("".join(pending))
                except Exception:  # recording the thinking must never break the thinking
                    pass
            pending, passed = [], time.time()

        try:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                model = chunk.get("model") or model
                usage = chunk.get("usage") or usage
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    finish = choice.get("finish_reason") or finish
                    if delta.get("content"):
                        content.append(delta["content"])
                    if delta.get("reasoning_content"):
                        pending.append(delta["reasoning_content"])
                        thought.append(delta["reasoning_content"])
                        if time.time() - passed >= 1.0:
                            pass_on()
        except (http.client.HTTPException, OSError):
            if not (thought or content):
                raise  # nothing came: the call is made again
        finally:
            pass_on()
        return {"model": model, "usage": usage, "reasoning": "".join(thought),
                "choices": [{"finish_reason": finish, "message": {"content": "".join(content)}}]}
