"""열거형 정의."""
from __future__ import annotations

from enum import Enum


class TestType(Enum):
    """시험 종류."""

    HARMONIC = "harmonic"
    INBAND = "inband"
    BILOG = "bilog"


class AntennaPol(Enum):
    """안테나 편파."""

    H = "H"
    V = "V"


class DUTAxis(Enum):
    """DUT 회전축."""

    X = "X"
    Y = "Y"
    Z = "Z"


class Modulation(Enum):
    """변조 방식 placeholder. TODO(spec): 실제 값 확정 필요."""

    # TODO(spec): QPSK/16QAM/64QAM/256QAM 등 명세 도착 후 채움
    UNSPECIFIED = "unspecified"
