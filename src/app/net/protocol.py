"""TCP 메시지 dataclass 및 (de)serialize.

메시지 형태(잠정):
    {"id": "uuid", "kind": "request|response|event",
     "op": "string", "params": {...}, "result": {...}, "error": null}
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar

# TODO(spec): op 카탈로그 enum화 (명세 도착 후)


@dataclass
class Request:
    """외부 프로그램에 보내는 요청."""

    id: str
    op: str
    params: dict[str, Any] = field(default_factory=dict)
    kind: ClassVar[str] = "request"

    def to_json(self) -> str:
        payload = {"kind": self.kind, "id": self.id, "op": self.op, "params": self.params}
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
        payload = {"kind": self.kind, "id": self.id, "op": self.op,
                   "result": self.result, "error": self.error}
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
        return json.dumps({"kind": self.kind, "id": self.id, "op": self.op, "params": self.params},
                          ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "Event":
        data = json.loads(s)
        return cls(id=str(data["id"]), op=str(data["op"]), params=dict(data.get("params") or {}))
