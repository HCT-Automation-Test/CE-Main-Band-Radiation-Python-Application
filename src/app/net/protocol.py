"""TCP 메시지 dataclass 및 length-prefix frame (de)serialize.

메시지 형태:
    Request/Event:
        {"type": "...", "id": "...", "target": "...", "command": "...", "Params": {...}}
    Response:
        {"type": "response", "id": "...", "status": "...", "Error": {...}, "Result": ...}
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeAlias

# TODO(spec): command 카탈로그 enum화 (명세 도착 후)

FRAME_HEADER_SIZE = 4
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
_LENGTH_STRUCT = struct.Struct(">I")


@dataclass
class Request:
    """외부 프로그램에 보내는 요청."""

    id: str
    target: str
    command: str
    params: dict[str, Any] = field(default_factory=dict)
    message_type: ClassVar[str] = "request"

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "type": self.message_type,
            "id": self.id,
            "target": self.target,
            "command": self.command,
            "Params": self.params,
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "Request":
        data = json.loads(s)
        return cls(
            id=str(data["id"]),
            target=str(data["target"]),
            command=str(data["command"]),
            params=_params_from_data(data),
        )


@dataclass
class Response:
    """외부 프로그램이 보낸 응답."""

    id: str
    status: str
    result: Any | None = None
    error: Any | None = None
    message_type: ClassVar[str] = "response"

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "type": self.message_type,
            "id": self.id,
            "status": self.status,
        }
        if self.error is not None:
            payload["Error"] = self.error
        if self.result is not None:
            payload["Result"] = self.result
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "Response":
        data = json.loads(s)
        return cls(
            id=str(data["id"]),
            status=str(data["status"]),
            result=data.get("Result"),
            error=data.get("Error"),
        )


@dataclass
class Event:
    """외부 프로그램이 비동기로 푸시하는 이벤트."""

    id: str
    target: str
    command: str
    params: dict[str, Any] = field(default_factory=dict)
    message_type: ClassVar[str] = "event"

    def to_json(self) -> str:
        payload: dict[str, Any] = {
            "type": self.message_type,
            "id": self.id,
            "target": self.target,
            "command": self.command,
            "Params": self.params,
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, s: str) -> "Event":
        data = json.loads(s)
        return cls(
            id=str(data["id"]),
            target=str(data["target"]),
            command=str(data["command"]),
            params=_params_from_data(data),
        )


Message: TypeAlias = Request | Response | Event


class ProtocolError(ValueError):
    """TCP/JSON 프로토콜 위반."""


def _params_from_data(data: dict[str, Any]) -> dict[str, Any]:
    """wire JSON의 Params 객체를 Python dict로 변환한다."""
    raw_params = data.get("Params")
    if raw_params is None:
        return {}
    if not isinstance(raw_params, dict):
        raise TypeError("Params must be an object")
    return dict(raw_params)


def message_from_json(s: str) -> Message:
    """JSON 문자열을 type에 맞는 메시지 dataclass로 변환한다."""
    try:
        data = json.loads(s)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON payload: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ProtocolError("JSON payload must be an object")

    message_type = data.get("type")
    try:
        if message_type == Request.message_type:
            return Request(
                id=str(data["id"]),
                target=str(data["target"]),
                command=str(data["command"]),
                params=_params_from_data(data),
            )
        if message_type == Response.message_type:
            return Response(
                id=str(data["id"]),
                status=str(data["status"]),
                result=data.get("Result"),
                error=data.get("Error"),
            )
        if message_type == Event.message_type:
            return Event(
                id=str(data["id"]),
                target=str(data["target"]),
                command=str(data["command"]),
                params=_params_from_data(data),
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolError(f"invalid {message_type!r} message payload") from exc

    raise ProtocolError(f"unknown message type: {message_type!r}")


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
