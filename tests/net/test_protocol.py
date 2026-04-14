"""Request/Response/Event JSON 라운드트립."""
from __future__ import annotations

from app.net.protocol import Event, Request, Response


def test_request_roundtrip() -> None:
    req = Request(id="abc-1", op="ping", params={"x": 1, "s": "hi"})
    round_tripped = Request.from_json(req.to_json())
    assert round_tripped.id == "abc-1"
    assert round_tripped.op == "ping"
    assert round_tripped.params == {"x": 1, "s": "hi"}


def test_response_roundtrip() -> None:
    res = Response(id="abc-1", op="ping", result={"ok": True}, error=None)
    round_tripped = Response.from_json(res.to_json())
    assert round_tripped.id == "abc-1"
    assert round_tripped.result == {"ok": True}
    assert round_tripped.error is None


def test_event_roundtrip() -> None:
    ev = Event(id="evt-1", op="progress", params={"percent": 50})
    round_tripped = Event.from_json(ev.to_json())
    assert round_tripped.op == "progress"
    assert round_tripped.params == {"percent": 50}
