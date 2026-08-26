# CE NR Radiated Measurement Automation SW Project Spec v1.0.1

## 1. 문서 목적

이 문서는 CE NR Radiated 측정 자동화 SW v1.0.1의 프로젝트 구조, 주요 기능, 실행 흐름, 모듈별 책임을 새 개발자가 빠르게 이해할 수 있도록 정리한 프로젝트 스펙 문서다.

본 프로젝트는 사용자 사용 검증이 어느 정도 완료된 안정 버전으로, 이 문서는 남은 리스크나 TODO를 중심으로 다루기보다 현재 개발되어 있는 기능과 코드 구성을 설명하는 데 초점을 둔다.

## 2. 프로젝트 개요

CE NR Radiated 측정 자동화 SW는 PySide6 기반 Windows 데스크톱 애플리케이션이다. 시험 오퍼레이터가 NR Radiated 측정 조건을 구성하고, 외부 LabVIEW 장비 제어 프로그램과 TCP/JSON으로 연동하여 측정 시퀀스를 실행하며, 결과를 Excel 리포트와 SA 스크린샷으로 저장한다.

Python 애플리케이션은 다음 책임을 가진다.

- Test Case 생성, 로드, 저장, 표시
- NR Band/BW/Channel/RB/Range 파라미터 계산
- 장비 연결 상태 확인 요청
- 장비 Set 작업 요청
- FSM 기반 측정 시퀀스 실행
- 외부 LabVIEW 프로그램과 TCP/JSON 명령 송수신
- Excel 템플릿에 결과 기록
- Spectrum Analyzer 스크린샷 최종 저장
- 오퍼레이터용 UI 제공

실제 장비 제어는 외부 LabVIEW 프로그램의 책임이다. Python 앱은 VISA 세션을 열어 장비를 직접 제어하지 않는다. 예외적으로 UI 입력 편의를 위한 로컬 VISA Resource 주소 목록 조회만 수행한다.

## 3. 대상 장비

프로젝트에서 다루는 주요 장비는 다음과 같다.

| 장비 | 역할 | Python 앱의 처리 방식 |
| --- | --- | --- |
| MT8000A | NR Callbox, NR Call/Handover | LabVIEW TCP command 호출 |
| FSV40 | Spectrum Analyzer, SA 설정/마커/스크린샷/TDF | LabVIEW TCP command 호출 |
| Switch Box | RF 입력/필터 경로 선택 | LabVIEW TCP command 호출 |
| CO3000 | Turntable, 3m/Bilog Mast 제어 | LabVIEW TCP command 호출 |
| 3D Controller | 1m Mast 편파 제어 | LabVIEW TCP command 호출 |

Instrument Check 화면에서는 장비별 VISA Resource 또는 IP/Port를 입력하고, LabVIEW 프로그램에 연결 요청을 보낸다.

## 4. 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| Language | Python 3.11+ |
| UI | PySide6 |
| Threading | QThread, QObject signal/slot |
| TCP | QTcpSocket 기반 client |
| Protocol | 4-byte length-prefix + UTF-8 JSON |
| Excel | openpyxl, pywin32 COM |
| VISA Resource 조회 | pyvisa ResourceManager.list_resources |
| Package manager | uv |
| Test | pytest, pytest-qt |
| Packaging | PyInstaller spec 파일 |

## 5. 저장소 구조

```text
claude_test/
  AGENTS.md
  README.md
  CLAUDE.md
  pyproject.toml
  uv.lock
  uv.toml
  CE_NR_Radiated.spec
  config/
  resources/
  src/app/
  testcases/
  tests/
  temp/
```

주요 디렉터리 역할은 다음과 같다.

| 경로 | 역할 |
| --- | --- |
| `src/app/models` | 시험 도메인 모델, enum, lookup table, Range 정의 |
| `src/app/core` | Test Case loader/validator, Runner, 장비 연결 서비스 |
| `src/app/core/fsm` | 측정 시퀀스 FSM 엔진과 상태 구현 |
| `src/app/net` | TCP client, protocol, LabVIEW command facade, mock server/client |
| `src/app/report` | Excel writer, report writer, screenshot store |
| `src/app/ui` | PySide6 UI 패널과 메인 윈도우 |
| `src/app/ui/generated` | `pyside6-uic` 생성 UI 파일 |
| `resources` | Qt Designer `.ui`, 아이콘, RF Switch Box 이미지 |
| `config` | 설정 예시 파일 |
| `testcases` | 샘플 Test Case CSV |
| `tests` | models/core/net/report/ui 테스트 |
| `temp` | 개발 보조 문서, 임시 스크린샷, LV 요구사항 문서 |

## 6. 애플리케이션 진입점

앱 실행 진입점은 `src/app/__main__.py`다.

실행 명령:

```bash
uv run python -m app
```

실행 시 동작은 다음과 같다.

1. 로깅 초기화
2. `QApplication` 생성
3. 앱 아이콘 설정
4. `MainWindow` import
5. 메인 윈도우 표시
6. Qt event loop 실행

생성된 UI 모듈이 없는 경우, `.ui` 파일을 먼저 컴파일하라는 에러 로그를 남기고 종료한다.

## 7. Build / Run / Test

기본 개발 환경 준비:

```bash
uv sync
```

Qt Designer `.ui` 변경 후 generated UI 재생성:

```bash
uv run pyside6-uic resources/main_window.ui -o src/app/ui/generated/main_window_ui.py
```

앱 실행:

```bash
uv run python -m app
```

테스트 실행:

```bash
uv run --no-sync pytest -q
```

영역별 테스트:

```bash
uv run --no-sync pytest tests/models -q
uv run --no-sync pytest tests/core -q
uv run --no-sync pytest tests/net -q
uv run --no-sync pytest tests/report -q
```

기본 pytest는 `tests/ui/**`, Qt/QThread runtime 의존 테스트, native desktop 테스트를
`quarantined`로 skip하고 안전한 순수 테스트만 실행한다. 명시 경로와 `-m`으로는
이 격리를 우회할 수 없다. 사용자가 명시적으로 승인한 격리 환경에서만 다음
opt-in 명령을 사용한다.

```bash
uv run --no-sync pytest --run-quarantined tests/ui -q
```

PyInstaller 빌드 설정은 `CE_NR_Radiated.spec`에 있다.

## 8. 전체 실행 흐름

오퍼레이터 사용 기준의 기본 흐름은 다음과 같다.

```text
1. 앱 실행
2. Instrument Check 화면에서 장비 연결 정보 입력
3. Connect 실행
4. 연결된 장비 상태 확인
5. 필요 장비 Set 실행
6. Test Manager 화면에서 EUT 이름, Excel template, screenshot 저장 경로 입력
7. NR Test Case 생성 또는 CSV load
8. 필요 시 TDF list 조회 / TDF all off / TDF set
9. Start 또는 Single Start 실행
10. Runner가 FSM worker thread 실행
11. FSM이 각 State를 순차 실행
12. State가 net.commands facade 호출
13. TcpClient가 LabVIEW 서버에 command 전송
14. LabVIEW가 장비 제어 후 response/event 반환
15. FSM이 측정 결과를 ReportWriter에 전달
16. Excel template에 결과 기록
17. SA screenshot을 최종 경로에 저장
18. UI에 진행 상태, 로그, 최신 screenshot 표시
```

## 9. 계층 구조와 의존 방향

프로젝트의 주요 의존 방향은 다음과 같다.

```text
ui -> core -> net
          -> report
          -> models
```

원칙:

- `ui`는 `core`의 Runner, service, event signal을 사용한다.
- `core`는 FSM과 장비 연결 작업을 조립한다.
- `core/fsm`은 `net.commands` facade를 통해 외부 프로그램에 요청한다.
- `report`는 Excel과 screenshot 저장만 담당한다.
- `net`과 `report`는 `ui`에 의존하지 않는다.
- `models`는 대부분의 계층에서 공유되는 순수 도메인 타입과 lookup을 제공한다.

## 10. Models 계층

경로: `src/app/models`

Models 계층은 시험 조건을 코드에서 안정적으로 표현하기 위한 기반이다.

### 10.1 주요 파일

| 파일 | 역할 |
| --- | --- |
| `enums.py` | NR Band, Generation, TestType, AntennaPol, DUTAxis, Modulation, RBAllocation, Switch/Filter path enum |
| `test_case.py` | CSV 한 행을 표현하는 `TestCase` dataclass |
| `test_range.py` | Range 1~6 고정 정의 |
| `band_group.py` | Band group, SCS, turntable speed, Range mapping |
| `supported_bandwidths.py` | Band별 지원 bandwidth 검증 |
| `rb_parameters.py` | Bandwidth/SCS/RB allocation 기준 RB size/offset lookup |
| `nr_channel_lookup.py` | Call channel, target frequency lookup |
| `measurement_result.py` | Fundamental/Harmonic/Inband/Bilog 결과 모델 |
| `switch_box.py` | Switch Box input/filter parsing 및 BRF filter path resolve |
| `test_run_settings.py` | 실행 시 UI에서 전달되는 run setting 모델 |

### 10.2 TestCase 모델

`TestCase`는 측정 조건 한 행을 표현한다.

주요 필드:

- `generation`
- `band`
- `anchor_band`
- `bandwidth`
- `test_type`
- `modulation`
- `rb_allocation`
- `test_channel`
- `antenna_pol`
- `dut_axis`
- `dut_ant_position`

주요 파생 속성:

- `rb_size`
- `rb_offset`
- `rb_parameters`
- `scs_khz`
- `test_range`
- `range_name`
- `range_definition`

`TestCase.from_csv_row()`는 CSV dict를 enum과 숫자 타입으로 변환하고 검증한다. `to_csv_row()`는 다시 CSV 저장 가능한 dict로 변환한다.

### 10.3 CSV 스키마

CSV fieldnames:

```text
generation,band,anchor_band,bandwidth,test_type,modulation,rb_allocation,test_channel,antenna_pol,dut_axis,dut_ant_position
```

`anchor_band`는 `NR_NSA`에서만 필수이며 지원값은
`B1/B3/B7/B5/B8/B20/B28/B38/B40/B41`이다. `NR_SA`와 `LTE`에서는 빈 값이어야 한다.
기존 10열 `NR_SA`/`LTE` CSV는 읽을 수 있지만 저장 시 11열로 갱신되며, 10열
`NR_NSA`는 Anchor를 추정하지 않고 차단한다.

샘플 파일:

```text
testcases/samples/harmonic_sample.csv
```

샘플 내용:

```csv
generation,band,anchor_band,bandwidth,test_type,modulation,rb_allocation,test_channel,antenna_pol,dut_axis,dut_ant_position
NR_SA,n78,,100,harmonic,QPSK,Inner_Full,mid,H,X,Upper
```

### 10.4 TestRange 정의

`test_range.py`는 Range 1~6을 고정 상수로 정의한다.

각 Range는 다음 값을 가진다.

- Range ID
- Start frequency
- Stop frequency
- RBW
- VBW
- Limit
- Sweep point
- Switch Box input path
- Filter mode

Range 정의는 SA 설정과 Switch Box 경로 설정에 함께 사용된다.

### 10.5 RB Parameter lookup

`rb_parameters.py`는 DFT-s 기반 RB allocation에 대한 RB size/offset lookup table이다.

lookup key:

```text
(bandwidth_mhz, scs_khz, rb_allocation)
```

값:

```text
(rb_size, rb_offset)
```

`resolve_rb_parameters()`는 다음 절차로 값을 결정한다.

1. Band로부터 BandGroup 조회
2. BandGroup에서 SCS 확인
3. Bandwidth 정규화
4. `(bandwidth, scs, rb_allocation)` key 생성
5. RB size/offset 반환

현재 OFDM은 스펙 범위 밖이며, DFT-s 조합만 지원한다.

## 11. Core 계층

경로: `src/app/core`

Core 계층은 앱 실행의 조립부다. UI 입력을 받아 FSM 실행 컨텍스트를 구성하고, 장비 연결 서비스와 테스트 실행 Runner를 제공한다.

### 11.1 주요 파일

| 파일 | 역할 |
| --- | --- |
| `tc_loader.py` | CSV Test Case load/save |
| `tc_validator.py` | Test Case 검증 |
| `runner.py` | 측정 세션 실행 컨트롤러 |
| `events.py` | RunnerEvents Qt signal 정의 |
| `instrument_connection.py` | Instrument Check 연결/탐색/Set service |
| `instrument_set.py` | 장비 Set event 대기/검증 helper |
| `tdf_service.py` | FSV40 TDF list/all off/set 작업 service |

### 11.2 Runner

`Runner`는 측정 실행의 중심 객체다.

책임:

- `RunnerEvents` 생성
- 공용 `TcpClient` 소유 또는 주입
- 공용 `commands` facade 소유
- `InstrumentConnectionService` 소유
- FSM worker thread 생성
- `SessionContext` 구성
- TestCase queue와 실행 설정 주입
- Excel `ReportWriter` 생성
- Start/Single Start/Stop 처리
- 수동 marker command 중계
- 장비 연결 상태를 FSM gate에 전달

`Runner.start()`는 다음 입력을 받는다.

- `cases`
- `settings`
- `start_index`
- `stop_index`

시작 전에 장비 준비 상태, Instrument Set 진행 여부, report writer 생성 가능 여부, Excel 준비 가능 여부를 확인한다.

### 11.3 InstrumentConnectionService

`InstrumentConnectionService`는 Instrument Check 화면에서 사용하는 비동기 서비스다.

주요 기능:

- VISA Resource 목록 조회
- LabVIEW TCP 서버에 장비 Connect 요청
- 장비별 연결 결과 반환
- 장비 Set 작업 실행
- worker thread shutdown 처리
- 연결 중복 요청 방지
- 실행 중 연결 요청 차단

연결 대상 장비:

- FSV40
- MT8000A
- CO3000
- Switch Box
- 3D Controller

임시 개발/검증 정책에 따라 선택된 장비 기준 준비 상태 판단을 지원한다. 즉 응답한 장비가 하나 이상 있고 모두 성공이면 selected equipment ready로 볼 수 있다.

### 11.4 Instrument Set

Instrument Set은 연결 완료된 장비에 대해 초기 기준 동작을 순차 수행한다.

연결 상태에 따라 수행되는 단계:

- CO3000: Set Reference
- 3D Controller: Ant Pol Vertical
- FSV40: Self Alignment

CO3000 Set Reference와 FSV40 Self Alignment는 command 응답뿐 아니라 완료 event 수신을 기다린다.

### 11.5 TDF Service

`TdfService`는 FSV40 TDF 조작을 담당한다.

지원 기능:

- TDF file list 조회
- TDF all off
- 선택 TDF set

UI에서는 Test Manager 화면에서 TDF list box와 활성 TDF 표시로 연결된다.

## 12. FSM 계층

경로: `src/app/core/fsm`

FSM은 실제 측정 시퀀스를 상태 단위로 구현한 핵심 실행 구조다.

### 12.1 FSM 기본 구조

`FSMEngine`은 등록된 State를 이름으로 찾아 다음 순서로 실행한다.

```text
state.enter(ctx)
result = state.run(ctx)
state.exit(ctx)
next_state = state.next_state(ctx, result)
```

`StateResult`는 상태 실행 결과를 표현한다.

- `OK`
- `FAIL`
- `RETRY`
- `WAIT_USER`

FSM은 QThread worker 안에서 동기적으로 실행된다. UI와의 통신은 `RunnerEvents` signal로 수행한다.

### 12.2 SessionContext

`SessionContext`는 세션 전체 상태를 보관한다.

주요 필드:

- `queue`: TestCase 목록
- `commands`: command facade
- `events`: RunnerEvents
- `client`: TCP client
- `report_writer`: ReportWriter
- `current_index`
- `start_index`
- `stop_index`
- `paused`
- `stopped`
- `current_case_stop_requested`
- `current_angle`
- `fundamental_frequency_mhz`
- `last_applied_factor_keyword`
- `temp_dir`
- `settings`
- `model_name`
- `template_path`
- `screenshot_root_dir`
- `equipment_state`
- `harmonic_precision_candidates`
- `equipment_connect_requested`
- `test_start_requested`
- `user_action_completed`
- `pending_transition_states`

`last_applied_factor_keyword`는 마지막 Set TDF 성공 Factor를 보관한다. `Idle`에서 Test Start를
수락할 때와 `TestEnd`에서 초기화하고, 같은 Factor가 연속되면 TDF 목록 조회와 적용을 생략한다.
목록 조회에 성공하면 `RunnerEvents.tdf_file_list_changed`로 전체 목록을 UI에 전달하고, 새 파일
적용에 성공하면 `RunnerEvents.active_tdf_file_changed`로 실제 파일명을 UI에 전달한다.

### 12.3 등록되는 State 그룹

`build_session_engine()`은 모든 State를 등록한다.

세션 제어:

- `SessionInit`
- `Idle`
- `CheckNextCase`
- `TestEnd`

NR 연결:

- `NRCallConnect`
- `NRCallDisconnected`

시험 간 전환:

- `AntPolChange`
- `Handover`
- `NSAHandover`
- `RecallChange`
- `DUTAxisChange`
- `TestTypeChange`
- `ApplyTdf`

공통 측정:

- `InitialTurntableZero`
- `SetupSpectrumAnalyzerStartupLevel`
- `PrepareFundamentalSwitchBoxBeforeCall`
- `PrepareFundamentalSwitchBox`
- `SetSwitchBox`
- `SetupSpectrumAnalyzer`
- `RotateTurntable`
- `ResetSwitchBox`

Harmonic:

- `MeasureFundamental`
- `MeasureHarmonics`
- `MeasureHarmonicsManual`
- `MeasureHarmonicPrecision`

In-band:

- `MeasureInBand`
- `MeasureInBandManual`

Bilog:

- `MeasureBilog`
- `MeasureBilogManual`

### 12.4 대표 상태 흐름

기본 흐름:

```text
SessionInit
  -> Idle
  -> InitialTurntableZero
  -> AntPolChange
  -> SetupSpectrumAnalyzerStartupLevel
  -> NRCallConnect
  -> ApplyTdf
  -> measurement states
  -> ResetSwitchBox
  -> CheckNextCase
  -> transition states or TestEnd
```

Harmonic 측정 진입 흐름:

```text
SetupSpectrumAnalyzerStartupLevel
  -> PrepareFundamentalSwitchBoxBeforeCall
  -> NRCallConnect
  -> ApplyTdf
  -> MeasureFundamental
  -> PrepareFundamentalSwitchBox
  -> SetSwitchBox
  -> SetupSpectrumAnalyzer
  -> RotateTurntable
  -> MeasureHarmonics
  -> optional MeasureHarmonicPrecision
  -> ResetSwitchBox
  -> CheckNextCase
```

In-band/Bilog 측정 흐름:

```text
SetupSpectrumAnalyzerStartupLevel
  -> NRCallConnect
  -> ApplyTdf
  -> SetSwitchBox
  -> SetupSpectrumAnalyzer
  -> RotateTurntable
  -> MeasureInBand or MeasureBilog
  -> ResetSwitchBox
  -> CheckNextCase
```

Manual marker mode가 켜져 있으면 `RotateTurntable` 이후 자동 측정 state 대신 manual 측정 state로 분기한다.

### 12.5 Turntable 진행 event

`RotateTurntableState`는 CO3000 회전 명령을 보낸 후 event를 기다린다.

처리하는 event:

- `turntable_progress`
- `turntable_complete`
- `equipment_error`

진행 중 angle update는 UI의 turntable info에 반영된다.

### 12.6 중단 시 Switch Box 안전 경로 복원

FSM 실행 중 stop 또는 예외가 발생하면 `FSMEngine`은 Switch Box가 연결되어 있을 때 best-effort로 안전 경로를 복원한다.

안전 경로:

- Input path: `INPUT2`
- Filter path: `THRU`

## 13. 측정 타입별 구현

### 13.1 Harmonic

Harmonic 측정은 다음을 수행한다.

1. Fundamental frequency 측정
2. Fundamental screenshot 저장
3. 2nd~5th harmonic marker 측정
4. Limit 초과 peak만 recordable peak로 판단
5. Harmonic screenshot 저장
6. 필요 시 precision 후보 구성
7. Precision SA setting 적용
8. Precision marker 측정
9. Precision screenshot 저장
10. Excel에 frequency와 level 기록

관련 파일:

- `src/app/core/fsm/states/measurement/harmonic.py`
- `src/app/models/measurement_result.py`
- `src/app/report/report_writer.py`
- `src/app/report/excel_writer.py`
- `src/app/report/screenshot_store.py`

### 13.2 In-band

In-band 측정은 공통 SA/Switch Box/Turntable 흐름 이후 `MeasureInBand`에서 수행된다.

동작:

1. 오래된 임시 screenshot 제거
2. `commands.measure_inband()` 호출
3. Limit 초과 여부 판단
4. `temp/inband.png`를 결과 screenshot으로 사용
5. Excel에 In-band level 기록
6. Screenshot 최종 저장

Manual marker mode에서는 `commands.measure_inband_manual()` 경로를 사용한다.

### 13.3 Bilog

Bilog는 현장 챔버 1차 컨펌 기준으로 In-band와 동일한 LV 측정 프로토콜을 사용한다.

구현 정책:

- Bilog command는 In-band와 동일하게 `FSV40 / Mark Inband`를 사용한다.
- `commands.measure_bilog()`는 `commands.measure_inband()`에 위임한다.
- `commands.measure_bilog_manual()`은 `commands.measure_inband_manual()`에 위임한다.
- LV가 측정 중 `temp/inband.png`를 생성하고 Bilog 상태가 이를 소비하는 동작은 의도된 현재 명세다.

Bilog와 In-band의 차이는 주로 방사원 신호, 표시되는 Range/SA 대역, 리포트 기록 위치에 있다.

## 14. Net 계층

경로: `src/app/net`

Net 계층은 Python 앱과 외부 LabVIEW 프로그램 사이의 TCP/JSON 통신을 담당한다.

### 14.1 주요 파일

| 파일 | 역할 |
| --- | --- |
| `protocol.py` | Request/Response/Event dataclass, frame encode/decode |
| `tcp_client.py` | QTcpSocket 기반 client |
| `commands.py` | FSM이 사용하는 고수준 command facade |
| `mock_lv_server.py` | LabVIEW server mock |
| `mock_lv_client.py` | command facade 테스트/수동 확인용 mock client |
| `mock_server.py` | 간단한 loopback mock server |
| `lv_server_process.py` | frozen 앱에서 LV server process 관리 |

### 14.2 Frame protocol

프레임 구조:

```text
4-byte big-endian payload length
UTF-8 JSON payload
```

최대 payload:

```text
64 MB
```

### 14.3 JSON message

Request/Event:

```json
{
  "type": "request",
  "id": "...",
  "target": "...",
  "command": "...",
  "Params": {}
}
```

Response:

```json
{
  "type": "response",
  "id": "...",
  "status": "ok",
  "Result": {},
  "Error": null
}
```

Event:

```json
{
  "type": "event",
  "id": "...",
  "target": "...",
  "command": "...",
  "Params": {}
}
```

### 14.4 Command facade

`commands.py`는 FSM과 UI service에서 사용하는 고수준 함수들을 제공한다.

장비 연결/Set:

- `connect_equipment`
- `set_reference_co3000`
- `self_align_fsv40`

MT8000A:

- `setup_mt8000`
- `call_handover`
- `check_call_status`

FSV40:

- `setup_sa`
- `setup_sa_startup_levels`
- `setup_sa_precision`
- `measure_fundamental`
- `measure_harmonics`
- `measure_harmonic_precision`
- `measure_inband`
- `measure_bilog`
- `measure_inband_manual`
- `measure_bilog_manual`
- `get_screenshot`
- `marker_peak`
- `marker_next`
- `marker_off`
- `marker_all_off`
- `get_tdf_list`
- `tdf_all_off`
- `set_tdf`

CO3000:

- `rotate_turntable`
- `get_turntable_angle`
- `stop_turntable`
- `set_antenna_pol`

Switch Box:

- `set_switch_input`
- `set_switch_filter`
- `set_switch_box`

모든 command 함수는 내부적으로 `client.send_request(target, command, params)`를 호출한다.

## 15. Report 계층

경로: `src/app/report`

Report 계층은 Excel 결과 기록과 SA screenshot 최종 저장을 담당한다.

### 15.1 주요 파일

| 파일 | 역할 |
| --- | --- |
| `excel_writer.py` | Excel workbook 작성 및 live monitoring |
| `report_writer.py` | Excel write와 screenshot finalize 묶음 |
| `screenshot_store.py` | Screenshot 최종 경로 생성 및 복사 |
| `template_map.py` | Band group/generation별 Excel cell mapping |

### 15.2 ExcelReportWriter

`ExcelReportWriter`는 Excel 템플릿 파일을 열고 측정 결과를 즉시 기록한다.

주요 기능:

- Band sheet 선택
- Band info 최초 1회 기록
- Fundamental frequency 기록
- Harmonic frequency 자동 계산 및 기록
- Harmonic level 기록
- In-band level 기록
- Bilog level 기록
- 열린 Excel workbook에 pywin32 COM으로 직접 update
- 저장 후 pending cell clear

지원 write method:

- `write_fundamental`
- `write_harmonic`
- `write_inband`
- `write_bilog`

기존 batch API인 `write(results, output_path)`는 더 이상 사용하지 않는다.

### 15.3 ReportWriter

`ReportWriter`는 FSM measurement state에서 직접 호출하는 report facade다.

주요 기능:

- 시험 시작 전 Excel live monitoring 준비
- Fundamental write 후 screenshot 저장
- Harmonic write 후 screenshot 저장
- In-band write 후 screenshot 저장
- Bilog write 후 screenshot 저장
- Excel에서 기존 fundamental frequency 읽기

### 15.4 Screenshot 저장 규칙

Screenshot 저장 구조:

```text
<root_dir>/
  <model_name>/
    Traffic/
      5G/
        <band>/
          <dut_ant_position>/
            <SA or NSA>/
              <filename>.png
```

일반 SA screenshot filename 구성:

```text
<model>_Traffic_5G_<SA|NSA>_<band>_<dut_ant_position>_
<target_frequency>_<start_freq>_<stop_freq>_<axis><pol>.png
```

Fundamental screenshot filename:

```text
<model>_Traffic_5G_<SA|NSA>_<band>_<dut_ant_position>_
<target_frequency>_Fundamental Frequency.png
```

Harmonic precision screenshot filename:

```text
<model>_Traffic_5G_<SA|NSA>_<band>_<dut_ant_position>_
<peak_frequency>_<axis><pol>_<sweep_time>ms.png
```

동일 파일명이 이미 있으면 `(1)`, `(2)` suffix를 붙여 저장한다.

## 16. UI 계층

경로: `src/app/ui`

UI는 PySide6 기반이며, 실제 사용자 조작 화면을 제공한다.

`src/app/ui/generated/main_window_ui.py`는 `resources/main_window.ui`에서 생성된 파일이다. 직접 수정하지 않고, UI 로직은 wrapper/패널 클래스에 작성한다.

### 16.1 MainWindow

파일:

```text
src/app/ui/main_window.py
```

역할:

- 최상위 QMainWindow
- 좌측 navigation button 구성
- 우측 stacked page 구성
- Instrument Check, Manual Test, Test Manager, Test Plot Screenshot page 연결
- RF Filter Box 별도 modeless window 연결
- Runner 생성 및 signal 연결
- TDF service 생성 및 signal 연결
- RF Switch Box service 생성 및 signal 연결
- 측정 중 Instrument Check/Set/TDF/RF 조작 lock 제어
- 사용자 수동 조작 dialog 표시
- manual marker dialog 표시
- 창 종료 시 worker/service 정리

### 16.2 Instrument Check 화면

파일:

```text
src/app/ui/instrument_check_panel.py
```

주요 기능:

- VISA Resource combo 표시
- CO3000, 3D Controller, FSV40, MT8000A resource 입력
- Switch Box IP/Port 입력
- Connect 버튼
- Set 버튼
- 연결 상태 label 표시
- 장비 Set 진행 dialog 표시
- 성공한 연결 설정 저장
- 화면 최초 표시 시 VISA Resource 자동 탐색

장비 상태 표시는 다음 status를 사용한다.

- Not Connected
- Connecting
- Connected
- Failed

### 16.3 Test Manager 화면

파일:

```text
src/app/ui/test_manager_panel.py
```

주요 기능:

- EUT 이름 입력
- Excel template path 선택
- Screenshot root path 선택
- Saturation Time 입력
- Connection Waiting Time 입력
- Atten Level 입력
- Next Peak Search Level 입력
- Custom Turn Table Speed 입력
- Manual Marker mode 선택
- NR SA/NR NSA Test Case 통합 생성 dialog 실행
- CSV Test Case load/save
- Test Case table 표시
- Start / Single Start / Stop
- TDF list 조회
- TDF all off
- 선택 TDF set
- 활성 TDF 표시
- 현재 실행 TestCase 표시
- 완료 TestCase row 표시
- 장비 연결 상태 indicator 표시
- Spectrum Analyzer info 표시
- Switch Box info 표시
- Turntable info 표시
- Polarization info 표시
- UI log panel 표시

RAT 버튼은 `NR SA → NR NSA → LTE → WCDMA → GSM` 순서이며, SA와 NSA 화면 상태는
Generation별로 독립 보존한다. NSA TestCase의 Band 표시는 `n5-B1` 형식을 사용한다.

Test Case table 주요 컬럼:

- Index
- Generation
- Band
- EUT ANT
- SCS
- BW
- Modulation
- RB Allocation
- RB Size
- RB Offset
- CH
- ARFCN
- CH_No.
- Case
- Start Freq
- Stop Freq
- Axis
- Pol

### 16.4 NR Select Dialog

파일:

```text
src/app/ui/nr_select.py
```

주요 기능:

- NR SA/NR NSA Generation별 단일 통합 화면
- NR Band 선택과 Parameter Table 동시 표시
- NR Band별 parameter 선택
- Band group별 test range option 구성
- Axis/Pol option 선택
- 기본 parameter 생성
- NSA 화면의 Band별 LTE Anchor 선택
- Generation별 `NRSelectState` 저장과 복원
- TestCase 목록 생성 후 Test Manager로 전달

### 16.5 RF Filter Box 화면

파일:

```text
src/app/ui/rf_filter_box_panel.py
```

RF Switch Box 수동 조작 화면이다. MainWindow stack page가 아니라 별도 modeless dialog로 열린다.

주요 기능:

- RF Switch Box block diagram 표시
- Input path 버튼 표시
- Filter path 버튼 표시
- 현재 active path red line 표시
- SET command 실행
- THRU command 실행
- Switch Box 연결 상태에 따른 버튼 enable/disable
- FSM이 알려준 Switch Box 상태와 UI 표시 동기화

배경 이미지:

```text
resources/images/rf_switch_box_bd.png
```

### 16.6 Test Plot Screenshot 화면

파일:

```text
src/app/ui/test_plot_screenshot_panel.py
```

주요 기능:

- `screenshot_saved` event로 전달된 최신 screenshot path 표시
- 이미지 파일 로드
- 화면 크기에 맞게 pixmap scaling
- 지원 확장자 검증
- 우측 log panel 표시

### 16.7 Manual Marker Dialog

파일:

```text
src/app/ui/manual_marker_dialog.py
```

Manual marker mode에서 표시되는 dialog다.

지원 동작:

- Marker Peak
- Marker Next
- Marker OFF
- Marker ALL OFF
- 완료
- 중단

Dialog에서 발생한 요청은 Runner의 marker command method로 연결된다.

## 17. Config 및 Resource

### 17.1 config

`config/app_config.example.json`:

```json
{
  "tcp_host": "127.0.0.1",
  "tcp_port": 5025,
  "tcp_timeout_s": 5.0,
  "excel_template_path": "resources/report_template.xlsx"
}
```

`config/instrument_connection.example.json`:

```json
{
  "mt8000a_visa_resource": "TCPIP0::192.168.0.3::inst0::INSTR",
  "fsv40_visa_resource": "TCPIP0::192.168.0.2::inst0::INSTR",
  "co3000_visa_resource": "ASRL1::INSTR",
  "controller_3d_visa_resource": "ASRL2::INSTR",
  "switch_box_ip_address": "192.168.0.10",
  "switch_box_port": 5000
}
```

### 17.2 resources

주요 resource:

- `resources/main_window.ui`
- `resources/icons/app_icon.ico`
- `resources/icons/app_icon.png`
- `resources/images/rf_switch_box_bd.png`

## 18. Logging

로깅 초기화는 `src/app/logging_setup.py`에서 수행한다.

UI에서는 `LogPanel`이 Python logging handler를 `QPlainTextEdit`에 mirror한다. Instrument Check, Test Manager, Test Plot Screenshot 화면에서 로그 패널을 사용한다.

코드에서는 `print` 대신 `logging`을 사용한다.

## 19. 외부 LabVIEW 연동 경계

Python 앱은 장비를 직접 제어하지 않는다.

허용:

- VISA Resource 목록 조회
- 사용자가 선택한 VISA 주소를 LabVIEW TCP command parameter로 전달
- TCP/JSON request/response/event 처리

금지:

- `open_resource`
- VISA session 유지
- `write`
- `read`
- `query`
- SCPI 직접 전송
- 측정/설정/상태 확인 목적의 직접 장비 제어

이 경계는 프로젝트 아키텍처에서 매우 중요하다. Python은 오케스트레이션/UI/리포트 계층이며, 장비 제어 실행자는 LabVIEW다.

## 20. 테스트 구성

테스트는 영역별로 구성되어 있다.

| 경로 | 검증 대상 |
| --- | --- |
| `tests/models` | enum, TestCase, Range, RB parameter, channel lookup 등 |
| `tests/core` | Runner, FSM, 장비 연결, TDF, TC loader/validator |
| `tests/net` | protocol, TCP client, command facade, mock LV server/client |
| `tests/report` | Excel writer, template map, screenshot store, report writer |
| `tests/ui` | PySide6 UI 패널, main window scaffold, interaction |

테스트 실행에는 pytest와 pytest-qt를 사용한다.
`qt_runtime`, `native_desktop`, `quarantined` marker는 위험 테스트를 식별한다.
`tests/ui/**`와 지정된 Qt core/net 모듈은 자동 분류되며, 신규 테스트가
`qtbot` 또는 `qapp` fixture를 사용해도 collection 시 자동으로 격리된다.
`--run-quarantined`는 사용자의 명시적 승인 없이 사용하지 않는다.

## 21. 개발자가 먼저 보면 좋은 파일 순서

처음 프로젝트를 인수받은 개발자는 다음 순서로 보면 전체 구조를 빠르게 잡을 수 있다.

1. `README.md`
2. `AGENTS.md`
3. `src/app/__main__.py`
4. `src/app/ui/main_window.py`
5. `src/app/core/runner.py`
6. `src/app/core/fsm/engine.py`
7. `src/app/core/fsm/context.py`
8. `src/app/core/fsm/states/session.py`
9. `src/app/core/fsm/states/measurement/common.py`
10. `src/app/core/fsm/states/measurement/harmonic.py`
11. `src/app/core/fsm/states/measurement/inband.py`
12. `src/app/core/fsm/states/measurement/bilog.py`
13. `src/app/net/commands.py`
14. `src/app/net/protocol.py`
15. `src/app/report/report_writer.py`
16. `src/app/report/excel_writer.py`
17. `src/app/models/test_case.py`
18. `src/app/models/test_range.py`
19. `src/app/models/rb_parameters.py`

## 22. 기능 요약

v1.0.1 기준 구현된 주요 기능을 한눈에 정리하면 다음과 같다.

| 영역 | 구현 기능 |
| --- | --- |
| Test Case | NR Test Case 생성, CSV load/save, table 표시 |
| Parameter | Band/BW/SCS/RB/channel/range 계산 |
| Instrument Check | VISA resource 조회, 장비 연결 요청, 상태 표시 |
| Instrument Set | CO3000 Set Reference, 3D Controller Vertical, FSV40 Self Alignment |
| TDF | TDF list 조회, all off, selected TDF set |
| FSM | 세션 초기화, 대기, 측정, TC 전환, 종료 |
| Transition | Ant Pol, Handover, Recall, DUT Axis, Test Type 변경 |
| Harmonic | Fundamental, Harmonic marker, precision 측정 |
| In-band | In-band 측정, manual marker mode |
| Bilog | In-band 공통 프로토콜 기반 Bilog 측정 |
| Switch Box | 자동 경로 설정, 중단 시 안전 경로 복원, 수동 SET/THRU |
| Turntable | 0도 초기화, 0/360 회전, progress event 표시 |
| Report | Excel live update, band info, frequency/level 기록 |
| Screenshot | Fundamental/Harmonic/In-band/Bilog/Precision screenshot 저장 |
| UI | Instrument Check, Test Manager, RF Filter Box, Screenshot viewer |
| Mock | LabVIEW mock server/client, loopback test 기반 |

## 23. 변경 작업별 시작 지점

이어 개발하는 사람이 작업 범위를 잡을 때는 아래 파일부터 확인하면 된다.

| 작업 종류 | 먼저 볼 파일 |
| --- | --- |
| Test Case CSV 스키마 변경 | `src/app/models/test_case.py`, `src/app/core/tc_loader.py`, `src/app/ui/test_manager_panel.py` |
| NR Band/BW/채널 추가 | `src/app/models/enums.py`, `src/app/models/supported_bandwidths.py`, `src/app/models/nr_channel_lookup.py` |
| RB allocation 추가 | `src/app/models/rb_parameters.py`, `src/app/models/enums.py` |
| Range/SA 설정 변경 | `src/app/models/test_range.py`, `src/app/models/band_group.py`, `src/app/core/fsm/states/measurement/common.py` |
| LabVIEW command 변경 | `src/app/net/commands.py`, `tests/net/test_commands.py` |
| TCP frame/protocol 변경 | `src/app/net/protocol.py`, `src/app/net/tcp_client.py`, `tests/net/test_protocol.py` |
| 측정 흐름 변경 | `src/app/core/fsm/engine.py`, `src/app/core/fsm/states/**`, `tests/core/test_fsm_*.py` |
| Excel 셀 매핑 변경 | `src/app/report/template_map.py`, `src/app/report/excel_writer.py`, `tests/report` |
| Screenshot 이름/경로 변경 | `src/app/report/screenshot_store.py`, `tests/report/test_screenshot_store.py` |
| UI 화면 변경 | `resources/main_window.ui`, `src/app/ui/**`, `tests/ui` |

## 24. 핵심 설계 문장

이 프로젝트를 한 문단으로 설명하면 다음과 같다.

CE NR Radiated 측정 자동화 SW는 PySide6 기반 오퍼레이터 앱으로, NR Test Case를 생성하고 장비 연결/Set 상태를 확인한 뒤, FSM 기반으로 Harmonic, In-band, Bilog 측정 시퀀스를 실행한다. Python 앱은 장비를 직접 VISA 제어하지 않고 외부 LabVIEW 프로그램과 TCP/JSON 프로토콜로 통신하며, 측정 결과는 Excel 템플릿에 즉시 기록되고 SA 스크린샷은 모델명과 측정 조건 기반 폴더 구조로 저장된다. 전체 구조는 UI, core/FSM, net command facade, report writer, models lookup 계층으로 분리되어 있다.

