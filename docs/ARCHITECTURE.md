# 아키텍처 개요

CE 규격 NR Radiated 방사 측정 자동화 SW의 전체 구조 문서.
처음 코드를 보는 개발자가 "무엇이 어디에 있고, 서로 어떻게 연결되는지"를 파악하는 출발점이다.

## 1. 시스템 구성

이 저장소의 Python 앱은 **오케스트레이션 + UI + 리포트** 계층이다.
장비의 VISA/SCPI 직접 제어는 전적으로 외부 LabVIEW 프로그램(**LV Inst Manager**)의 책임이며,
Python 앱은 LabVIEW 프로그램과 **TCP 기반 자체 JSON 프로토콜**로만 통신한다.

```text
┌─────────────────────────────┐        TCP/JSON         ┌──────────────────┐   VISA/SCPI   ┌──────────┐
│  Python 앱 (이 저장소)       │ ◄──────────────────────► │  LV Inst Manager │ ◄───────────► │  장비 5종 │
│  PySide6 UI / FSM / Report  │  Request/Response/Event │  (외부 LabVIEW)   │               │          │
└─────────────────────────────┘   127.0.0.1:5025 기본    └──────────────────┘               └──────────┘
```

### 제어 대상 장비 (5종)

| 장비 이름 (프로토콜 target) | 역할 | 연결 방식 |
| --- | --- | --- |
| `MT8000A` | NR/LTE Callbox — Call 연결/Handover | VISA 주소 (LV가 제어) |
| `FSV40` | Spectrum Analyzer — Range 설정/측정/스크린샷 | VISA 주소 |
| `CO3000` | Turntable — DUT 회전, Mast 편파(3m/Bilog) | VISA 주소 |
| `Switch Box` | RF 입력/필터 경로 선택 | IP + Port (raw TCP) |
| `3D Controller` | 1m Mast 편파 제어 | VISA 주소 |

장비 이름 문자열은 [instrument_connection.py](../src/app/core/instrument_connection.py)의
`REQUIRED_EQUIPMENT_NAMES`가 원본이며, 프로토콜 target·`equipment_state` dict 키·UI 상태 표시가
모두 이 문자열(공백 포함)을 그대로 쓴다.

### Python 앱의 책임

1. CSV Test Case 로드/편집/저장 및 검증
2. 코드 상수 기반 도메인 모델(TestRange, Band Group, 채널/RB lookup)
3. **통합 세션 FSM** 실행 (QThread 워커에서 동기 구동, 시험 간 전환 포함)
4. LabVIEW와 TCP/JSON 명령 송신·비동기 Event 수신
5. EUT별 RawData 결과 workbook 기록(라이브 모니터링 포함) + SA 스크린샷 정리 저장
6. UI: 장비 연결/Set, TC 관리, 실행 모니터링, RF Switch Box 수동 제어, 스크린샷 뷰어, 로그

예외적으로 **로컬 VISA Resource 주소 목록 조회**(`pyvisa list_resources()`)만 Python에서 수행하고,
조회된 주소는 LabVIEW에 보내는 Connect 명령의 파라미터로만 사용한다.

## 2. 계층 구조

의존 방향은 `ui → core → (net | report)` 단방향이고, `models`는 어느 계층에서나 임포트하는
최하위 leaf(Qt 미의존 순수 Python)다. `config`도 최하위 유틸이다.

```text
        ┌────────────────────── ui ──────────────────────┐
        │ MainWindow(허브) + 패널/다이얼로그               │
        └───────┬────────────────────────────────────────┘
                │ Runner 생성·소유, RunnerEvents 구독
        ┌───────▼────────────── core ────────────────────┐
        │ Runner(QThread) / RunPreparer / FSM(states) /   │
        │ InstrumentConnectionService / TdfService /      │
        │ tc_loader / tc_validator / events(RunnerEvents) │
        └──────┬──────────────────────────────┬──────────┘
               │ ctx.commands facade          │ ctx.report_writer
        ┌──────▼───── net ─────────┐   ┌──────▼──── report ────────┐
        │ protocol / tcp_client /  │   │ rawdata_source/workbook / │
        │ commands / lv_server /   │   │ excel_writer/report_writer│
        │ mock 서버들               │   │ template_map /            │
        └──────────────────────────┘   │ screenshot_store          │
                                       └───────────────────────────┘
                 (models, config 는 모든 계층에서 임포트 가능한 leaf)
```

- `core`는 UI 통지를 위해 Qt 시그널(`QObject`) 사용이 허용된다 —
  [events.py](../src/app/core/events.py)의 `RunnerEvents`가 FSM→UI 단방향 통지의 유일한 통로.
- UI→FSM 방향 개입은 `SessionContext`의 `threading.Event` 3종과 bool 플래그로만 이루어진다
  ([PROJECT_SPEC_1.0.1.md](PROJECT_SPEC_1.0.1.md)의 FSM 계층 참조).
- `net`의 Qt 의존은 [tcp_client.py](../src/app/net/tcp_client.py)에 국한되고
  protocol/commands/mock 계열은 순수 Python이다.

## 3. 디렉터리 맵 (실제 현재 구조)

```text
claude_test/
├── pyproject.toml               # 패키지 메타데이터(버전), 의존성, pytest 설정
├── uv.toml                      # uv 캐시를 저장소 내부 .uv-cache/에 둠
├── CE_NR_Radiated.spec          # PyInstaller 스펙 (산출물 이름: CE_MainBand_Radiation)
├── CLAUDE.md / AGENTS.md        # AI 에이전트용 프로젝트 규칙
├── docs/                        # 이 문서들
├── resources/
│   ├── main_window.ui           # 최소 골격만 (실제 화면 구조는 main_window.py 코드가 조립)
│   ├── icons/app_icon.{ico,png}
│   ├── templates/               # NR/LTE read-only RawData 원본 workbook
│   └── images/rf_switch_box_bd.png   # RF Switch Box 패널 배경 회로도
├── testcases/samples/harmonic_sample.csv
├── config/
│   ├── app_config.example.json            # AppConfig 스키마 예시 (현재 로드하는 코드 없음 — 휴면)
│   ├── instrument_connection.example.json # 장비 연결 입력 영속화 스키마 예시
│   └── excel_template_map.example.json    # 레거시 자리표시자 (실 매핑은 report/template_map.py 코드 상수)
├── src/app/
│   ├── __main__.py              # 엔트리포인트: logging → QApplication → MainWindow
│   ├── __init__.py              # __version__ (pyproject.toml과 수동 동기화)
│   ├── logging_setup.py         # 루트 로거 구성 (콘솔 + 선택적 파일)
│   ├── config/
│   │   ├── app_config.py                    # 휴면 코드 (아무도 로드하지 않음)
│   │   └── instrument_connection_settings.py # config/instrument_connection.json 영속화(fail-soft)
│   ├── models/                  # 도메인 모델 — PROJECT_SPEC_1.0.1.md §10
│   │   ├── enums.py             # NRBand, TestType, InputPath, FilterPath 등 12종
│   │   ├── test_case.py         # CSV 1행 = TestCase, 파생 프로퍼티(rb/range/scs)
│   │   ├── test_range.py        # 전역 Range 1~6 상수 (SA 설정 + SwitchBox 경로 묶음)
│   │   ├── band_group.py        # Band 그룹 4종 (SCS/recall/턴테이블 속도), (band,type)→Range
│   │   ├── nr_channel_lookup.py # band×BW×channel → NR-ARFCN/주파수 하드코딩 테이블
│   │   ├── rb_parameters.py     # (BW,SCS,RB할당) → (rb_size, rb_offset)
│   │   ├── supported_bandwidths.py
│   │   ├── switch_box.py        # 라벨 파싱, BRF band→PORT 매핑, 표시명
│   │   ├── measurement_result.py # Fundamental/Harmonic/Inband/Bilog 결과 dataclass
│   │   └── test_run_settings.py  # Start 시점 사용자 입력 검증 (frozen)
│   ├── core/
│   │   ├── events.py            # RunnerEvents — FSM/서비스→UI Qt 시그널 묶음
│   │   ├── runner.py            # 세션 컨트롤러: QThread 워커 + 시작 가드 + 수명주기
│   │   ├── run_preparer.py      # FSM worker에서 RawData 결과와 writer 준비
│   │   ├── tc_loader.py         # CSV 로드/저장 (헤더 완전 일치 검증)
│   │   ├── tc_validator.py      # TC 검증 (현재 band/BW 조합 1규칙)
│   │   ├── tdf_service.py       # TDF(FSV Factor) 목록/설정 비동기 서비스
│   │   ├── instrument_connection.py # 장비 연결/Set 비동기 서비스 (워커 3종)
│   │   ├── instrument_set.py    # Set 완료/에러 비동기 Event 대기 유틸
│   │   └── fsm/                 # 통합 세션 FSM — PROJECT_SPEC_1.0.1.md §12
│   │       ├── base.py          # State ABC, StateResult
│   │       ├── context.py       # SessionContext (세션 전역 데이터)
│   │       ├── engine.py        # FSMEngine + build_session_engine (전 상태 등록)
│   │       ├── call_routing.py  # Generation별 Call/Handover/복구 상태 결정
│   │       ├── equipment.py     # 장비 연결 여부 판정 헬퍼
│   │       ├── transition_flow.py # 복합 전환 체이닝(next_transition_or)
│   │       └── states/
│   │           ├── session.py   # SessionInit, Idle, PrepareReport, CheckNextCase, TestEnd
│   │           ├── nr_setup.py  # NRCallConnect, NRCallDisconnected
│   │           ├── lte_setup.py # LTECallConnect, LTECallDisconnected
│   │           ├── transition.py # AntPol/NR·LTE·NSA Handover/Recall/DUTAxis/TestType Change
│   │           └── measurement/
│   │               ├── common.py    # 공유 스텝(SwitchBox/SA/Turntable) + test_type 분기 허브
│   │               ├── harmonic.py  # Fundamental/Harmonics/Precision 측정
│   │               ├── inband.py    # In-band 측정
│   │               ├── bilog.py     # Bilog 측정 (LV 프로토콜은 In-band와 동일)
│   │               ├── manual_marker.py # 수동 마커 모드 공용 헬퍼
│   │               └── reporting.py # ReportWriter 호출 단일 관문
│   ├── net/                     # LabVIEW 연동 — PROJECT_SPEC_1.0.1.md §14
│   │   ├── protocol.py          # Request/Response/Event + length-prefix 프레이밍
│   │   ├── tcp_client.py        # QTcpSocket을 전용 QThread에 가둔 동기 클라이언트
│   │   ├── commands.py          # 고수준 facade — target/command/파라미터의 단일 진실
│   │   ├── lv_server_process.py # LV Inst Manager.exe 기동/종료/창 숨김
│   │   ├── mock_server.py       # pytest용 저수준 TCP 스텁
│   │   ├── mock_lv_server.py    # 장비 도메인 로직을 갖춘 모의 LabVIEW 서버 (CLI 실행 가능)
│   │   └── mock_lv_client.py    # commands facade 수동 실행 콘솔 (lv> REPL)
│   ├── report/                  # Excel + 스크린샷 — PROJECT_SPEC_1.0.1.md §15
│   │   ├── report_writer.py     # FSM이 부르는 facade (Excel 기록 + 스크린샷 finalize)
│   │   ├── excel_writer.py      # openpyxl + win32com COM 이중 경로
│   │   ├── rawdata_source.py    # dev/frozen 원본 조회와 관리 시트 검증
│   │   ├── rawdata_workbook.py  # EUT별 결과 생성·검증·재사용
│   │   ├── template_map.py      # 시트/셀 좌표 규칙 (코드 상수)
│   │   └── screenshot_store.py  # 스크린샷 파일명/경로 규칙과 복사
│   └── ui/                      # PROJECT_SPEC_1.0.1.md §16
│       ├── main_window.py       # 패널 조립 + 시그널 결선 허브 + 잠금 정책
│       ├── generated/           # pyside6-uic 산출물 (직접 편집 금지)
│       ├── instrument_check_panel.py
│       ├── test_manager_panel.py
│       ├── nr_select.py         # NR TestCase 생성 다이얼로그 2단
│       ├── rf_filter_box_panel.py
│       ├── test_plot_screenshot_panel.py
│       ├── manual_test_panel.py # placeholder (TODO(spec))
│       ├── manual_marker_dialog.py
│       ├── instrument_set_progress_dialog.py
│       └── log_panel.py
└── tests/                       # 계층별 테스트 — PROJECT_SPEC_1.0.1.md §20
```

## 4. 스레딩 모델

이벤트 루프 차단 금지 원칙에 따라 블로킹 작업은 전부 별도 스레드에 있다.

| 스레드 | 소유자 | 하는 일 |
| --- | --- | --- |
| UI(메인) 스레드 | QApplication | 모든 위젯, 시그널 슬롯. `Runner.start/stop`, 마커 명령 등 짧은 호출만 수행 |
| FSM 워커 (QThread) | [runner.py](../src/app/core/runner.py) `_RunnerWorker` | `FSMEngine.run("SessionInit")` 동기 실행. 앱 시작 시 1회 기동되어 세션 사이에도 Idle 루프로 **상주** |
| TCP 소켓 스레드 (QThread) | [tcp_client.py](../src/app/net/tcp_client.py) `_SocketThread` | QTcpSocket 소유. 명령 큐 소비 + 수신 폴링. `send_request`는 호출 스레드를 블로킹하는 **동기** API |
| 장비 연결/Set/VISA 탐색 워커 (QThread 3종) | [instrument_connection.py](../src/app/core/instrument_connection.py) | Connect(장비별 상태 dict 수신), Set(CO3000 Reference→3D Pol→FSV40 Self Align 순차), VISA 목록 조회 |
| TDF 워커 (QThread) | [tdf_service.py](../src/app/core/tdf_service.py) | TDF 목록/활성화/비활성화 단발 작업 |
| LV 창 숨김 데몬 스레드 | [lv_server_process.py](../src/app/net/lv_server_process.py) | LabVIEW 프론트 패널 창을 10초간 폴링하며 숨김 |

공통 규약:

- 워커 종료는 `quit + wait(1000ms)`, 실패 시 스레드를 detach해 자연 종료를 기다린다(강제 terminate 금지).
- FSM→UI는 Qt 시그널만, UI→FSM은 `threading.Event`/bool 플래그만 사용한다.
- `client.event_received`에 워커가 연결할 때는 `Qt.DirectConnection`을 쓰므로 핸들러 안에서는
  Qt 객체를 만지지 말고 `threading` 프리미티브만 사용해야 한다.

## 5. 대표 실행 흐름 (요약)

상세한 상태 전이와 명령 스키마는 [PROJECT_SPEC_1.0.1.md](PROJECT_SPEC_1.0.1.md)의 FSM/Net 계층 설명을 참조.

1. **기동** — `python -m app` → 로깅 구성 → `MainWindow` 생성 시 `Runner`가 조립되고
   `Runner.initialize()`가 FSM 워커를 띄워 `SessionInit`에서 장비 준비 대기.
2. **장비 연결** — Instrument Check 패널에서 VISA 주소/Switch Box IP 입력 → Connect →
   (패키징 실행이면 `LvServerManager`가 LV Inst Manager.exe 자동 기동) → LV에 장비별 `Connect`
   명령 → 성공 시 `Runner.mark_equipment_ready()`가 FSM gate 해제 → FSM이 `Idle` 진입.
3. **TC 준비** — Test Manager에서 NR/LTE 다이얼로그로 TestCase 생성(또는 CSV 불러오기),
   EUT 이름과 실행 옵션 설정.
4. **시험 실행** — 시작 버튼 → `Runner.start()`가 저비용 가드 통과 후 요청 저장 → FSM의
   `PrepareReport`가 EUT별 RawData 결과 확보, `ReportWriter` 생성과 Excel 라이브 모니터링 준비 →
   FSM이 TC 큐를 순회: Generation별 Call 연결 → SwitchBox/SA 설정 → 턴테이블 회전 →
   측정 → Excel 기록 + 스크린샷 저장 → `CheckNextCase`가 TC 간 차이를 보고 전환 상태
   (Handover/AntPol/축/Recall/타입) 스케줄 → 반복.
5. **종료** — 큐 소진 시 `TestEnd` → `session_finished` → FSM은 `Idle`로 복귀해 다음 Start 대기.
   사용자 정지는 `Runner.stop()` → Switch Box 안전 경로 복원 후 `session_stopped`.

## 6. 설정과 상태 저장

| 파일 | 쓰는 코드 | 내용 |
| --- | --- | --- |
| `config/instrument_connection.json` | [instrument_connection_settings.py](../src/app/config/instrument_connection_settings.py) (fail-soft 로드/저장) | Instrument Check 입력값(VISA 주소 4종, Switch Box IP/포트). **상대 경로**라 실행 디렉터리에 따라 위치가 달라진다 |
| `config/app_config.json` | 없음 (**휴면**) | `AppConfig` 로더는 존재하나 어떤 코드도 호출하지 않는다. TCP 주소는 `SessionContext` 기본값(127.0.0.1:5025) + UI 입력에서 온다 |
| RawData 원본 `.xlsx` | [rawdata_source.py](../src/app/report/rawdata_source.py) | 개발은 저장소 `resources/templates`, frozen은 `sys._MEIPASS/resources/templates`; read-only source로 사용 |
| EUT 결과 `.xlsx`와 스크린샷 | [rawdata_workbook.py](../src/app/report/rawdata_workbook.py), [screenshot_store.py](../src/app/report/screenshot_store.py) | 개발은 `~/Desktop/<EUT>`, frozen은 `<EXE 폴더>/<EUT>` 아래에 함께 저장 |

로깅은 [logging_setup.py](../src/app/logging_setup.py)가 루트 로거에 콘솔 핸들러를 부착하고,
UI에는 [log_panel.py](../src/app/ui/log_panel.py)의 `LogPanel`이 자체 logging 핸들러를 붙여
QPlainTextEdit로 미러링한다(스레드 안전: 시그널 경유). 파일 로그는 `setup_logging(log_file=...)`
인자로 지원되지만 현재 엔트리포인트는 인자 없이 호출하므로 비활성 상태다.

## 7. 버전

버전은 두 곳에 정의되며 **수동 동기화** 대상이다: [pyproject.toml](../pyproject.toml)의
`version`과 [src/app/__init__.py](../src/app/__init__.py)의 `__version__`. 현재 1.0.1.
PyInstaller 스펙에는 Windows 버전 리소스가 없어 배포 exe 속성에는 버전이 표시되지 않는다.
