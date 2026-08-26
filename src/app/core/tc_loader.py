"""Test Case CSV 로드/세이브 헬퍼."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from app.core.tc_validator import validate
from app.models.test_case import CSV_FIELDNAMES, TestCase

_LEGACY_CSV_FIELDNAMES: tuple[str, ...] = tuple(
    field_name for field_name in CSV_FIELDNAMES if field_name != "anchor_band"
)


def _validate_header(fieldnames: list[str] | None) -> bool:
    """CSV header를 검증하고 기존 10열 스키마 여부를 반환한다."""

    if fieldnames is None:
        raise ValueError("CSV header is missing")

    actual_fieldnames = [field.strip() for field in fieldnames]
    expected_fieldnames = list(CSV_FIELDNAMES)
    if actual_fieldnames == expected_fieldnames:
        return False
    if actual_fieldnames == list(_LEGACY_CSV_FIELDNAMES):
        return True

    message_parts = [
        "CSV header mismatch: "
        f"expected {expected_fieldnames!r} or legacy "
        f"{list(_LEGACY_CSV_FIELDNAMES)!r}, got {actual_fieldnames!r}"
    ]
    missing_columns = [
        field_name
        for field_name in expected_fieldnames
        if field_name not in actual_fieldnames
    ]
    unexpected_columns = [
        field_name
        for field_name in actual_fieldnames
        if field_name not in expected_fieldnames
    ]
    if missing_columns:
        message_parts.append(f"missing required columns: {missing_columns!r}")
    if unexpected_columns:
        message_parts.append(f"unexpected columns: {unexpected_columns!r}")
    raise ValueError("; ".join(message_parts))


def load_csv(path: Path) -> list[TestCase]:
    """CSV 파일에서 TestCase 목록을 읽어온다."""

    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        is_legacy_schema = _validate_header(reader.fieldnames)

        cases: list[TestCase] = []
        for row_number, row in enumerate(reader, start=2):
            extra_values = row.get(None)
            if extra_values:
                raise ValueError(
                    f"CSV row {row_number} has unexpected extra values: {extra_values!r}"
                )

            if all(
                value is None or str(value).strip() == ""
                for field_name, value in row.items()
                if field_name is not None
            ):
                continue

            if (
                is_legacy_schema
                and str(row.get("generation", "")).strip().upper() == "NR_NSA"
            ):
                raise ValueError(
                    f"Invalid CSV row {row_number}: legacy 10-column NR_NSA CSV "
                    "requires anchor_band migration"
                )

            try:
                cases.append(TestCase.from_csv_row(row))
            except ValueError as exc:
                raise ValueError(f"Invalid CSV row {row_number}: {exc}") from exc

        return cases


def save_csv(path: Path, cases: Iterable[TestCase]) -> None:
    """고정된 외부 CSV 스키마로 TestCase 목록을 저장한다."""

    case_list = list(cases)
    for row_number, case in enumerate(case_list, start=2):
        errors = validate(case)
        if errors:
            raise ValueError(f"Invalid CSV row {row_number}: {errors[0]}")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(CSV_FIELDNAMES),
            lineterminator="\n",
        )
        writer.writeheader()
        for case in case_list:
            writer.writerow(case.to_csv_row())
