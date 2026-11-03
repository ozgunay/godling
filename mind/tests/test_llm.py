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
