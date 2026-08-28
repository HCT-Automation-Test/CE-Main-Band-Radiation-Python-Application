from __future__ import annotations

from app.config.app_config import AppConfig


def test_app_config_loads_without_excel_template_path(tmp_path) -> None:
    config_path = tmp_path / "app_config.json"
    config_path.write_text(
        '{"tcp_host": "127.0.0.1", "tcp_port": 5025, "tcp_timeout_s": 3}',
        encoding="utf-8",
    )

    config = AppConfig.load(config_path)

    assert config.tcp_host == "127.0.0.1"
    assert config.tcp_port == 5025
    assert config.tcp_timeout_s == 3
    assert not hasattr(config, "excel_template_path")
