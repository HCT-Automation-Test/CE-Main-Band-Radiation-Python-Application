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
- **VISA 직접 제어는 외부 LabVIEW 프로그램의 책임**. 이 Python 앱은 장비 제어를 위해
  VISA 세션을 직접 열거나 SCPI/장비 명령을 직접 전송하지 않는다.
- 장비 연결, 설정, 측정, 상태 확인은 외부 프로그램과
  **TCP 기반 자체 JSON 프로토콜 (Request/Response + 비동기 Event)**로만 수행한다.
- 예외적으로 UI 입력 편의를 위한 로컬 VISA Resource 주소 목록 조회는 허용한다.

## Python 책임 범위

1. CSV Test Case 로드 / 편집 / Range 확장
2. 코드 상수 기반 TestRange(SA·SwitchBox 파라미터 묶음) 정의 및 매핑
3. **통합 세션 FSM 실행** (QThread + 명시적 State 클래스, 시험 간 전환 포함)
4. 외부 프로그램과 TCP/JSON으로 명령 송신 및 결과 수신
5. Excel 템플릿에 결과 매핑 + SA 스크린샷 저장
6. UI: 장비 상태 / TC 편집 / 실행 모니터링 / 스크린샷 뷰어 / 로그

## Tech Stack

- **Python**: 3.11+
- **UI**: PySide6 (`QTcpSocket`, `QThread`)
- **Package manager**: uv (pyproject.toml)
- **VISA Resource 목록 조회**: pyvisa (`ResourceManager().list_resources()` 용도에 한정)
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
│   │       ├── context.py       # SessionContext
│   │       ├── engine.py        # FSM 전이 엔진
│   │       └── states/
│   │           ├── session.py       # Init, Idle, CheckNextCase, TestEnd
│   │           ├── nr_setup.py      # NRCallConnect, NRCallDisconnected
│   │           ├── transition.py    # AntPolChange, Handover, RecallChange, DUTAxisChange
│   │           └── measurement/
│   │               ├── harmonic.py  # Harmonic 측정 State들 (4~9)
│   │               ├── inband.py    # TODO(spec)
│   │               └── bilog.py     # TODO(spec)
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

## 통합 세션 FSM 설계

세션 전체를 하나의 FSM으로 모델링. 시험 간 전환(Handover, AntPol 변경 등)이 FSM 상태로 존재.

**상태 흐름:**
`Init → Idle → NRCallConnect → [Measurement(test type별)] → CheckNextCase → (전환 상태) → loop | TestEnd → Idle`

**전환 상태:** AntPolChange, Handover, RecallChange, DUTAxisChange, NRCallDisconnected

**설계 원칙:**

- 각 State는 `next_state()`로 다음 상태를 결정 (고정 리스트 순차 실행이 아님)
- NRCallConnect 진입 시 항상 풀 Setup + 신규 연결
- 같은 Band 내 파라미터(BW/Mod/RB/Channel)는 Band에 종속 — 별도 전환 불필요
- 복합 변경(Band+AntPol 동시 등) 우선순위 규칙은 추후 협의 예정

**시험 타입 확장 (InBand/Bilog):**

- 측정 구간(states/measurement/)만 test type별로 분기
- NRCallConnect 출구 및 CheckNextCase 복귀 지점에서 test_type 기반 분기
- InBand/Bilog는 Harmonic과 상태 재활용 많을 예정
- InBand/Bilog는 시험 간 전환 상태(AntPol/Handover/DUTAxis)가 없이 연속 진행 다수

## 새 시험 타입 추가 절차

1. `src/app/core/fsm/states/measurement/<type>.py` 모듈 생성
2. `src/app/core/fsm/engine.py`에 test_type 분기 전이 규칙 등록
3. `src/app/net/commands.py`에 필요한 facade 함수 추가
4. `src/app/models/enums.py`의 `TestType` enum에 항목 추가
5. 해당 타입 테스트를 `tests/core/test_fsm_<type>.py`에 작성

## Forbidden / Requires Approval

- `src/app/ui/generated/**` 파일 직접 편집 금지 (재생성으로 덮어쓰기).
- **Python에서 장비 제어 목적의 VISA 직접 호출 금지**. 장비 제어는 전적으로 외부 LabVIEW 프로그램 책임.
  - 허용: `pyvisa.ResourceManager().list_resources()` 수준의 로컬 VISA Resource 주소 목록 조회.
  - 금지: `open_resource`, `write`, `read`, `query`, 장비 세션 유지, SCPI 전송, 측정/설정/상태 확인.
  - 조회된 VISA 주소는 LabVIEW TCP 명령의 설정값으로 전달하는 용도에만 사용한다.
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
