from __future__ import annotations

import pytest

from app.models.enums import RBAllocation
from app.models.rb_parameters import resolve_rb_parameters


def test_resolve_rb_parameters_returns_inner_full_mapping() -> None:
    assert resolve_rb_parameters("n78", "100MHz", RBAllocation.INNER_FULL) == (135, 67)


def test_resolve_rb_parameters_normalizes_bandwidth_label() -> None:
    assert resolve_rb_parameters("n78", "100 MHz", RBAllocation.INNER_1RB_RIGHT) == (1, 271)


def test_resolve_rb_parameters_rejects_unsupported_combination() -> None:
    with pytest.raises(ValueError, match="Unsupported RB allocation mapping"):
        resolve_rb_parameters("n1", "60MHz", RBAllocation.INNER_FULL)
