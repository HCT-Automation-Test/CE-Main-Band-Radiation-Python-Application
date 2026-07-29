from __future__ import annotations

import pytest

from app.models.enums import LTERBAllocation
from app.models.lte_rb_parameters import resolve_lte_rb_parameters

EXPECTED_OFFSETS = {
    1.4: (0, 3, 5),
    3.0: (0, 7, 14),
    5.0: (0, 12, 24),
    10.0: (0, 24, 49),
    15.0: (0, 36, 74),
    20.0: (0, 49, 99),
}


def test_lte_rb_table_matches_all_18_final_rows() -> None:
    checked_rows = 0

    for bandwidth, offsets in EXPECTED_OFFSETS.items():
        for index, allocation in enumerate(LTERBAllocation):
            assert resolve_lte_rb_parameters(bandwidth, allocation) == (
                1,
                offsets[index],
            )
            checked_rows += 1

    assert checked_rows == 18


def test_lte_rb_lookup_rejects_unsupported_bandwidth() -> None:
    with pytest.raises(ValueError, match="Unsupported LTE RB allocation mapping"):
        resolve_lte_rb_parameters(25.0, LTERBAllocation.MID)
