"""pytest 공유 fixture."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest


_TESTS_DIR = Path(__file__).resolve().parent
_UI_TESTS_DIR = _TESTS_DIR / "ui"
_QT_RUNTIME_MODULES = {
    _TESTS_DIR / "core" / "test_instrument_connection.py",
    _TESTS_DIR / "core" / "test_runner.py",
    _TESTS_DIR / "core" / "test_tdf_service.py",
    _TESTS_DIR / "net" / "test_mock_lv_client.py",
    _TESTS_DIR / "net" / "test_mock_lv_server.py",
    _TESTS_DIR / "net" / "test_tcp_client_loopback.py",
}
_NATIVE_DESKTOP_MODULES = {
    _TESTS_DIR / "net" / "test_lv_server_process.py",
}
_QT_FIXTURES = {"qapp", "qtbot"}
_QUARANTINE_REASON = (
    "Qt/QThread/native desktop 테스트는 안전을 위해 기본 실행에서 격리됩니다. "
    "사용자의 명시적 승인 후 --run-quarantined를 사용하세요."
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """격리 테스트의 명시적 opt-in 옵션을 등록한다."""
    parser.addoption(
        "--run-quarantined",
        action="store_true",
        default=False,
        help="Qt/QThread/native desktop 격리 테스트를 실행합니다.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """opt-in 실행에서만 Qt를 offscreen 플랫폼으로 고정한다."""
    if config.getoption("--run-quarantined"):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"


def _is_ui_test(path: Path) -> bool:
    try:
        path.relative_to(_UI_TESTS_DIR)
    except ValueError:
        return False
    return True


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Qt/native 테스트를 중앙에서 분류하고 기본 실행을 차단한다."""
    run_quarantined = config.getoption("--run-quarantined")

    for item in items:
        path = Path(str(item.path)).resolve()
        fixture_names = set(getattr(item, "fixturenames", ()))

        if (
            _is_ui_test(path)
            or path in _QT_RUNTIME_MODULES
            or bool(_QT_FIXTURES & fixture_names)
        ):
            item.add_marker("qt_runtime")

        if path in _NATIVE_DESKTOP_MODULES:
            item.add_marker("native_desktop")

        if item.get_closest_marker("qt_runtime") or item.get_closest_marker(
            "native_desktop"
        ):
            item.add_marker("quarantined")

        if not run_quarantined and item.get_closest_marker("quarantined"):
            item.add_marker(pytest.mark.skip(reason=_QUARANTINE_REASON))


@pytest.hookimpl(tryfirst=True)
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef,
    request: pytest.FixtureRequest,
) -> None:
    """동적으로 qapp/qtbot fixture를 얻는 테스트도 기본 실행에서 차단한다."""

    if fixturedef.argname not in _QT_FIXTURES:
        return None

    request.node.add_marker("qt_runtime")
    request.node.add_marker("quarantined")
    if not request.config.getoption("--run-quarantined"):
        pytest.skip(_QUARANTINE_REASON)
    return None


@pytest.fixture
def placeholder_fixture() -> None:
    """TODO(spec): 공용 픽스처 추가."""
    return None


@pytest.fixture
def tmp_path() -> Path:
    """Windows sandbox에서 pytest 기본 0o700 temp dir 생성을 피한다."""
    root = Path("test-temp")
    root.mkdir(mode=0o777, exist_ok=True)

    path = root / f"t_{uuid.uuid4().hex}"
    path.mkdir(mode=0o777)

    yield path

    shutil.rmtree(path, ignore_errors=True)
