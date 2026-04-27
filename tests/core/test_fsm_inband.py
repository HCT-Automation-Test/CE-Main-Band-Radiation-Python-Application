from __future__ import annotations

import pytest


@pytest.mark.skip(reason="spec TODO: In-Band 측정 명세 확정 후")
def test_inband_measurement_chain() -> None:
    """NRCallConnect → SetSwitchBox → ... → MeasureInBand → ResetSwitchBox → CheckNextCase 전이 확인."""
    ...


@pytest.mark.skip(reason="spec TODO: In-Band 측정 명세 확정 후")
def test_inband_test_type_change_from_harmonic() -> None:
    """Harmonic TC 다음에 같은 Band/AntPol/Axis의 In-Band TC가 오면 TestTypeChange 경유 확인."""
    ...
