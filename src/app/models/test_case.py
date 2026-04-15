"""Test Case 데이터 모델 (§3.3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.band_group import find_band_group
from app.models.enums import AntennaPol, DUTAxis, Modulation, RBAllocation
from app.models.rb_parameters import resolve_rb_parameters


@dataclass
class TestCase:
    """CSV 한 행에 대응하는 Test Case.

    TODO(spec): 필드 이름/타입/기본값은 명세 §3.3 확정 후 재정비.
    """

    band: str
    bandwidth: str
    modulation: Modulation
    rb_allocation: RBAllocation
    test_channel: str
    range_name: str
    antenna_pol: AntennaPol
    dut_axis: DUTAxis

    @property
    def rb_size(self) -> int:
        return self.rb_parameters[0]

    @property
    def rb_offset(self) -> int:
        return self.rb_parameters[1]

    @property
    def rb_parameters(self) -> tuple[int, int]:
        return resolve_rb_parameters(
            band=self.band,
            bandwidth=self.bandwidth,
            rb_allocation=self.rb_allocation,
        )

    @property
    def scs_khz(self) -> int:
        return find_band_group(self.band).scs_khz

    @classmethod
    def from_csv_row(cls, row: dict[str, Any]) -> "TestCase":
        """CSV dict row에서 인스턴스 생성."""
        # TODO(spec): 파싱/정규화 규칙 확정
        raise NotImplementedError("spec TODO")

    def to_csv_row(self) -> dict[str, Any]:
        """CSV dict row로 직렬화."""
        # TODO(spec): 직렬화 형식 확정
        raise NotImplementedError("spec TODO")
