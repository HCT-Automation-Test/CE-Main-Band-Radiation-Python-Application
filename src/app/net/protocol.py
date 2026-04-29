"""TCP 메시지 dataclass 및 length-prefix frame (de)serialize.

메시지 형태(잠정):
    {"id": "uuid", "kind": "request|response|event",
     "op": "string", "params": {...}, "result": {...}, "error": null}
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeAlias

# TODO(spec): op 카탈로그 enum화 (명세 도착 후)

FRAME_HEADER_SIZE = 4
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
_LENGTH_STRUCT = struct.Struct(">I")


@dataclass
class Request:
    """외부 프로그램에 보내는 요청."""

    id: str
    op: str
    params: dict[str, Any] = field(default_factory=dict)
    kind: ClassVar[str] = "request"

    def to_json(self) -> str:
        payload = {
            "kind": self.kind,
            "id": self.id,
            "op": self.op,
            "params": self.params,
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "Request":
        data = json.loads(s)
        return cls(id=str(data["id"]), op=str(data["op"]), params=dict(data.get("params") or {}))


@dataclass
class Response:
    """외부 프로그램이 보낸 응답."""

    id: str
    op: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    kind: ClassVar[str] = "response"

    def to_json(self) -> str:
        payload = {
            "kind": self.kind,
            "id": self.id,
            "op": self.op,
            "result": self.result,
            "error": self.error,
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "Response":
        data = json.loads(s)
        return cls(id=str(data["id"]), op=str(data["op"]),
                   result=data.get("result"), error=data.get("error"))


@dataclass
class Event:
    """외부 프로그램이 비동기로 푸시하는 이벤트."""

    id: str
    op: str
    params: dict[str, Any] = field(default_factory=dict)
    kind: ClassVar[str] = "event"

    def to_json(self) -> str:
        return json.dumps(
            {
                "kind": self.kind,
                "id": self.id,
                "op": self.op,
                "params": self.params,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, s: str) -> "Event":
        data = json.loads(s)
        return cls(id=str(data["id"]), op=str(data["op"]), params=dict(data.get("params") or {}))


Message: TypeAlias = Request | Response | Event


class ProtocolError(ValueError):
    """TCP/JSON 프로토콜 위반."""


def message_from_json(s: str) -> Message:
    """JSON 문자열을 kind에 맞는 메시지 dataclass로 변환한다."""
    try:
        data = json.loads(s)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON payload: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ProtocolError("JSON payload must be an object")

    kind = data.get("kind")
    try:
        if kind == Request.kind:
            return Request(
                id=str(data["id"]),
                op=str(data["op"]),
                params=dict(data.get("params") or {}),
            )
        if kind == Response.kind:
            return Response(
                id=str(data["id"]),
                op=str(data["op"]),
                result=data.get("result"),
                error=data.get("error"),
            )
        if kind == Event.kind:
            return Event(
                id=str(data["id"]),
                op=str(data["op"]),
                params=dict(data.get("params") or {}),
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolError(f"invalid {kind!r} message payload") from exc

    raise ProtocolError(f"unknown message kind: {kind!r}")


def encode_frame(message: Message | str | bytes) -> bytes:
    """메시지를 4-byte big-endian length prefix frame으로 인코딩한다."""
    if isinstance(message, bytes):
        payload = message
    elif isinstance(message, str):
        payload = message.encode("utf-8")
    else:
        payload = message.to_json().encode("utf-8")

    payload_length = len(payload)
    if payload_length > MAX_PAYLOAD_BYTES:
        raise ProtocolError(
            f"payload is too large: {payload_length} > {MAX_PAYLOAD_BYTES}"
        )
    return _LENGTH_STRUCT.pack(payload_length) + payload


def decode_frames(buffer: bytearray) -> list[Message]:
    """buffer에서 완성된 frame들을 파싱하고 남은 partial frame은 보존한다."""
    messages: list[Message] = []
    offset = 0

    while len(buffer) - offset >= FRAME_HEADER_SIZE:
        payload_length = _LENGTH_STRUCT.unpack(
            buffer[offset : offset + FRAME_HEADER_SIZE]
        )[0]
        if payload_length > MAX_PAYLOAD_BYTES:
            raise ProtocolError(
                f"payload is too large: {payload_length} > {MAX_PAYLOAD_BYTES}"
            )

        frame_end = offset + FRAME_HEADER_SIZE + payload_length
        if len(buffer) < frame_end:
            break

        payload = bytes(buffer[offset + FRAME_HEADER_SIZE : frame_end])
        try:
            payload_text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("payload is not valid UTF-8") from exc
        messages.append(message_from_json(payload_text))
        offset = frame_end

    if offset:
        del buffer[:offset]
    return messages
