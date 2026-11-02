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

    def complete_json(self, system, user, purpose="decide", max_tokens=32768, retries=2, on_reasoning=None):
        """One JSON reply. Reasoning stays fully on; the cap is high so reasoning never cuts the answer off.

        At 16000, about 1 decision in 25 spent the whole cap on reasoning and lost its answer (smokes s3, s4).
        The reply is streamed: `on_reasoning(new_text)` receives the reasoning in pieces, about one a second, as
        it arrives (for the thinking log that viewers read)."""
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0.9,
                "response_format": {"type": "json_object"}, "stream": True, "stream_options": {"include_usage": True},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
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
                body["messages"].append({"role": "assistant", "content": text[:2000]})
                body["messages"].append({"role": "user", "content": "That was not valid JSON. Reply with the JSON object only."})
        raise RuntimeError(f"LLM call failed after {retries + 1} attempts: {last_error}")

    def quick_json(self, system, user, purpose, max_tokens=80):
        """One short JSON reply without reasoning: under a second, for small readings beside the mind (the thought
        bubble), never for the mind's own decisions."""
        body = {"model": self.model, "max_tokens": max_tokens, "temperature": 0.7, "thinking": {"type": "disabled"},
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
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
        """Collect a streamed reply into the shape of a non-streamed one; pass the reasoning on as it arrives."""
        content, finish, model, usage = [], None, None, {}
        pending, passed = [], time.time()

        def pass_on():
            nonlocal pending, passed
            if on_reasoning and pending:
                try:
                    on_reasoning("".join(pending))
                except Exception:  # recording the thinking must never break the thinking
                    pass
            pending, passed = [], time.time()

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
                    if time.time() - passed >= 1.0:
                        pass_on()
        pass_on()
        return {"model": model, "usage": usage,
                "choices": [{"finish_reason": finish, "message": {"content": "".join(content)}}]}
