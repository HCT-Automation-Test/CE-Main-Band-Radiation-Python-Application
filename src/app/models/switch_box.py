"""Switch Box label parsing and filter resolution helpers."""
from __future__ import annotations

from app.models.enums import FilterMode, FilterPath, InputPath

_INPUT_PATH_BY_LABEL = {
    "Input1": InputPath.INPUT1,
    "Input2": InputPath.INPUT2,
    "Input3": InputPath.INPUT3,
}

_FILTER_MODE_BY_LABEL = {
    "BRF": FilterMode.BRF,
    "1G HPF": FilterMode.HPF_1G,
    "3G HPF": FilterMode.HPF_3G,
    "6G HPF": FilterMode.HPF_6G,
}

_FILTER_PATH_BY_MODE = {
    FilterMode.HPF_1G: FilterPath.HPF_1G,
    FilterMode.HPF_3G: FilterPath.HPF_3G,
    FilterMode.HPF_6G: FilterPath.HPF_6G,
}

_INPUT_PATH_DISPLAY_LABELS = {
    InputPath.INPUT1: "Bilog",
    InputPath.INPUT2: "3m",
    InputPath.INPUT3: "1m",
}

_FILTER_PATH_DISPLAY_LABELS = {
    FilterPath.THRU: "THRU",
    FilterPath.DIRECT_AMP: "Direct Amp",
    FilterPath.HPF_1G: "1G HPF",
    FilterPath.HPF_3G: "3G HPF",
    FilterPath.HPF_7G: "7G HPF",
    FilterPath.HPF_6G: "6G HPF",
}

_BRF_FILTER_PATH_BY_BAND = {
    band: FilterPath[f"PORT_{index}"]
    for index, band in enumerate((1, 3, 5, 7, 8, 20, 26, 28, 38, 40, 41, 71, 77, 78, 79), start=1)
}


def parse_input_path(label: str) -> InputPath:
    try:
        return _INPUT_PATH_BY_LABEL[label]
    except KeyError as exc:
        raise ValueError(f"Unknown input path label: {label!r}") from exc


def parse_filter_mode(label: str) -> FilterMode:
    try:
        return _FILTER_MODE_BY_LABEL[label]
    except KeyError as exc:
        raise ValueError(f"Unknown filter mode label: {label!r}") from exc


def display_input_path(input_path: InputPath) -> str:
    try:
        return _INPUT_PATH_DISPLAY_LABELS[input_path]
    except KeyError as exc:
        raise ValueError(f"Unknown input path: {input_path!r}") from exc


def display_filter_path(filter_path: FilterPath) -> str:
    if filter_path.name.startswith("PORT_"):
        return f"Port {filter_path.name.removeprefix('PORT_')}"
    try:
        return _FILTER_PATH_DISPLAY_LABELS[filter_path]
    except KeyError as exc:
        raise ValueError(f"Unknown filter path: {filter_path!r}") from exc


def resolve_filter_path(filter_mode: FilterMode, band: str) -> FilterPath:
    if filter_mode is FilterMode.BRF:
        return resolve_brf_filter_path(band)
    return _FILTER_PATH_BY_MODE[filter_mode]


def resolve_brf_filter_path(band: str) -> FilterPath:
    band_number = parse_band_number(band)
    try:
        return _BRF_FILTER_PATH_BY_BAND[band_number]
    except KeyError as exc:
        raise ValueError(f"Unsupported BRF band: {band!r}") from exc


def parse_band_number(band: str) -> int:
    if not isinstance(band, str):
        raise ValueError(f"Band must be a string, got {type(band).__name__}")

    normalized = band.strip()
    if normalized.lower().startswith("n"):
        normalized = normalized[1:]

    try:
        return int(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid band format: {band!r}") from exc
