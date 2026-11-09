import http.client
import io
import itertools
import json
import urllib.error
from datetime import datetime, timezone

import pytest

from godling import llm as llm_module
from godling.llm import LLM, load_api_key, peak_multiplier


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def stream(*chunks, done=True):
    lines = [b"event: ignored\n", b"data: not json\n"]
    lines += [b"data: " + json.dumps(c).encode() + b"\n" for c in chunks]
    if done:
        lines.append(b"data: [DONE]\n")
        lines.append(b"data: " + json.dumps({"choices": [{"delta": {"content": "after done"}}]}).encode() + b"\n")
    return Reply(b"".join(lines))


@pytest.fixture
def requests(monkeypatch):
    """Replies queued for urlopen, and the requests that were sent."""
    sent, queue = [], []

    def urlopen(req, timeout=None):
        sent.append((req, timeout))
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(llm_module.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm_module.time, "sleep", lambda s: None)
    monkeypatch.setattr(llm_module, "peak_multiplier", lambda now=None: 1)
    return sent, queue


def test_peak_multiplier():
    assert peak_multiplier(datetime(2026, 11, 2, 2, tzinfo=timezone.utc)) == 2  # Monday 02:00
    assert peak_multiplier(datetime(2026, 11, 2, 7, tzinfo=timezone.utc)) == 2
    assert peak_multiplier(datetime(2026, 11, 2, 12, tzinfo=timezone.utc)) == 1
    assert peak_multiplier(datetime(2026, 11, 1, 2, tzinfo=timezone.utc)) == 1  # Sunday
    assert peak_multiplier() in (1, 2)


def test_load_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
    assert load_api_key() == "env-key"
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    monkeypatch.setattr(llm_module.Path, "home", lambda: tmp_path)
    with pytest.raises(RuntimeError, match="No DeepSeek key"):
        load_api_key()
    settings = tmp_path / ".claude-deepseek" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"env": {}}))
    with pytest.raises(RuntimeError):
        load_api_key()
    settings.write_text(json.dumps({"env": {"ANTHROPIC_AUTH_TOKEN": "file-key"}}))
    assert load_api_key() == "file-key"
    assert LLM().key == "file-key"


def test_complete_json_streams_and_counts_cost(requests):
    sent, queue = requests
    logs, reasoning = [], []
    queue.append(stream(
        {"model": "deepseek-flash", "choices": [{"delta": {"reasoning_content": "think "}}]},
        {"choices": [{"delta": {"reasoning_content": "more"}}]},
        {"choices": [{"delta": {"content": '{"a": '}}]},
        {"choices": [{"delta": {"content": "1}"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_cache_hit_tokens": 1000, "prompt_cache_miss_tokens": 2000,
                                  "completion_tokens": 500, "completion_tokens_details": {"reasoning_tokens": 300}}},
    ))
    model = LLM(api_key="k", log=lambda **kw: logs.append(kw))
    assert model.complete_json("sys", "user", on_reasoning=reasoning.append) == {"a": 1}
    assert "".join(reasoning) == "think more"
    req, timeout = sent[0]
    body = json.loads(req.data)
    assert timeout == 360 and body["stream"] and body["messages"][1]["content"] == "user"
    assert req.get_header("Authorization") == "Bearer k"
    assert model.calls == 1 and model.cost == pytest.approx((1000 * 0.003 + 2000 * 0.15 + 500 * 0.6) / 1e6)
    assert logs[0]["reasoning"] == 300 and logs[0]["finish"] == "stop" and logs[0]["model"] == "deepseek-flash"


def test_complete_json_retries_on_errors_and_bad_json(requests):
    sent, queue = requests
    queue.append(urllib.error.URLError("down"))
    queue.append(stream({"choices": [{"delta": {"content": "not json"}}]},
                        {"usage": {"prompt_tokens": 10, "completion_tokens": 2}}, done=False))
    queue.append(stream({"choices": [{"delta": {"content": '{"ok": true}'}}]}))
    model = LLM(model="unknown-model", api_key="k")
    assert model.complete_json("s", "u", retries=2) == {"ok": True}
    last = json.loads(sent[-1][0].data)["messages"]
    assert last[-2] == {"role": "assistant", "content": "not json"} and "not valid JSON" in last[-1]["content"]
    assert model.calls == 2


def test_complete_json_gives_up(requests):
    _, queue = requests
    queue.extend([TimeoutError("slow"), ConnectionError("reset")])
    with pytest.raises(RuntimeError, match="after 2 attempts: reset"):
        LLM(api_key="k").complete_json("s", "u", retries=1)


def answered(text='{"ok": 1}', usage=None):
    return stream({"choices": [{"delta": {"content": text}, "finish_reason": "stop"}]},
                  {"choices": [], "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5}})


def test_reasoning_effort_is_sent_only_when_asked_for(requests):
    """ADR-030: how hard the mind thinks is an option. Unset, the request is today's: no effort named, so the provider's
    default (high), and the cap of 32768 tokens."""
    sent, queue = requests
    queue.extend([answered(), answered(), answered()])
    model = LLM(api_key="k")
    model.complete_json("s", "u")
    model.complete_json("s", "u", effort="low", max_tokens=16000)
    model.complete_json("s", "u", effort="none")
    today, low, off = (json.loads(req.data) for req, _ in sent)
    assert "reasoning_effort" not in today and "thinking" not in today and today["max_tokens"] == llm_module.DECIDE_TOKENS
    assert low["reasoning_effort"] == "low" and low["max_tokens"] == 16000 and "thinking" not in low
    assert off["thinking"] == {"type": "disabled"} and "reasoning_effort" not in off
    # Review of #80 (80-CLEAN1): thinking off, the temperature counts, and it is the bubble's (quick_json), not 0.9.
    assert today["temperature"] == 0.9 and off["temperature"] == 0.7


def test_an_answer_cut_off_by_the_cap_is_given_from_the_reasoning_so_far(requests):
    """Run live (2026-11-08): 8 of 219 decisions spent all 32768 tokens on reasoning, about 200 s each, and lost their
    answer; the retry then thought the whole plan up again. Past the cap, the answer now comes from what it has thought,
    in one call that does not think again."""
    sent, queue = requests
    logs, heard = [], []
    queue.append(stream(
        {"choices": [{"delta": {"reasoning_content": "an early idea. " * 3000}}]},
        {"choices": [{"delta": {"reasoning_content": "so: fetch Log_4 for the wall"}}]},
        {"choices": [{"delta": {"content": '{"thought": "the wa'}, "finish_reason": "length"}]},
        {"choices": [], "usage": {"prompt_tokens": 9000, "completion_tokens": 32768,
                                  "completion_tokens_details": {"reasoning_tokens": 32760}}}))
    queue.append(answered('{"thought": "the wall"}', {"prompt_tokens": 9500, "completion_tokens": 40}))
    model = LLM(api_key="k", log=lambda **kw: logs.append(kw))
    assert model.complete_json("sys", "situation", purpose="decide", on_reasoning=heard.append) == {"thought": "the wall"}
    assert len(sent) == 2 and model.forced == 1 and model.calls == 2
    assert {"kind": "answer_forced", "purpose": "decide", "ok": True} in logs
    logs[:] = [entry for entry in logs if entry["kind"] == "llm"]
    answer = json.loads(sent[1][0].data)
    assert answer["thinking"] == {"type": "disabled"} and answer["max_tokens"] <= 4096
    assert answer["messages"][0]["content"] == "sys" and len(answer["messages"]) == 2
    asked = answer["messages"][1]["content"]
    assert asked.startswith("situation") and "so: fetch Log_4 for the wall" in asked and '{"thought": "the wa' in asked
    assert len(asked) < 20000  # the end of its thinking, not all of it
    assert [entry["purpose"] for entry in logs] == ["decide", "decide:answer"] and logs[0]["finish"] == "length"
    assert "".join(heard).endswith("so: fetch Log_4 for the wall")  # the viewers still read all of it


def test_a_reply_that_broke_off_is_answered_from_its_reasoning_too(requests):
    """A stream that ends without a finish reason (three in run live, one after 223 s) keeps what it thought."""
    sent, queue = requests
    queue.append(stream({"choices": [{"delta": {"reasoning_content": "thinking hard"}}]}, done=False))
    queue.append(answered())
    model = LLM(api_key="k")
    assert model.complete_json("s", "u") == {"ok": 1}
    assert model.forced == 1 and json.loads(sent[1][0].data)["thinking"] == {"type": "disabled"}


def test_a_forced_answer_that_fails_falls_back_to_asking_again(requests):
    sent, queue = requests
    logs = []
    queue.append(stream({"choices": [{"delta": {"reasoning_content": "r"}, "finish_reason": "length"}]}))
    queue.extend([answered("still not json"), answered("nor this"), answered()])
    model = LLM(api_key="k", log=lambda **kw: logs.append(kw))
    assert model.complete_json("s", "u", retries=1) == {"ok": 1}
    last = json.loads(sent[-1][0].data)
    assert "thinking" not in last and "not valid JSON" in last["messages"][-1]["content"]
    # Review of #80 (80-CDE5): `forced` counts answers given, not attempts; the log says which attempt failed.
    assert model.forced == 0 and {"kind": "answer_forced", "purpose": "decide", "ok": False} in logs


def test_a_forced_answer_never_forces_itself_again(requests):
    """Review of #80 (80-AB1): whether to force is decided by the request. A forced call (thinking off) whose reply still
    streams reasoning and is cut off again is asked once more as an ordinary reply, never forced in turn: no nesting."""
    sent, queue = requests
    logs = []
    queue.append(stream({"choices": [{"delta": {"reasoning_content": "deep"}, "finish_reason": "length"}]}))
    queue.append(stream({"choices": [{"delta": {"reasoning_content": "still thinking"}, "finish_reason": "length"}]}))
    queue.append(answered())
    model = LLM(api_key="k", log=lambda **kw: logs.append(kw))
    assert model.complete_json("s", "u") == {"ok": 1}
    assert [entry["purpose"] for entry in logs if entry["kind"] == "llm"] == ["decide", "decide:answer", "decide:answer"]
    assert "not valid JSON" in json.loads(sent[2][0].data)["messages"][-1]["content"] and model.forced == 1


class Breaking(Reply):
    """A streamed reply whose connection breaks after `lines` lines."""

    def __init__(self, lines, error):
        super().__init__(b"")
        self.lines, self.error = list(lines), error

    def __iter__(self):
        yield from self.lines
        raise self.error


def test_a_stream_broken_by_an_error_is_answered_from_its_reasoning(requests):
    """Review of #80 (80-AB2): a connection that breaks mid-stream (IncompleteRead, a reset, a read timeout) after the
    reasoning began keeps what it thought, as a stream that ends without a finish does; one that breaks before anything
    came is asked again, as before."""
    sent, queue = requests
    heard = []
    piece = b"data: " + json.dumps({"choices": [{"delta": {"reasoning_content": "minutes of thought"}}]}).encode() + b"\n"
    queue.append(Breaking([piece], http.client.IncompleteRead(b"")))
    queue.append(answered())
    model = LLM(api_key="k")
    assert model.complete_json("s", "u", on_reasoning=heard.append) == {"ok": 1}
    assert model.forced == 1 and "".join(heard) == "minutes of thought"
    forced = json.loads(sent[1][0].data)
    assert forced["thinking"] == {"type": "disabled"} and "minutes of thought" in forced["messages"][1]["content"]
    queue.extend([Breaking([], ConnectionResetError("reset")), answered()])
    assert model.complete_json("s", "u") == {"ok": 1}
    assert "thinking" not in json.loads(sent[-1][0].data) and model.forced == 1


def test_a_reply_without_thinking_is_never_forced(requests):
    """With thinking off there is nothing to answer from: a bad reply is asked again, as before."""
    sent, queue = requests
    queue.extend([stream({"choices": [{"delta": {"content": "{"}, "finish_reason": "length"}]}), answered()])
    model = LLM(api_key="k")
    assert model.complete_json("s", "u", effort="none") == {"ok": 1}
    assert model.forced == 0 and "not valid JSON" in json.loads(sent[1][0].data)["messages"][-1]["content"]


def test_reasoning_callback_failures_are_swallowed(monkeypatch):
    clock = itertools.count(0, 5)  # every reading of the clock is 5 s later: each piece is passed on alone
    monkeypatch.setattr(llm_module.time, "time", lambda: next(clock))
    calls = []

    def broken(text):
        calls.append(text)
        raise ValueError("no")

    data = LLM._read_stream(stream({"choices": [{"delta": {"reasoning_content": "a"}}]},
                                   {"choices": [{"delta": {"reasoning_content": "b"}}]}), broken)
    assert calls == ["a", "b"] and data["choices"][0]["message"]["content"] == ""


def test_read_stream_without_callback():
    data = LLM._read_stream(stream({"model": "m", "choices": [{"delta": {"reasoning_content": "r", "content": "c"}}]}))
    assert data["model"] == "m" and data["choices"][0]["message"]["content"] == "c"


def test_quick_json(requests):
    sent, queue = requests
    logs = []
    reply = {"model": "deepseek-flash", "usage": {"prompt_tokens": 100, "prompt_cache_hit_tokens": 40,
                                                  "completion_tokens": 10},
             "choices": [{"message": {"content": '{"thing": "fish"}'}}]}
    queue.append(Reply(json.dumps(reply).encode()))
    model = LLM(api_key="k", log=lambda **kw: logs.append(kw))
    assert model.quick_json("s", "u", purpose="bubble") == {"thing": "fish"}
    body = json.loads(sent[0][0].data)
    assert body["thinking"] == {"type": "disabled"} and body["max_tokens"] == 80 and sent[0][1] == 30
    assert logs[0]["purpose"] == "bubble" and logs[0]["cache_miss"] == 60
    queue.append(Reply(json.dumps({"choices": [{"message": {}}]}).encode()))
    assert model.quick_json("s", "u", purpose="bubble") == {}
    assert model.calls == 2
