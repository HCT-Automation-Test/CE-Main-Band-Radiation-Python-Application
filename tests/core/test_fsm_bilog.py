from __future__ import annotations

import pytest


@pytest.mark.skip(reason="spec TODO: Bilog 측정 명세 확정 후")
def test_bilog_measurement_chain() -> None:
    """NRCallConnect → SetSwitchBox → ... → MeasureBilog → ResetSwitchBox → CheckNextCase 전이 확인."""
    ...


@pytest.mark.skip(reason="spec TODO: Bilog 측정 명세 확정 후")
def test_bilog_test_type_change_from_inband() -> None:
    """In-Band TC 다음에 같은 Band/AntPol/Axis의 Bilog TC가 오면 TestTypeChange 경유 확인."""
    ...
