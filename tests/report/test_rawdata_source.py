from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.models.enums import Generation
from app.report.rawdata_source import (
    RawDataSourceError,
    RawDataWorkbookKind,
    expected_sheet_names,
    resolve_rawdata_source,
    runtime_resource_root,
    validate_rawdata_workbook,
    workbook_kind_for_generation,
)

_NR_SOURCE_NAME = "NR_Rawdata_.xlsx"
_LTE_SOURCE_NAME = "_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx"
_NR_SHA256 = "25dedf6246bb47006028e7c71113d5e5db9ab3604ed0ca7b0f618308e74331cb"
_LTE_SHA256 = "48a5aa7c11123318e82a648b35b5e81a7eed9891db0457af4f9b2c73c35c900d"


@pytest.mark.parametrize("generation", [Generation.NR_SA, Generation.NR_NSA])
def test_nr_generation_uses_nr_workbook(generation: Generation) -> None:
    assert workbook_kind_for_generation(generation) is RawDataWorkbookKind.NR


def test_lte_generation_uses_lte_workbook() -> None:
    assert workbook_kind_for_generation(Generation.LTE) is RawDataWorkbookKind.LTE


def test_expected_sheet_inventory_matches_supported_bands() -> None:
    assert len(expected_sheet_names(RawDataWorkbookKind.NR)) == 15
    assert len(expected_sheet_names(RawDataWorkbookKind.LTE)) == 11


@pytest.mark.parametrize(
    ("generation", "filename", "expected_kind", "expected_hash"),
    [
        (
            Generation.NR_SA,
            _NR_SOURCE_NAME,
            RawDataWorkbookKind.NR,
            _NR_SHA256,
        ),
        (
            Generation.LTE,
            _LTE_SOURCE_NAME,
            RawDataWorkbookKind.LTE,
            _LTE_SHA256,
        ),
    ],
)
def test_tracked_source_assets_have_expected_inventory_and_checksum(
    generation: Generation,
    filename: str,
    expected_kind: RawDataWorkbookKind,
    expected_hash: str,
) -> None:
    source = resolve_rawdata_source(generation)

    assert source.kind is expected_kind
    assert source.path.name == filename
    assert source.sha256 == expected_hash
    assert expected_sheet_names(expected_kind).issubset(source.sheet_names)


def test_development_lookup_does_not_depend_on_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)

    assert runtime_resource_root() == Path(__file__).resolve().parents[2]
    assert resolve_rawdata_source(Generation.NR_NSA).path.name == _NR_SOURCE_NAME


def test_frozen_lookup_uses_meipass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_root = Path(__file__).resolve().parents[2]
    template_dir = tmp_path / "resources" / "templates"
    template_dir.mkdir(parents=True)
    shutil.copy2(
        source_root / "resources" / "templates" / _NR_SOURCE_NAME,
        template_dir / _NR_SOURCE_NAME,
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    source = resolve_rawdata_source(Generation.NR_SA)

    assert source.path == (template_dir / _NR_SOURCE_NAME).resolve()
    assert source.sha256 == _NR_SHA256


def test_frozen_lookup_fails_without_meipass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    with pytest.raises(RawDataSourceError, match="PyInstaller resource root"):
        runtime_resource_root()


def test_missing_source_fails_without_fallback(tmp_path: Path) -> None:
    with pytest.raises(RawDataSourceError, match="does not exist"):
        resolve_rawdata_source(Generation.LTE, resource_root=tmp_path)


def test_unreadable_workbook_reports_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"not an Excel workbook")

    with pytest.raises(RawDataSourceError, match="unreadable"):
        validate_rawdata_workbook(path, RawDataWorkbookKind.NR)


def test_missing_managed_sheet_is_rejected(tmp_path: Path) -> None:
    expected = sorted(expected_sheet_names(RawDataWorkbookKind.NR))
    path = tmp_path / "missing.xlsx"
    _write_workbook(path, expected[:-1])

    with pytest.raises(RawDataSourceError, match="missing="):
        validate_rawdata_workbook(path, RawDataWorkbookKind.NR)


def test_unexpected_managed_sheet_is_rejected(tmp_path: Path) -> None:
    sheets = sorted(expected_sheet_names(RawDataWorkbookKind.LTE))
    path = tmp_path / "unexpected.xlsx"
    _write_workbook(path, [*sheets, "LTE_BAND 99"])

    with pytest.raises(RawDataSourceError, match="unexpected="):
        validate_rawdata_workbook(path, RawDataWorkbookKind.LTE)


def test_non_managed_lte_sheets_are_allowed(tmp_path: Path) -> None:
    sheets = sorted(expected_sheet_names(RawDataWorkbookKind.LTE))
    path = tmp_path / "shared.xlsx"
    _write_workbook(path, ["WCDMA 1", "WCDMA 5", *sheets])

    actual = validate_rawdata_workbook(path, RawDataWorkbookKind.LTE)

    assert "WCDMA 1" in actual
    assert expected_sheet_names(RawDataWorkbookKind.LTE).issubset(actual)


def _write_workbook(path: Path, sheet_names: list[str]) -> None:
    workbook = Workbook()
    first = workbook.active
    first.title = sheet_names[0]
    for sheet_name in sheet_names[1:]:
        workbook.create_sheet(sheet_name)
    workbook.save(path)
    workbook.close()
