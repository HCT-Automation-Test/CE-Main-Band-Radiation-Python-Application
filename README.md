# CE NR Radiated 측정 자동화 SW

PySide6 기반 CE 규격 NR Radiated 방사 측정 자동화 데스크톱 앱.
Python은 Test Case 관리 / FSM 시퀀스 실행 / 외부 LabVIEW 프로그램과의 TCP-JSON
프로토콜 / Excel 리포트 생성을 담당한다. 장비(MT8000A, FSV40, Switch Box, CO3000)의
VISA 제어는 외부 LabVIEW 프로그램 책임이다.

> Note: 일부 장비 미연결 시 FSM state를 스킵하는 동작은 In-band/Bilog 및 최종 통합 전 검증을 위한 임시 개발 정책이다. 실제 배포에서는 필수 장비 전체 연결 없이는 시험을 진행하지 않는다.

## Build / Run / Test

```bash
uv sync
uv run pyside6-uic resources/main_window.ui -o src/app/ui/generated/main_window_ui.py
uv run python -m app
uv run pytest -q
```

## Docs

- 프로젝트 규칙: [CLAUDE.md](CLAUDE.md)
- 설계 플랜: `C:\Users\HCT-3320\.claude\plans\compressed-stargazing-squirrel.md`
