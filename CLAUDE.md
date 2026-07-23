# Project: CE NR Radiated 측정 자동화 SW (PySide6)

## Project Overview

**CE 규격 NR Radiated 방사 측정 자동화 소프트웨어**. PySide6 기반 데스크톱 앱으로,
시험 오퍼레이터가 Test Case를 관리하고 시퀀스를 실행하며 결과 리포트를 생성하는
**오케스트레이션 + UI + 리포트** 계층을 담당한다.

- **도메인**: NR SA + NSA (구현 완료), 확장: LTE
- **시험 종류**: Harmonic, In-band, Bilog (모두 구현. Bilog는 In-band와 동일 LV 프로토콜 공유)
- **장비 5종**:
  - **MT8000A** — NR Callbox
  - **FSV40** — Spectrum Analyzer
  - **Switch Box** — 입력/필터 경로 선택 (IP/Port 연결)
  - **CO3000** — Turntable (DUT 회전) + 3m/Bilog Mast 편파
  - **3D Controller** — 1m Mast 편파 제어
- **VISA 직접 제어는 외부 LabVIEW 프로그램의 책임**. 이 Python 앱은 장비 제어를 위해
  VISA 세션을 직접 열거나 SCPI/장비 명령을 직접 전송하지 않는다.
- 장비 연결, 설정, 측정, 상태 확인은 외부 프로그램과
  **TCP 기반 자체 JSON 프로토콜 (Request/Response + 비동기 Event)**로만 수행한다.
- 예외적으로 UI 입력 편의를 위한 로컬 VISA Resource 주소 목록 조회는 허용한다.

## Python 책임 범위

1. CSV Test Case 로드 / 편집 / 검증 (Range 매핑은 `TestCase` 파생 프로퍼티가 수행)
2. 코드 상수 기반 TestRange(SA·SwitchBox 파라미터 묶음) 정의 및 매핑
3. **통합 세션 FSM 실행** (QThread + 명시적 State 클래스, 시험 간 전환 포함)
4. 외부 프로그램과 TCP/JSON으로 명령 송신 및 결과 수신
5. Excel 템플릿에 결과 매핑(라이브 모니터링 포함) + SA 스크린샷 저장
6. UI: 장비 연결/Set / TC 관리 / 실행 모니터링 / RF Switch Box 수동 제어 / 스크린샷 뷰어 / 로그

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
├── pyproject.toml               # 버전(src/app/__init__.py와 수동 동기화), 의존성, pytest 설정
├── README.md / CLAUDE.md / AGENTS.md
├── CE_NR_Radiated.spec          # PyInstaller 스펙 (산출물: CE_MainBand_Radiation)
├── docs/                        # 프로젝트 스펙/아키텍처/심화 문서
├── resources/
│   ├── main_window.ui           # 최소 골격 (실제 화면은 main_window.py가 코드로 조립)
│   ├── icons/
│   └── images/rf_switch_box_bd.png
├── testcases/samples/harmonic_sample.csv
├── config/
│   ├── app_config.example.json            # AppConfig 예시 (현재 로드하는 코드 없음 — 휴면)
│   ├── instrument_connection.example.json # 장비 연결 입력 영속화 스키마
│   └── excel_template_map.example.json    # 레거시 (실 매핑은 report/template_map.py 코드 상수)
├── src/app/
│   ├── __main__.py              # QApplication 부트스트랩
│   ├── logging_setup.py
│   ├── config/
│   │   ├── app_config.py                     # 휴면 코드
│   │   └── instrument_connection_settings.py # config/instrument_connection.json 로드/저장
│   ├── models/                  # enums, test_case, test_range, band_group,
│   │                            # nr_channel_lookup, rb_parameters, supported_bandwidths,
│   │                            # switch_box, measurement_result, test_run_settings
│   ├── core/
│   │   ├── tc_loader.py / tc_validator.py
│   │   ├── runner.py            # QObject + QThread runner (세션 컨트롤러)
│   │   ├── events.py            # RunnerEvents (Qt signals)
│   │   ├── instrument_connection.py # 장비 연결/Set 비동기 서비스
│   │   ├── instrument_set.py    # Set 완료/에러 Event 대기 유틸
│   │   ├── tdf_service.py       # FSV40 TDF 비동기 서비스
│   │   └── fsm/
│   │       ├── base.py          # State ABC, StateResult
│   │       ├── context.py       # SessionContext
│   │       ├── engine.py        # FSM 전이 엔진 + build_session_engine
│   │       ├── call_routing.py  # SA/NSA Call/Handover 진입 상태 결정
│   │       ├── equipment.py     # 장비 연결 여부 판정
│   │       ├── transition_flow.py # 복합 전환 체이닝(next_transition_or)
│   │       └── states/
│   │           ├── session.py       # SessionInit, Idle, CheckNextCase, TestEnd
│   │           ├── nr_setup.py      # LTECallAnchor, NRCallConnect, NRCallDisconnected
│   │           ├── transition.py    # AntPol/Handover/Recall/DUTAxis/TestType Change
│   │           └── measurement/
│   │               ├── common.py    # 공유 스텝(SwitchBox/SA/Turntable) + test_type 분기 허브
│   │               ├── harmonic.py  # Fundamental/Harmonics/Precision
│   │               ├── inband.py / bilog.py  # Bilog는 In-band LV 프로토콜 공유
│   │               ├── manual_marker.py      # 수동 마커 모드 헬퍼
│   │               └── reporting.py          # ReportWriter 호출 단일 관문
│   ├── net/
│   │   ├── protocol.py          # Request/Response/Event dataclass + 프레이밍
│   │   ├── tcp_client.py        # QTcpSocket 래퍼 (전용 QThread)
│   │   ├── commands.py          # FSM이 호출하는 고수준 facade (명령 스키마의 단일 진실)
│   │   ├── lv_server_process.py # LV Inst Manager.exe 기동/종료 (frozen 실행 시)
│   │   ├── mock_server.py       # loopback 테스트용 저수준 스텁
│   │   ├── mock_lv_server.py    # 모의 LabVIEW 서버 (CLI 실행 가능)
│   │   └── mock_lv_client.py    # facade 수동 검증 콘솔
│   ├── report/
│   │   ├── report_writer.py     # FSM이 부르는 facade
│   │   ├── excel_writer.py      # openpyxl + COM 라이브 모니터링
│   │   ├── template_map.py      # 시트/셀 좌표 규칙 (코드 상수)
│   │   └── screenshot_store.py
│   └── ui/
│       ├── main_window.py       # 패널 조립 + 시그널 결선 허브 + 잠금 정책
│       ├── instrument_check_panel.py
│       ├── test_manager_panel.py
│       ├── nr_select.py         # NR TestCase 생성 다이얼로그
│       ├── rf_filter_box_panel.py
│       ├── test_plot_screenshot_panel.py
│       ├── manual_test_panel.py # placeholder (TODO(spec))
│       ├── manual_marker_dialog.py
│       ├── instrument_set_progress_dialog.py
│       ├── log_panel.py
│       └── generated/           # pyside6-uic 산출물 (편집 금지)
└── tests/                       # models / core / net / report / ui
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
- 복합 변경(Band+AntPol 동시 등)은 `CheckNextCase`가 diff 기반으로 전환 상태 리스트를
  만들고(순서: Recall/Handover → DUTAxis → AntPol → TestType), 나머지를
  `pending_transition_states` 큐로 체이닝 (`transition_flow.next_transition_or`)

**시험 타입 분기 (InBand/Bilog 구현 완료):**

- 측정 구간(states/measurement/)만 test type별로 분기 —
  분기 허브는 `common.measurement_start_state_for(test_type, after_rotate, manual_marker)`
- NRCallConnect 출구 및 CheckNextCase 복귀 지점에서 이 허브를 경유
- InBand/Bilog는 Fundamental/Precision 단계 없이 공유 스텝
  (SetSwitchBox→SetupSA→RotateTurntable) 후 단일 측정
- Bilog는 LV 프로토콜 수준에서 In-band와 동일 명령 사용
  (`measure_bilog`는 `measure_inband`에 위임, 스크린샷도 `inband.png`)

## 새 시험 타입 추가 절차

1. `src/app/models/enums.py`의 `TestType`에 항목 추가 +
   `band_group.RANGE_BY_BAND_TEST`에 band별 매핑 + `measurement_result.py`에 결과 dataclass
2. `src/app/core/fsm/states/measurement/<type>.py` 모듈 생성 (inband.py가 최소 템플릿)
3. `common.measurement_start_state_for()`의 매핑 3개(진입/회전후/회전후+수동)에 항목 추가
4. `src/app/core/fsm/engine.py`의 `build_session_engine()`에 상태 register
5. `src/app/net/commands.py`에 facade 함수 추가 (+ `mock_lv_server.py` 핸들러)
6. `report/template_map.py` 레이아웃·좌표 함수 + `excel_writer.py`/`report_writer.py`에
   `write_<type>` 추가
7. `ui/nr_select.py`의 `_test_range_options_for_group`에 라벨↔TestType 매핑 추가
8. 테스트: `tests/core/test_fsm_<type>.py`(harmonic 하네스 재사용),
   `test_fsm_routing.py` 분기, `tests/net/test_commands.py` 계약

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

- **models**: 순수 Python 단위 테스트. Range/lookup 수치를 리터럴로 고정.
- **core (FSM)**: duck-typed 가짜(commands/events/client/writer)를 SessionContext에 주입해
  상태 전이·호출 순서 검증. `test_fsm_harmonic.py`가 공용 하네스.
  단, `test_runner`/`test_tdf_service`/`test_instrument_connection`은 `pytest-qt` 필요.
- **net**: `mock_server`/`mock_lv_server` 기반 실제 TCP loopback (port=0).
  `test_commands.py`가 LV 명령 계약을 리터럴로 고정.
- **report**: 실제 openpyxl 워크북 + COM fake.
- **ui**: `pytest-qt`(qtbot) + `findChild(objectName)` 스캐폴드 검증.
- **통합**: loopback 테스트만 CI 대상. 실기 외부 서버 대상 테스트는 사용자 승인 필요.

## Related Docs

- 프로젝트 스펙: `docs/PROJECT_SPEC_1.0.1.md` (메인), `docs/ARCHITECTURE.md` (개요)
- 심화: `docs/FSM.md`, `docs/PROTOCOL.md`, `docs/DOMAIN_MODELS.md`,
  `docs/REPORTING.md`, `docs/UI_GUIDE.md`
- 스킬: `.claude/skills/pyside-widget/SKILL.md`
- 서브에이전트: `.claude/agents/ui-reviewer.md`, `.claude/agents/test-writer.md`
