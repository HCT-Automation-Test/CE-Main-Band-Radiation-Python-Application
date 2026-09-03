"""Test Case 데이터 모델과 CSV 변환 헬퍼."""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from app.models.band_group import find_band_group, resolve_range_id
from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Generation,
    LTEBand,
    LTERBAllocation,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel,
    TestType,
)
from app.models.lte_band_group import find_lte_band_group, resolve_lte_range_id
from app.models.lte_channel_lookup import resolve_arfcn, resolve_lte_frequency_mhz
from app.models.lte_rb_parameters import resolve_lte_rb_parameters
from app.models.lte_supported_bandwidths import validate_lte_supported_bandwidth
from app.models.nr_channel_lookup import resolve_call_channel, resolve_target_frequency_mhz
from app.models.nsa_anchor import validate_anchor_band_for_generation
from app.models.rb_parameters import resolve_rb_parameters
from app.models.supported_bandwidths import validate_supported_bandwidth
from app.models.test_range import RangeId, TestRange, get_test_range

CSV_FIELDNAMES: tuple[str, ...] = (
    "generation",
    "band",
    "anchor_band",
    "bandwidth",
    "test_type",
    "modulation",
    "rb_allocation",
    "test_channel",
    "antenna_pol",
    "dut_axis",
    "dut_ant_position",
)

EnumT = TypeVar("EnumT", bound=Enum)


def _get_required_csv_value(row: dict[str, Any], field_name: str) -> str:
    value = row.get(field_name)
    if value is None:
        raise ValueError(f"Missing required field: {field_name}")

    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"Empty required field: {field_name}")
    return normalized


def _parse_bandwidth_value(raw_value: str) -> float:
    try:
        bandwidth = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"Invalid bandwidth: {raw_value!r}") from exc

    if not math.isfinite(bandwidth):
        raise ValueError(f"Invalid bandwidth: {raw_value!r}")
    return bandwidth


def _coerce_bandwidth_value(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Invalid bandwidth: {value!r}")
    if isinstance(value, str):
        return _parse_bandwidth_value(value.strip())
    if isinstance(value, int | float):
        bandwidth = float(value)
        if not math.isfinite(bandwidth):
            raise ValueError(f"Invalid bandwidth: {value!r}")
        return bandwidth
    raise ValueError(f"Invalid bandwidth: {value!r}")


def _format_bandwidth_value(bandwidth: float) -> str:
    return format(_coerce_bandwidth_value(bandwidth), ".15g")


def _coerce_enum_value(value: Any, field_name: str, enum_type: type[EnumT]) -> EnumT:
    if isinstance(value, enum_type):
        return value

    raw_value = str(value).strip()
    for member in enum_type:
        if str(member.value).lower() == raw_value.lower():
            return member
    raise ValueError(f"Invalid {field_name}: {raw_value!r}")


def _parse_enum_value(row: dict[str, Any], field_name: str, enum_type: type[EnumT]) -> EnumT:
    return _coerce_enum_value(_get_required_csv_value(row, field_name), field_name, enum_type)


def _parse_optional_enum_value(
    row: dict[str, Any],
    field_name: str,
    enum_type: type[EnumT],
) -> EnumT | None:
    value = row.get(field_name)
    if value is None or not str(value).strip():
        return None
    return _coerce_enum_value(value, field_name, enum_type)


@dataclass
class TestCase:
    """CSV 스키마의 한 행을 표현하는 Test Case."""

    __test__ = False

    band: NRBand | LTEBand
    bandwidth: float
    test_type: TestType
    modulation: Modulation
    rb_allocation: RBAllocation | LTERBAllocation
    test_channel: TestChannel
    antenna_pol: AntennaPol
    dut_axis: DUTAxis
    dut_ant_position: DUTAntPosition
    generation: Generation = Generation.NR_SA
    anchor_band: LTEBand | None = None

    def __post_init__(self) -> None:
        self.generation = _coerce_enum_value(self.generation, "generation", Generation)
        if self.anchor_band is not None and str(self.anchor_band).strip():
            self.anchor_band = _coerce_enum_value(
                self.anchor_band,
                "anchor_band",
                LTEBand,
            )
        else:
            self.anchor_band = None

        validate_anchor_band_for_generation(self.generation, self.anchor_band)

        if self.generation is Generation.LTE:
            self.band = _coerce_enum_value(self.band, "band", LTEBand)
            self.rb_allocation = _coerce_enum_value(
                self.rb_allocation,
                "rb_allocation",
                LTERBAllocation,
            )
        else:
            self.band = _coerce_enum_value(self.band, "band", NRBand)
            self.rb_allocation = _coerce_enum_value(
                self.rb_allocation,
                "rb_allocation",
                RBAllocation,
            )
        self.bandwidth = _coerce_bandwidth_value(self.bandwidth)
        self.test_type = _coerce_enum_value(self.test_type, "test_type", TestType)
        self.modulation = _coerce_enum_value(
            self.modulation,
            "modulation",
            Modulation,
        )
        self.dut_ant_position = _coerce_enum_value(
            self.dut_ant_position,
            "dut_ant_position",
            DUTAntPosition,
        )
        self.test_channel = _coerce_enum_value(
            self.test_channel,
            "test_channel",
            TestChannel,
        )
        if self.generation is Generation.LTE:
            if self.modulation is not Modulation.QPSK:
                raise ValueError("LTE modulation must be QPSK")
            resolve_lte_range_id(self.band, self.test_type)
            validate_lte_supported_bandwidth(self.band, self.bandwidth)
            resolve_arfcn(self.band, self.bandwidth, self.test_channel)
            resolve_lte_rb_parameters(self.bandwidth, self.rb_allocation)
        else:
            resolve_range_id(self.band, self.test_type)
            validate_supported_bandwidth(self.band, self.bandwidth)

    @property
    def rb_size(self) -> int:
        return self.rb_parameters[0]

    @property
    def rb_offset(self) -> int:
        return self.rb_parameters[1]

    @property
    def rb_parameters(self) -> tuple[int, int]:
        if self.generation is Generation.LTE:
            return resolve_lte_rb_parameters(
                bandwidth=self.bandwidth,
                rb_allocation=self.rb_allocation,
            )
        return resolve_rb_parameters(
            band=self.band,
            bandwidth=self.bandwidth,
            rb_allocation=self.rb_allocation,
        )

    @property
    def scs_khz(self) -> int:
        if self.generation is Generation.LTE:
            return find_lte_band_group(self.band).scs_khz
        return find_band_group(self.band).scs_khz

    @property
    def factor_keyword(self) -> str:
        if self.generation is Generation.LTE:
            return find_lte_band_group(self.band).factor_keyword
        return find_band_group(self.band).sa_recall

    @property
    def mt8000_recall(self) -> str:
        if self.generation is Generation.LTE:
            return find_lte_band_group(self.band).mt8000_recall
        group = find_band_group(self.band)
        if self.generation is Generation.NR_NSA:
            return group.mt8000_nsa_recall
        return group.mt8000_sa_recall

    @property
    def turntable_speed(self) -> int:
        if self.generation is Generation.LTE:
            return find_lte_band_group(self.band).turntable_speed
        return find_band_group(self.band).turntable_speed

    @property
    def channel_number(self) -> int:
        if self.generation is Generation.LTE:
            return resolve_arfcn(self.band, self.bandwidth, self.test_channel)
        return resolve_call_channel(self.band, self.bandwidth, self.test_channel)

    @property
    def frequency_mhz(self) -> float:
        if self.generation is Generation.LTE:
            return resolve_lte_frequency_mhz(
                self.band,
                self.bandwidth,
                self.test_channel,
            )
        return resolve_target_frequency_mhz(
            self.band,
            self.bandwidth,
            self.test_channel,
        )

    @property
    def test_range(self) -> RangeId:
        if self.generation is Generation.LTE:
            return resolve_lte_range_id(self.band, self.test_type)
        return resolve_range_id(self.band, self.test_type)

    @property
    def range_name(self) -> str:
        return self.test_range.key

    @property
    def range_definition(self) -> TestRange:
        return get_test_range(self.test_range)

    @classmethod
    def from_csv_row(cls, row: dict[str, Any]) -> "TestCase":
        """검증한 CSV dict 한 행으로부터 TestCase를 생성한다."""

        generation = _parse_enum_value(row, "generation", Generation)
        anchor_band = _parse_optional_enum_value(row, "anchor_band", LTEBand)
        band: NRBand | LTEBand
        rb_allocation: RBAllocation | LTERBAllocation
        if generation is Generation.LTE:
            band = _parse_enum_value(row, "band", LTEBand)
            rb_allocation = _parse_enum_value(
                row,
                "rb_allocation",
                LTERBAllocation,
            )
        else:
            band = _parse_enum_value(row, "band", NRBand)
            rb_allocation = _parse_enum_value(row, "rb_allocation", RBAllocation)
        bandwidth = _parse_bandwidth_value(_get_required_csv_value(row, "bandwidth"))
        test_type = _parse_enum_value(row, "test_type", TestType)
        modulation = _parse_enum_value(row, "modulation", Modulation)
        test_channel = _parse_enum_value(row, "test_channel", TestChannel)
        antenna_pol = _parse_enum_value(row, "antenna_pol", AntennaPol)
        dut_axis = _parse_enum_value(row, "dut_axis", DUTAxis)
        dut_ant_position = _parse_enum_value(
            row,
            "dut_ant_position",
            DUTAntPosition,
        )

        return cls(
            band=band,
            bandwidth=bandwidth,
            test_type=test_type,
            modulation=modulation,
            rb_allocation=rb_allocation,
            test_channel=test_channel,
            antenna_pol=antenna_pol,
            dut_axis=dut_axis,
            dut_ant_position=dut_ant_position,
            generation=generation,
            anchor_band=anchor_band,
        )

    def to_csv_row(self) -> dict[str, Any]:
        """외부 CSV 스키마에 포함되는 필드만 직렬화한다."""

        return {
            "generation": self.generation.value,
            "band": self.band.value,
            "anchor_band": (
                self.anchor_band.value if self.anchor_band is not None else ""
            ),
            "bandwidth": _format_bandwidth_value(self.bandwidth),
            "test_type": self.test_type.value,
            "modulation": self.modulation.value,
            "rb_allocation": self.rb_allocation.value,
            "test_channel": self.test_channel.value,
            "antenna_pol": self.antenna_pol.value,
            "dut_axis": self.dut_axis.value,
            "dut_ant_position": self.dut_ant_position.value,
        }
