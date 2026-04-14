"""시험 타입 → 시퀀스 매핑 레지스트리."""
from __future__ import annotations

from typing import Any

from app.core.fsm.harmonic.sequence import HarmonicSequence
from app.models.enums import TestType

SEQUENCES: dict[TestType, type[Any]] = {
    TestType.HARMONIC: HarmonicSequence,
    # TODO(spec): INBAND, BILOG 시퀀스 등록
}
