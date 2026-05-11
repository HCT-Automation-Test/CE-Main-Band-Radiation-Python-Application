"""Request/Response/Event JSON 라운드트립."""
from __future__ import annotations

import json
import struct

import pytest

from app.net.protocol import (
    Event,
    ProtocolError,
    Request,
    Response,
    decode_frames,
    encode_frame,
    message_from_json,
)


def _json_keys(payload: str) -> list[str]:
    return list(json.loads(payload).keys())


def test_request_roundtrip() -> None:
    req = Request(
        id="abc-1",
        target="fsv",
        command="ping",
        params={"x": 1, "s": "hi"},
    )
    assert _json_keys(req.to_json()) == ["type", "id", "target", "command", "Params"]

    round_tripped = Request.from_json(req.to_json())
    assert round_tripped.id == "abc-1"
    assert round_tripped.target == "fsv"
    assert round_tripped.command == "ping"
    assert round_tripped.params == {"x": 1, "s": "hi"}


def test_response_default_roundtrip() -> None:
    res = Response(id="abc-1", status="ok")
    assert _json_keys(res.to_json()) == ["type", "id", "status"]

    round_tripped = Response.from_json(res.to_json())
    assert round_tripped.id == "abc-1"
    assert round_tripped.status == "ok"
    assert round_tripped.result is None
    assert round_tripped.error is None


def test_response_result_roundtrip() -> None:
    res = Response(id="abc-1", status="ok", result={"power": -30.5})
    assert _json_keys(res.to_json()) == ["type", "id", "status", "Result"]

    round_tripped = Response.from_json(res.to_json())
    assert round_tripped.result == {"power": -30.5}
    assert round_tripped.error is None


def test_response_error_roundtrip() -> None:
    res = Response(id="abc-1", status="error", error={"message": "stalled"})
    assert _json_keys(res.to_json()) == ["type", "id", "status", "Error"]

    round_tripped = Response.from_json(res.to_json())
    assert round_tripped.status == "error"
    assert round_tripped.result is None
    assert round_tripped.error == {"message": "stalled"}


def test_event_roundtrip() -> None:
    ev = Event(
        id="evt-1",
        target="co3000",
        command="turntable_progress",
        params={"percent": 50},
    )
    assert _json_keys(ev.to_json()) == ["type", "id", "target", "command", "Params"]

    round_tripped = Event.from_json(ev.to_json())
    assert round_tripped.target == "co3000"
    assert round_tripped.command == "turntable_progress"
    assert round_tripped.params == {"percent": 50}


def test_encode_frame_uses_big_endian_payload_byte_length() -> None:
    req = Request(
        id="abc-1",
        target="fsv",
        command="한글",
        params={"message": "측정"},
    )

    frame = encode_frame(req)
    payload = req.to_json().encode("utf-8")

    assert frame[:4] == struct.pack(">I", len(payload))
    assert frame[4:] == payload


def test_decode_frames_keeps_partial_frame_in_buffer() -> None:
    event = Event(
        id="evt-1",
        target="co3000",
        command="turntable_progress",
        params={"percent": 50},
    )
    frame = encode_frame(event)
    buffer = bytearray(frame[:6])

    assert decode_frames(buffer) == []
    assert buffer == bytearray(frame[:6])

    buffer.extend(frame[6:])
    messages = decode_frames(buffer)

    assert messages == [event]
    assert buffer == bytearray()


def test_decode_frames_reads_consecutive_frames() -> None:
    response = Response(id="abc-1", status="ok", result={"ok": True})
    event = Event(
        id="evt-1",
        target="co3000",
        command="turntable_progress",
        params={"percent": 100},
    )
    buffer = bytearray(encode_frame(response) + encode_frame(event))

    assert decode_frames(buffer) == [response, event]
    assert buffer == bytearray()


def test_message_from_json_rejects_unknown_type() -> None:
    with pytest.raises(ProtocolError, match="unknown message type"):
        message_from_json('{"type": "unknown", "id": "1", "command": "ping"}')


def test_decode_frames_rejects_malformed_json() -> None:
    buffer = bytearray(encode_frame('{"type": "response"'))

    with pytest.raises(ProtocolError, match="invalid JSON payload"):
        decode_frames(buffer)
