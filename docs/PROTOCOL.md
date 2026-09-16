# LabVIEW 연동 TCP/JSON 프로토콜 — 심화

> 개요는 [PROJECT_SPEC_1.0.1.md](PROJECT_SPEC_1.0.1.md) §14 참조.
> 이 문서는 명령별 파라미터/응답 스키마와 단위 규약, mock 사용법을 다루는 심화 문서다.

외부 LabVIEW 프로그램(**LV Inst Manager**)과의 통신 규약과 net 계층
([src/app/net/](../src/app/net/)) 구조 문서. 이 프로토콜이 앱의 유일한 장비 제어 통로다.

## 1. 와이어 포맷 — [protocol.py](../src/app/net/protocol.py)

- **프레이밍**: `4바이트 big-endian unsigned int 길이 prefix + UTF-8 JSON 페이로드`.
  최대 페이로드 64MiB. 부분 수신 프레임은 버퍼에 보존된다(`decode_frames`).
- **메시지 3종**:

```jsonc
// Request (Python → LV)
{"type": "request", "id": "<uuid4>", "target": "FSV40", "command": "Load SA Range Setting", "Params": {...}}

// Response (LV → Python) — id로 Request와 매칭
{"type": "response", "id": "<같은 id>", "status": "ok", "Result": {...}}   // 실패 시 status!="ok" + "Error"

// Event (LV → Python, 비동기 푸시)
{"type": "event", "id": "...", "target": "CO3000", "command": "turntable_progress", "Params": {"Current Angle": 120.0}}
```

- **키 대소문자 비대칭 주의**: `type/id/status/target/command`는 소문자,
  `Params/Result/Error`는 **대문자 시작** — LabVIEW 측 규약이며
  [tests/net/test_protocol.py](../tests/net/test_protocol.py)가 키 순서까지 고정한다.
- 프로토콜 위반은 `ProtocolError`(ValueError 서브클래스).

## 2. 전송 계층 — [tcp_client.py](../src/app/net/tcp_client.py)

`TcpClient`는 QTcpSocket을 **전용 QThread**(`_SocketThread`)에 가두고 명령 큐로 구동한다.

- `connect_to(host, port, timeout=5.0)` / `disconnect_from_host()` / `close()`
- `send_request(target, command, params, timeout=30.0) -> Response` —
  uuid4 id로 Request를 만들고 Response를 id 매칭으로 기다리는 **완전 동기(블로킹)** API.
  UI 스레드에서 직접 부르면 이벤트 루프가 멈춘다(FSM 워커/서비스 워커에서 호출이 전제).
  단, RF Switch Box 수동 명령 등 짧은 호출은 예외적으로 UI 스레드에서 동기 실행한다.
- **비동기 Event 이중 전달**: 수신된 Event는 (1) `event_received` 시그널 방출과
  (2) 내부 deque 버퍼(maxlen=1000) 적재 두 경로로 전달된다. 소비자는
  `event_received` 연결(DirectConnection — 소켓 스레드에서 실행됨에 주의) +
  `pop_events(predicate)` 폴링을 병용한다. 같은 Event가 양쪽으로 올 수 있어
  소비 측에서 dedup이 필요하다.
- 타임아웃 → `TcpClientTimeoutError`, 연결/쓰기 실패 → `TcpClientError`. **재시도는 없다**
  (NR Call의 Max Retry Count는 LV 측 재시도 파라미터).

## 3. 명령 카탈로그 — [commands.py](../src/app/net/commands.py)

`commands.py`는 FSM이 호출하는 고수준 facade이자 **target/command 문자열과 파라미터 스키마의
단일 진실 공급원**이다. 응답 status가 "ok"가 아니거나 판정 대상 `Result.ok`가 `false`이면
`CommandError`를 던진다. 일반 action facade는 성공 시 `True`를 반환하지만,
`connect_equipment`는 장비별 연결 결과를 bool dict로 반환하고 `check_call_status`와
`recall_param`은 `Result.connected`에 따른 최종 Call 연결 상태를 bool로 반환한다.

### 연결

| facade | target / command | Params | 응답 |
| --- | --- | --- | --- |
| `connect_equipment(client, config)` | 각 장비 / `Connect` | VISA 장비: `{"VISA Resource"}`, Switch Box: `{"ip address", "port"}` | 장비별 bool dict |

### MT8000A (NR/LTE Callbox)

| facade | command | Params 요점 |
| --- | --- | --- |
| `setup_mt8000` | `NR Call` | Band, BandWidth, Center Channel, RB Size/Offset, Modulation(`pi/2 BPSK`→와이어 `PI/2 BPSK`), Max Retry Count(기본 3), Waiting Time(기본 5) |
| `setup_nsa_mt8000` | `NSA Call` | NR Call 8개 필드 + Anchor UL Channel을 flat Params로 전송 |
| `call_handover` | `NR Handover` | Band, BandWidth, Center Channel, RB Size/Offset, Modulation, Max Retry Count(기본 3), Waiting Time(기본 5) |
| `nsa_handover` | `NSA Handover` | 기존 NR Call 8개 필드 + Anchor UL Channel |
| `setup_lte_mt8000` | `LTE Call` | BandWidth(문자열), UL Channel, RB Offset, Max Retry Count(기본 3), Waiting Time(기본 5) |
| `lte_call_handover` | `LTE Handover` | BandWidth(문자열), DL Channel, UL Channel, RB Offset, Max Retry Count(기본 3), Waiting Time(기본 5) |
| `recall_param` | `Recall Param` | `{"Recall Name": "<TestCase.mt8000_recall>"}` 단일 필드 → Result `{ok, connected}` |
| `check_call_status` | `Check Call Status` | NR/LTE 공용 → Result `{ok, connected}` |

#### Recall Param Interface Contract (H2026E014-47)

Python은 Recall 파일 이름만 `MT8000A / Recall Param`으로 전달한다. LV는 Call 정리,
Recall 적용, Call 재연결과 최종 Call Check를 내부에서 모두 처리한다.

```jsonc
// Request Params
{"Recall Name": "5GNR_SA_TDD"}

// Success
{"type": "response", "id": "<same id>", "status": "ok", "Result": {"ok": true, "connected": true}}

// Failure
{"type": "response", "id": "<same id>", "status": "error", "Error": {"message": "..."}}
```

`Recall Name`에는 MT8000A Parameter Recall 파일명에서 `.PRM` 확장자를 제외한 값을
전달한다.

Python은 `Result.ok=true`를 요구하고 `Result.connected`를 Call 연결 결과로 사용한다.
별도 `Check Call Status`는 호출하지 않는다. 연결 성공 후 현재 Test Case 설정은 기존
`NR Call`/`LTE Call`로 적용하며, Recall과 NSA Anchor가 함께 변경된 경우에는 `NR Call`
대신 `NSA Handover`를 사용한다. Python은 LV primitive를 직접 호출하거나 조합하지 않는다.

LTE `BandWidth`는 LabVIEW enum 변환을 위해 단위 없는 문자열 `"1.4"`, `"3"`, `"5"`, `"10"`, `"15"`, `"20"` 중 하나로 전송한다.

#### NSA Call Interface Contract (H2026E014-66)

첫 실행 Test Case가 NR NSA이면 Python은 `MT8000A / NSA Call` request 하나를 보낸다.
`start_index > 0`에서 선택한 첫 실행 NSA TC와 NSA 풀 재연결에도 같은 정책을 적용한다.
`Params`는 다른 MT8000A command와 동일하게 wrapper 없는 flat 구조이며, 필드 구성은
현재 `NSA Handover`와 동일한 9개다.

```json
{
  "Band": 78,
  "BandWidth": 100,
  "Center Channel": 636666,
  "RB Size": 135,
  "RB Offset": 67,
  "Modulation": "QPSK",
  "Anchor UL Channel": 18300,
  "Max Retry Count": 3,
  "Waiting Time": 5
}
```

`NSA Call`과 `NSA Handover`는 동일한 flat Params 필드 구성을 사용한다. Anchor UL Channel은 아래의 기존
MID/5 MHz lookup을 재사용하며 Anchor Band나 DL Channel 등 추가 Anchor 필드는 보내지 않는다.

응답은 Default Response 계약을 사용한다. Python은 `status`만 판정하고 `Result`의
유무·타입·내용에는 의존하지 않는다.

#### NSA Handover Interface Contract (H2026E014-36)

Python은 이전에 실행한 NSA TC와 Anchor Band가 달라진 경우에만
`MT8000A / NSA Handover` request 하나를 보낸다. 첫 NSA TC는 H2026E014-66에 따라
`MT8000A / NSA Call`을 사용한다.
SCG Release, Anchor Handover, 내부 NR Call 및 최종 상태 확인은 LV composite의 책임이며,
Python이 `NR Call`이나 장비 primitive를 추가로 조합하지 않는다.

정확한 `Params`는 다음 9개다. 앞의 8개는 기존 `NR Call`과 같은 필드이며,
신규 wire 필드는 `Anchor UL Channel` 하나뿐이다. `Max Retry Count=3`과
`Waiting Time=5`도 기존 기본값을 그대로 사용한다.

```json
{
  "Band": 78,
  "BandWidth": 100,
  "Center Channel": 636666,
  "RB Size": 135,
  "RB Offset": 67,
  "Modulation": "QPSK",
  "Anchor UL Channel": 18300,
  "Max Retry Count": 3,
  "Waiting Time": 5
}
```

다음 Anchor 정보는 보내지 않는다: `Anchor Band`, `DL Channel`, Anchor `BandWidth`,
`RB Size`, `RB Offset`, `Modulation`, `Test Channel`. Anchor는 MID/5 MHz 고정 기준이며
지원 Band와 채널은 다음과 같다.

| Anchor Band | Anchor UL Channel |
| --- | ---: |
| B1 | 18300 |
| B3 | 19575 |
| B7 | 21100 |
| B5 | 20525 |
| B8 | 21625 |
| B20 | 24300 |
| B28 | 27385 |
| B38 | 38000 |
| B40 | 39150 |
| B41 | 40620 |

`B34`와 표에 없는 Band는 지원하지 않는다. Python lookup의 UL/DL 값은 기존 LTE
MID/5 MHz lookup과 일치해야 한다. Wire에는 위 UL 값만 넣고 DL 값은 전송하지 않는다.

응답은 Default Response 계약을 사용한다. Python은 최종 `status`만 판정하며 `Result`가
없거나 어떤 형식으로 존재하더라도 무시한다. 성공 시 `status="ok"`, 실패 시
`status="error"`와 `Error.message`만 요구한다. 성공 read-back이나 단계별 상태를 담은
`Result`, 또는 별도 failure envelope는 필수가 아니다.

```jsonc
{"type": "response", "id": "<같은 id>", "status": "ok"}
{"type": "response", "id": "<같은 id>", "status": "error", "Error": {"message": "..."}}
```

### FSV40 (Spectrum Analyzer)

| facade | command | 비고 |
| --- | --- | --- |
| `setup_sa(test_range)` | `Load SA Range Setting` | Start/Stop Frequency, RBW, VBW, Sweep Point, Limit |
| `setup_sa_startup_levels` | `Load SA Level Setting` | Atten Level, Next Peak Search Level |
| `setup_sa_precision` | `Load SA Precision Setting` | Peak Frequency, Sweep Time — **Python 인자 ms → 와이어 초** |
| `self_align_fsv40` | `Self Alignment` | 완료는 `self_alignment_complete` Event |
| `measure_fundamental` | `Search Fundamental Frequency` | Center Frequency(MHz) → Result Hz를 MHz로 환산 반환. LV가 `fundamental.png` 저장 |
| `measure_harmonics` / `measure_harmonic_manual` | `Mark Harmonic` / `Measure Harmonic` | → Amplitude[4]+Frequency[4](Hz) → 2~5차 `HarmonicMarker` 리스트 (개수 4 강제) |
| `measure_harmonic_precision` | `Mark Precision` | → Amplitude |
| `measure_inband` / `measure_inband_manual` | `Mark Inband` / `Measure Inband` | Limit 전달 → Amplitude. LV가 `inband.png` 저장 |
| `measure_bilog` / `measure_bilog_manual` | (In-band에 위임) | **Bilog 전용 LV 명령 없음** — alias |
| `get_screenshot` | `Get Screenshot` | LV가 temp/`screenshot.png` 저장 |
| `marker_peak/next/off`, `marker_all_off` | `Marker Peak/Next/OFF`, `Marker ALL OFF` | Marker Index, Excursion — 수동 마커 다이얼로그용 |
| `get_tdf_list` / `tdf_all_off` / `set_tdf` | `Get TDF List` / `TDF All Off` / `Set TDF` | TDF(FSV Factor) 파일 관리 |

### CO3000 (Turntable) / Switch Box / 편파

| facade | target / command | 비고 |
| --- | --- | --- |
| `rotate_turntable` | CO3000 / `Move TurnTable` | Target Angle, Speed, Fetch Interval=10(고정). 완료는 Event로 수신 |
| `stop_turntable` | CO3000 / `Stop TurnTable` | |
| `get_turntable_angle` | CO3000 / `Get TurnTable Angle` | → Current Angle (0~360 검증) |
| `set_reference_co3000` | CO3000 / `Set Reference` | 완료는 `set_reference_complete` Event |
| `set_switch_input/filter/box` | Switch Box / `Set Input`/`Set Filter`/`Set Path` | Input Path / Filter Path (int) |
| `set_antenna_pol(pol, input_path)` | INPUT3→`3D Controller`, INPUT1/2→CO3000 / `Change Ant Pol` | **INPUT1→Mast Index 2, INPUT2→Mast Index 1** (직관과 반대 주의) |

### 비동기 Event 목록

| Event command | target | 의미 |
| --- | --- | --- |
| `turntable_progress` | CO3000 | 회전 진행 (`Current Angle`) — 0.1초 스로틀로 UI 갱신 |
| `turntable_complete` | CO3000 | 회전 완료 |
| `set_reference_complete` | CO3000 | Set Reference 완료 |
| `self_alignment_complete` | FSV40 | Self Alignment 완료 |
| `equipment_error` | (해당 장비) | `Params.message`에 사유 — 대기 중이던 소비자가 실패 처리 |

### 단위 규약

- 주파수: **요청은 MHz, LV 응답은 Hz** → Python이 MHz로 환산해 내부는 MHz로 통일.
- Sweep Time: Python 인자 ms → 와이어에서는 초.
- 스크린샷: 응답에 실리지 않고 **LV가 temp 디렉터리에 PNG 파일을 남기는
  파일시스템 사이드채널**이다 (`fundamental.png`/`harmonic.png`/`precision.png`/
  `inband.png`/`screenshot.png`).

명령 문자열이 [commands.py](../src/app/net/commands.py)와
[mock_lv_server.py](../src/app/net/mock_lv_server.py)에 중복 정의되어 있으므로
(enum화는 TODO(spec)) 명령 추가/변경 시 두 곳을 함께 고쳐야 한다.
[tests/net/test_commands.py](../tests/net/test_commands.py)가 command 문자열과 파라미터
키를 리터럴로 고정하고 있어 사실상 **LabVIEW와의 계약 문서** 역할을 한다.

## 4. LV 서버 프로세스 관리 — [lv_server_process.py](../src/app/net/lv_server_process.py)

`LvServerManager`가 `LV Inst Manager/LV Inst Manager.exe`를 관리한다.

- `ensure_running()`: 자기가 띄운 프로세스가 살아 있으면 재사용, 아니면 숨김 창
  (`CREATE_NO_WINDOW` + `SW_HIDE`)으로 기동 후 포트(기본 127.0.0.1:5025)가 열릴 때까지
  최대 10초 폴링. **포트를 다른 프로세스가 선점 중이면 재사용하지 않고 `LvServerError`**.
- `restart()`: 종료 → 포트 해제 대기 → 재기동. TCP transport 오류로 연결 실패 시
  연결 워커가 1회 재시도 트리거로 사용.
- LabVIEW가 늦게 띄우는 프론트 패널까지 잡기 위해 데몬 스레드가 10초간 pid/exe 경로가
  일치하는 창을 폴링하며 숨긴다(pywin32).
- **자동 생성 조건**: Runner는 `sys.frozen`(PyInstaller 패키징 실행)일 때만
  LvServerManager를 만든다. 개발 환경(`uv run`)에서는 LV 서버 자동 기동이 없으므로
  mock 서버를 직접 띄워야 한다 (§5).
- 상시 watchdog은 없다 — `is_running` 프로퍼티(poll 기반)만 제공.

## 5. Mock 3종 구분

| 모듈 | 용도 | 특징 |
| --- | --- | --- |
| [mock_server.py](../src/app/net/mock_server.py) | pytest 픽스처용 저수준 스텁 | 도메인 로직 없음. `enqueue_response`로 응답 스크립팅, `send_event`로 Event 푸시. port=0이면 OS 임의 포트 |
| [mock_lv_server.py](../src/app/net/mock_lv_server.py) | **모의 LabVIEW 서버** (수동 실행 + 통합 테스트) | 장비 상태 유지, 측정값 회신, 턴테이블 회전 Event 시뮬레이션, 스크린샷 PNG 생성. NSA Call/Handover 실패 시나리오 제공 |
| [mock_lv_client.py](../src/app/net/mock_lv_client.py) | commands facade 수동 검증 콘솔 | `lv>` REPL — `connect`, `setup-mt8000`, `setup-nsa-mt8000`, `measure-fundamental target_freq=3550`, `rotate angle=60 wait=true`, `raw` 등 |

개발 환경에서 실장비 없이 앱을 돌리는 방법:

```bash
# 터미널 1: 모의 LabVIEW 서버 (기본 127.0.0.1:5025)
uv run python -m app.net.mock_lv_server --temp-dir temp

# 터미널 2: 앱
uv run python -m app
# Instrument Check에서 아무 VISA 주소나 입력 후 Connect → mock이 전부 연결 성공으로 응답
```

시나리오 옵션 예: `--scenario turntable-error`, `--turntable-delay-sec 0.1`,
`--screenshot-fixture-dir <실제 SA 캡처 폴더>` (없으면 1x1 투명 PNG 생성).

콘솔 클라이언트: `uv run python -m app.net.mock_lv_client --host 127.0.0.1 --port 5025`.
LTE Call/Handover 수동 검증 예:

```text
lv> setup-lte-mt8000 bw=20 ul_channel=18100 rb_offset=0
lv> check-call-status
lv> lte-handover bw=20 dl_channel=500 ul_channel=18500 rb_offset=99 max_retry_count=7 waiting_time=11
lv> check-call-status
```

NSA Call/Handover 수동 검증 예:

```text
lv> setup-nsa-mt8000 band=78 bw=100 modulation=QPSK rb_size=135 rb_offset=67 channel=636666 anchor_ul_channel=18300
lv> nsa-handover band=78 bw=100 modulation=QPSK rb_size=135 rb_offset=67 channel=636666 anchor_ul_channel=18300
```

Mock은 외부 primitive command를 추가하지 않고 composite 내부 상태만 재현한다. 정상 완료는
`8000A=8`, `8821C=6`이며 Result 없는 Default OK를 반환한다. 실패 시 도달한 단계의
부분 상태와 Anchor/목표 NR 설정을 보존하고 `Error.message`만 있는 Default Error를 반환한다.

| `--scenario` | 실패 지점 | 보존되는 REM_DEST 상태 |
| --- | --- | --- |
| `nsa-scg-release-error` | SCG Release 장비 오류 | `8000A=9`, `8821C=None` |
| `nsa-scg-release-timeout` | SCG Release timeout | `8000A=9`, `8821C=None` |
| `nsa-anchor-handover-error` | Anchor Handover 장비 오류 | `8000A=6`, `8821C=13` |
| `nsa-anchor-handover-timeout` | Anchor Handover timeout | `8000A=6`, `8821C=13` |
| `nsa-anchor-profile-mismatch` | Anchor profile 불일치 | `8000A=6`, `8821C=6` |
| `nsa-nr-call-error` | 내부 NR Call 장비 오류 | `8000A=7`, `8821C=6` |
| `nsa-nr-call-timeout` | 내부 NR Call timeout | `8000A=7`, `8821C=6` |
| `nsa-final-status-timeout` | 최종 상태 확인 timeout | `8000A=7`, `8821C=6` |

`NSA Call`은 `nsa-call-error`와 `nsa-call-timeout` 시나리오에서 각각 장비 오류와
workflow timeout을 Default Error로 반환하며 성공 상태를 적용하지 않는다.


## 6. 함정 정리

- 와이어 키 대소문자 비대칭 (`Params`/`Result`/`Error`만 대문자 시작).
- `connect_equipment`만 실패를 False로 반환하고 나머지 facade는 예외(CommandError)를 던진다.
- Event 버퍼는 deque(maxlen=1000)라 폭주 시 오래된 이벤트가 조용히 유실된다.
- `disconnect_from_host()` 후에도 `_ensure_thread`가 다음 `send_request`에서 스레드를
  재생성하지만 소켓은 재연결되지 않아 "not connected" 오류가 난다.
- InputPath→Mast Index 매핑이 직관과 반대(INPUT1→2, INPUT2→1)다.
- mock_lv_server의 timeout 시나리오는 에러 Event조차 보내지 않는다(소비자 타임아웃 검증용).
- 실기 LV 서버 대상 통합 테스트는 사용자 명시 승인 필요 — 저장소의 모든 net 테스트는
  loopback(port=0)만 사용한다.
