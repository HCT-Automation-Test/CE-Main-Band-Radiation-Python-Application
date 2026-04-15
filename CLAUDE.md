# Project: CE NR Radiated 측정 자동화 SW (PySide6)

## Project Overview

**CE 규격 NR Radiated 방사 측정 자동화 소프트웨어**. PySide6 기반 데스크톱 앱으로,
시험 오퍼레이터가 Test Case를 관리하고 시퀀스를 실행하며 결과 리포트를 생성하는
**오케스트레이션 + UI + 리포트** 계층을 담당한다.

- **도메인**: NR SA (MVP), 확장: NSA / LTE
- **시험 종류**: Harmonic, In-band, Bilog (Harmonic이 우선 명세 확정)
- **장비 4종**:
  - **MT8000A** — NR Callbox
  - **FSV40** — Spectrum Analyzer
  - **Switch Box** — 입력/필터 경로 선택
  - **CO3000** — Turntable (DUT 회전)
- **VISA 직접 제어는 외부 LabVIEW 프로그램의 책임**. 이 Python 앱은 VISA를 일체 사용하지 않으며,
  외부 프로그램과는 **TCP 기반 자체 JSON 프로토콜 (Request/Response + 비동기 Event)**로 파라미터/결과만 교환한다.

## Python 책임 범위

1. CSV Test Case 로드 / 편집 / Range 확장
2. 코드 상수 기반 TestRange(SA·SwitchBox 파라미터 묶음) 정의 및 매핑
3. **FSM 기반 시퀀스 실행** (QThread + 명시적 State 클래스)
4. 외부 프로그램과 TCP/JSON으로 명령 송신 및 결과 수신
5. Excel 템플릿에 결과 매핑 + SA 스크린샷 저장
6. UI: 장비 상태 / TC 편집 / 실행 모니터링 / 스크린샷 뷰어 / 로그

## Tech Stack

- **Python**: 3.11+
- **UI**: PySide6 (`QTcpSocket`, `QThread`)
- **Package manager**: uv (pyproject.toml)
- **Excel**: openpyxl
- **YAML/JSON**: PyYAML + 표준 json
- **Test**: pytest, pytest-qt

## Directory Layout

```
claude_test/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── resources/
│   ├── main_window.ui
│   └── icons/
├── testcases/
│   ├── samples/harmonic_sample.csv
├── config/
│   ├── app_config.example.json
│   └── excel_template_map.example.json
├── src/app/
│   ├── __main__.py              # QApplication 부트스트랩
│   ├── logging_setup.py
│   ├── config/app_config.py
│   ├── models/                  # enums, test_case, test_range, measurement_result
│   ├── core/
│   │   ├── tc_loader.py
│   │   ├── tc_validator.py
│   │   ├── runner.py            # QObject + QThread runner
│   │   ├── events.py            # RunnerEvents (Qt signals)
│   │   └── fsm/
│   │       ├── base.py          # State ABC, StateResult
│   │       ├── context.py
│   │       ├── registry.py      # TestType → Sequence 매핑
│   │       ├── harmonic/        # states.py, sequence.py (§4 8단계)
│   │       ├── inband/          # TODO(spec)
│   │       └── bilog/           # TODO(spec)
│   ├── net/
│   │   ├── protocol.py          # Request/Response/Event dataclass
│   │   ├── tcp_client.py        # QTcpSocket 래퍼
│   │   ├── commands.py          # FSM이 호출하는 고수준 facade
│   │   └── mock_server.py       # loopback 테스트용
│   ├── report/
│   │   ├── excel_writer.py
│   │   ├── template_loader.py
│   │   └── screenshot_store.py
│   └── ui/
│       ├── main_window.py
│       ├── device_status_panel.py
│       ├── tc_editor.py
│       ├── execution_panel.py
│       ├── screenshot_viewer.py
│       ├── log_panel.py
│       └── generated/           # pyside6-uic 산출물 (편집 금지)
└── tests/
```

## Build / Run / Test

```bash
# 의존성 설치
uv sync

# .ui 컴파일 (UI 변경 시)
uv run pyside6-uic resources/main_window.ui -o src/app/ui/generated/main_window_ui.py

# 앱 실행
uv run python -m app

# 테스트
uv run pytest -q
uv run pytest tests/core -k harmonic
```

## Coding Rules

- **레이어 분리**: `ui → core → (net | report)` 단방향. `net`/`report`는 `ui`에 의존하지 않는다.
  `core`는 UI 알림 전달을 위해 `QObject`/시그널 사용 허용.
- **이벤트 루프 차단 금지**: TCP 송수신·파일 I/O는 `QThread` 또는 `QTcpSocket` 비동기 시그널로 분리.
- **생성 파일**: `.ui` → `*_ui.py`는 `src/app/ui/generated/`에만 두고 **직접 편집 금지**.
  로직은 상속/컴포지션 클래스(`src/app/ui/main_window.py` 등)에 작성.
- **경로**: 항상 `pathlib.Path`. 파일 I/O에는 `encoding="utf-8"` 명시.
- **시그널/슬롯 네이밍**: 시그널 `something_changed`, 슬롯 `on_something_changed`.
- **로깅**: `print` 금지. `logging` 모듈 사용. UI에는 `QPlainTextEdit` 미러 핸들러.
- **Spec TODO 규약**: 명세 미확정 지점은 일관된 `# TODO(spec): ...` 주석으로 표시.

## 새 시험 타입 추가 절차

1. `src/app/core/fsm/<type>/` 모듈 생성 (`states.py`, `sequence.py`)
2. `src/app/core/fsm/registry.py`의 `SEQUENCES`에 등록
3. `src/app/net/commands.py`에 필요한 facade 함수 추가
4. `src/app/models/enums.py`의 `TestType` enum에 항목 추가
5. 해당 타입 테스트를 `tests/core/test_fsm_<type>.py`에 작성

## Forbidden / Requires Approval

- `src/app/ui/generated/**` 파일 직접 편집 금지 (재생성으로 덮어쓰기).
- **Python에서 VISA 직접 호출 금지**. 장비 제어는 전적으로 외부 LabVIEW 프로그램 책임.
- **실기 외부 서버 대상 통합 테스트 실행은 사용자 명시 승인 필요** (호스트/포트 포함).
  기본 테스트는 `mock_server` 또는 loopback으로 수행.
- 의존성 추가/제거는 `uv add` / `uv remove` 사용. `pyproject.toml` 직접 편집 지양.

## Test Strategy

- **core / net / report**: 순수 Python 단위 테스트 (`pytest`). Qt 의존 최소화.
- **models / ui**: Qt 의존 부분은 `pytest-qt`로 신호/모델 상태 검증.
- **통합**: `net/mock_server.py` 기반 loopback 테스트만 CI 대상.

## Related Docs

- 플랜: `C:\Users\HCT-3320\.claude\plans\compressed-stargazing-squirrel.md`
- 스킬: `.claude/skills/pyside-widget/SKILL.md`
- 서브에이전트: `.claude/agents/ui-reviewer.md`, `.claude/agents/test-writer.md`
