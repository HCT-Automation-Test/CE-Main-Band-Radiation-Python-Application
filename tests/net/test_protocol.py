"""Request/Response/Event JSON 라운드트립."""
from __future__ import annotations

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


def test_encode_frame_uses_big_endian_payload_byte_length() -> None:
    req = Request(id="abc-1", op="한글", params={"message": "측정"})

    frame = encode_frame(req)
    payload = req.to_json().encode("utf-8")

    assert frame[:4] == struct.pack(">I", len(payload))
    assert frame[4:] == payload


def test_decode_frames_keeps_partial_frame_in_buffer() -> None:
    event = Event(id="evt-1", op="progress", params={"percent": 50})
    frame = encode_frame(event)
    buffer = bytearray(frame[:6])

    assert decode_frames(buffer) == []
    assert buffer == bytearray(frame[:6])

    buffer.extend(frame[6:])
    messages = decode_frames(buffer)

    assert messages == [event]
    assert buffer == bytearray()


def test_decode_frames_reads_consecutive_frames() -> None:
    response = Response(id="abc-1", op="ping", result={"ok": True})
    event = Event(id="evt-1", op="progress", params={"percent": 100})
    buffer = bytearray(encode_frame(response) + encode_frame(event))

    assert decode_frames(buffer) == [response, event]
    assert buffer == bytearray()


def test_message_from_json_rejects_unknown_kind() -> None:
    with pytest.raises(ProtocolError, match="unknown message kind"):
        message_from_json('{"kind": "unknown", "id": "1", "op": "ping"}')


def test_decode_frames_rejects_malformed_json() -> None:
    buffer = bytearray(encode_frame('{"kind": "response"'))

    with pytest.raises(ProtocolError, match="invalid JSON payload"):
        decode_frames(buffer)
