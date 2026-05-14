"""고정 전역 Range 정의."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from app.models.enums import FilterMode, InputPath


class RangeId(IntEnum):
    """측정 흐름 전반에서 사용하는 전역 Range 식별자."""

    RANGE_1 = 1
    RANGE_2 = 2
    RANGE_3 = 3
    RANGE_4 = 4
    RANGE_5 = 5
    RANGE_6 = 6

    @property
    def key(self) -> str:
        return f"range_{self.value}"

    @property
    def label(self) -> str:
        return f"Range {self.value}"

    @classmethod
    def coerce(cls, value: "RangeId | int | str") -> "RangeId":
        """int/문자열 입력을 정규화해 RangeId로 변환한다."""

        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            raise ValueError(f"Invalid range value: {value!r}")
        if isinstance(value, int):
            try:
                return cls(value)
            except ValueError as exc:
                raise ValueError(f"Unknown range id: {value}") from exc
        if isinstance(value, str):
            normalized = value.strip().lower().replace("_", "").replace(" ", "")
            if normalized.startswith("range"):
                normalized = normalized[5:]
            try:
                return cls(int(normalized))
            except ValueError as exc:
                raise ValueError(f"Unknown range label: {value!r}") from exc
        raise ValueError(f"Invalid range value type: {type(value).__name__}")


@dataclass(frozen=True)
class TestRange:
    """고정 전역 Range에 대응하는 Spectrum Analyzer + Switch Box 설정."""

    __test__ = False

    id: RangeId
    start_freq: float
    stop_freq: float
    rbw: float
    vbw: float
    limit: float
    sweep_point: int
    input_path: InputPath
    filter_mode: FilterMode

    @property
    def name(self) -> str:
        return self.id.key

    @property
    def sweep_points(self) -> int:
        return self.sweep_point


RANGE_1 = TestRange(
    id=RangeId.RANGE_1,
    start_freq=30.0,
    stop_freq=1000.0,
    rbw=0.1,
    vbw=0.3,
    limit=-36.0,
    sweep_point=10001,
    input_path=InputPath.INPUT2,
    filter_mode=FilterMode.BRF,
)

RANGE_2 = TestRange(
    id=RangeId.RANGE_2,
    start_freq=1000.0,
    stop_freq=3000.0,
    rbw=1.0,
    vbw=3.0,
    limit=-30.0,
    sweep_point=30001,
    input_path=InputPath.INPUT1,
    filter_mode=FilterMode.BRF,
)

RANGE_3 = TestRange(
    id=RangeId.RANGE_3,
    start_freq=1000.0,
    stop_freq=12750.0,
    rbw=1.0,
    vbw=3.0,
    limit=-30.0,
    sweep_point=30001,
    input_path=InputPath.INPUT1,
    filter_mode=FilterMode.HPF_1G,
)

RANGE_4 = TestRange(
    id=RangeId.RANGE_4,
    start_freq=3000.0,
    stop_freq=12750.0,
    rbw=1.0,
    vbw=3.0,
    limit=-30.0,
    sweep_point=30001,
    input_path=InputPath.INPUT1,
    filter_mode=FilterMode.HPF_3G,
)

RANGE_5 = TestRange(
    id=RangeId.RANGE_5,
    start_freq=1000.0,
    stop_freq=6000.0,
    rbw=1.0,
    vbw=3.0,
    limit=-30.0,
    sweep_point=30001,
    input_path=InputPath.INPUT3,
    filter_mode=FilterMode.BRF,
)

RANGE_6 = TestRange(
    id=RangeId.RANGE_6,
    start_freq=6000.0,
    stop_freq=18000.0,
    rbw=1.0,
    vbw=3.0,
    limit=-30.0,
    sweep_point=30001,
    input_path=InputPath.INPUT3,
    filter_mode=FilterMode.HPF_6G,
)


ALL_TEST_RANGES: tuple[TestRange, ...] = (
    RANGE_1,
    RANGE_2,
    RANGE_3,
    RANGE_4,
    RANGE_5,
    RANGE_6,
)

TEST_RANGES_BY_ID: dict[RangeId, TestRange] = {
    test_range.id: test_range for test_range in ALL_TEST_RANGES
}


def get_test_range(range_id: RangeId | int | str) -> TestRange:
    """식별자에 해당하는 고정 TestRange 정의를 반환한다."""

    normalized = RangeId.coerce(range_id)
    return TEST_RANGES_BY_ID[normalized]
