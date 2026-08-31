# 통합 세션 FSM — 심화

> 개요는 [PROJECT_SPEC_1.0.1.md](PROJECT_SPEC_1.0.1.md) §12~13 참조.
> 이 문서는 전이 규칙·엔진 동작·주의점을 코드 수준으로 다루는 심화 문서다.

세션 전체(장비 준비 → 대기 → NR Call → 측정 → TC 간 전환 → 종료)를 하나의 상태기계로
모델링한다. 코드 위치: [src/app/core/fsm/](../src/app/core/fsm/).

## 1. 기본 계약

### State ABC — [base.py](../src/app/core/fsm/base.py)

```python
class State(ABC):
    name: str                                   # 엔진 레지스트리 키
    def enter(self, ctx) -> None: ...           # 진입 훅 (기본 no-op)
    def run(self, ctx) -> StateResult: ...      # 본 작업 (abstract)
    def exit(self, ctx) -> None: ...            # 이탈 훅 (기본 no-op)
    def next_state(self, ctx, result) -> str | None: ...  # 다음 상태 이름, None이면 FSM 종료
```

`StateResult`는 `OK / RETRY / FAIL / WAIT_USER` 4종. 상태 간 데이터 전달은 전부
`SessionContext` 경유이며, 다음 상태는 고정 시퀀스가 아니라 각 상태의 `next_state()`가
컨텍스트(현재/이전 TC, pending 전환 큐)를 보고 동적으로 결정한다.

### SessionContext — [context.py](../src/app/core/fsm/context.py)

세션 전역 dataclass. 주요 필드:

| 분류 | 필드 | 설명 |
| --- | --- | --- |
| 실행 대상 | `queue`, `current_index`, `start_index`, `stop_index` | TC 큐와 진행 위치. `stop_index` 도달 시 종료(단일 실행에 사용) |
| 외부 통신 | `commands`, `client`, `tcp_host`, `tcp_port` | `commands`는 net.commands 모듈 또는 테스트용 mock facade |
| UI 통지 | `events` | `RunnerEvents` Qt 시그널 묶음 (FSM→UI 유일 통로) |
| 리포트 | `run_preparer`, `pending_run_request`, `result_workbook_path`, `report_writer`, `temp_dir`, `screenshot_root_dir`, `model_name` | `screenshot_root_dir`는 호환성을 위해 유지한 이름으로 EUT 결과 기준 root이고, temp_dir는 LV가 스크린샷 PNG를 떨어뜨리는 위치 |
| 제어 플래그 | `paused`, `stopped`, `current_case_stop_requested` | UI 스레드가 쓰고 FSM이 폴링 |
| 측정 진행 | `current_angle`, `fundamental_frequency_mhz`, `harmonic_precision_candidates`, `settings` | 각도는 세션 전체에서 이어짐(0↔360 토글) |
| TDF 적용 | `last_applied_factor_keyword` | 마지막 적용 성공 Factor. Test Start/TestEnd에서 초기화하며 연속 중복 적용을 생략하는 데 사용 |
| Recall 적용 | `last_applied_recall_id` | 장비에 적용된 것으로 확인한 Recall ID. `PrepareReport` 성공 시 시작 TC 값으로 초기화하고 Recall+Call Check 성공 시 갱신하며 `TestEnd`에서 초기화 |
| 장비 상태 | `equipment_state` | 장비명→bool. [equipment.py](../src/app/core/fsm/equipment.py) `is_equipment_connected()`로 조회 |
| 동기화 게이트 | `equipment_connect_requested`, `test_start_requested`, `user_action_completed` (threading.Event) | UI가 set, FSM이 0.1초 폴링 대기 |
| 복합 전환 | `pending_transition_states` | CheckNextCase가 채우고 각 전환 상태가 FIFO 소비 |

### FSMEngine — [engine.py](../src/app/core/fsm/engine.py)

name→State 레지스트리를 들고 `enter → run → exit → next_state` 루프를 QThread 워커에서
동기 실행한다. 루프의 특수 처리:

- **RETRY**: `next_state()`를 호출하지 않고 **같은 상태를 enter부터 재실행**한다.
  상태의 `next_state`에 RETRY 분기를 써도 도달하지 않는다.
- **WAIT_USER**: `ctx.paused = True` 설정 후 continue — 재개 시 같은 상태를 처음부터 재실행.
- **stopped**: 루프 탈출 전 Switch Box를 안전 경로(INPUT2/THRU)로 best-effort 복원.
- **current_case_stop_requested**: Switch Box 복원 → 플래그 소비 → `Idle`로 강제 복귀
  (세션은 유지, 다음 Start 대기).
- **예외**: Switch Box 복원 후 그대로 재전파 → Runner가 `session_failed` 처리.
- **FAIL + next None**: FSM 종료 경로에서도 Switch Box 복원.

모든 상태는 `build_session_engine()`에서 싱글턴으로 등록된다.

## 2. 상태 카탈로그

### 세션 제어 — [states/session.py](../src/app/core/fsm/states/session.py)

| 상태 | 역할 | next |
| --- | --- | --- |
| `SessionInit` | `equipment_connect_requested` 대기 → client/equipment_state/`is_selected_equipment_ready` 검증 (실패 시 RETRY로 재대기) | OK→`Idle` |
| `Idle` | `test_start_requested` 대기 → pending Start 요청 확인 | OK→`PrepareReport` |
| `PrepareReport` | RawData 결과 workbook 확보 → writer 생성 → Excel live monitoring 준비. 성공할 때만 queue/settings/result path/writer를 확정하고 `start_index` 첫 TC의 Recall ID를 적용 ID로 초기화한 뒤 `tc_started` emit. 실패 시 `start_rejected` emit 후 실행 잠금 해제 | OK→`InitialTurntableZero`, 실패/Stop→`Idle` |
| `CheckNextCase` | `tc_finished` emit → 큐 끝/stop_index면 종료 플래그 → 아니면 index 증가, prev/current diff로 **전환 계획** 수립 | 아래 §4 참조 |
| `TestEnd` | `session_finished` emit, 큐/인덱스/TDF·Recall 적용 기록 리셋 | OK→`Idle` (FSM 상주) |

`PrepareReport`는 기존 FSM QThread에서 실행된다. 준비 중 Stop은 UI 호출을 막지 않지만 이미
진행 중인 openpyxl/COM 호출을 강제 중단하지 않는다. 해당 호출이 반환된 직후 Stop을 관찰해
장비 command와 측정 상태에 진입하지 않고 `Idle`로 복귀한다.

### NR/LTE 연결 — [states/nr_setup.py](../src/app/core/fsm/states/nr_setup.py), [states/lte_setup.py](../src/app/core/fsm/states/lte_setup.py)

| 상태 | 역할 | next |
| --- | --- | --- |
| `NRCallConnect` | **항상 풀 Setup + 신규 연결.** `resolve_call_channel`로 채널 산출 후 `commands.setup_mt8000(band, bw, mod, rb, channel, waiting_time)` | OK→`next_transition_or(ApplyTdf)` / FAIL→`NRCallDisconnected` |
| `NRCallDisconnected` | "비행기 모드 On/Off 후 확인" 사용자 확인 대기 | OK→`call_entry_state_for(ctx)` (NR SA/NSA=`NRCallConnect`) |
| `LTECallConnect` | 현재 TC의 BW/ARFCN/RB Offset으로 `commands.setup_lte_mt8000` 호출 | OK→`next_transition_or(ApplyTdf)` / FAIL→`LTECallDisconnected` |
| `LTECallDisconnected` | NR과 같은 "비행기 모드 On/Off 후 확인" 사용자 확인 대기 | OK→`LTECallConnect` |

Generation 분기는 [call_routing.py](../src/app/core/fsm/call_routing.py)에 집중되어 있다.
LTE는 LTE Call/Handover 상태로 진입한다. NR SA와 NR NSA의 첫 연결은 동일한 NR Call을
사용하고, 같은 Anchor의 NR 설정 변경도 기존 NR Handover를 사용한다. 첫 NSA TC의 Anchor는
장비에 미리 준비되어 있다고 간주한다.

### 시험 간 전환 — [states/transition.py](../src/app/core/fsm/states/transition.py)

| 상태 | 트리거 (prev vs current diff) | 동작 | next |
| --- | --- | --- | --- |
| `RecallChange` | 현재 TC의 `mt8000_recall`이 `last_applied_recall_id`와 다름 | `commands.recall_param` 호출 후 `commands.check_call_status`를 정확히 한 번 호출. 둘 다 성공한 경우에만 적용 ID 갱신 | OK→`next_transition_or(ApplyTdf)` / FAIL→종료 |
| `Handover` | Recall 변경이 없고 NR Call 설정(Band/BW/Channel/RB/Modulation)이 다름 | 이전 TC MID 조회 없이 현재 TC의 NR 목적지 파라미터로 `commands.call_handover` 호출 | OK→`next_transition_or(ApplyTdf)` / FAIL→`NRCallDisconnected` |
| `NSAHandover` | 연속 NSA TC의 `anchor_band`가 다름. Recall도 바뀌면 `RecallChange` 직후 실행 | 현재 TC의 NR 목적지 파라미터와 Anchor DL Channel로 `commands.nsa_handover` 한 번 호출 | OK→`next_transition_or(ApplyTdf)` / FAIL→`NRCallDisconnected` |
| `LTEHandover` | Recall 변경이 없고 LTE Call 설정(Band/BW/Channel/RB)이 다름 | 이전 TC MID 조회 없이 현재 TC의 DL/UL Channel과 설정으로 `commands.lte_call_handover` 호출 | OK→`next_transition_or(ApplyTdf)` / FAIL→`LTECallDisconnected` |
| `DUTAxisChange` | `dut_axis` 다름 | "DUT Axis 변경: X→Y" 수동 확인 | OK→`call_entry_state_for` (Generation별 풀 재연결) |
| `AntPolChange` | 편파가 다르거나 input_path의 **mast 매핑**이 다름 | `commands.set_antenna_pol(pol, input_path)` — INPUT3은 3D Controller, INPUT1/2는 CO3000 mast 2/1 | 첫 TC 초기 셋업 경로→`SetupSpectrumAnalyzerStartupLevel`, 그 외→`next_transition_or(ApplyTdf)` |
| `TestTypeChange` | `test_type`만 다름 | 장비 재설정 없이 `commands.check_call_status`만 확인 | OK→`next_transition_or(ApplyTdf)` / FAIL→Generation별 CallDisconnected |

주의: `AntPolChange`는 필요 장비(CO3000/3D Controller) 미연결 시 FAIL이 아니라
**에러 로그 후 OK(스킵)** 로 계속 진행한다. 반면 NR/LTE CallConnect, Handover,
TestTypeChange는 MT8000A 미연결 시 FAIL이다.

Recall 변경 시 Python은 LV의 고수준 `Recall Param`만 호출한다. LV가 Call 정리, Recall 적용,
재연결을 내부 처리한 Default Response를 반환하면 Python은 `Check Call Status`를 한 번 호출한다.
연결 확인 성공 후 현재 TC 설정을 NR/LTE Call로 적용한다. Recall ID와 NSA Anchor가 함께
바뀐 경우에는 NR Call 대신 기존 `NSA Handover`로 목표 NR 설정과 Anchor를 함께 적용한다.
Recall 또는 Call Check 실패 시 적용 ID를 갱신하지 않고 FSM을 종료하므로 TDF와 측정으로
진입하지 않는다. Call 단절 복구는 기존 CallConnect만 재시도하며 Recall을 재조회·재적용하지 않는다.

NSA Call 전환 결정표는 다음과 같다.

```text
첫 실행 TC (start_index 포함)  → Generation별 NR/LTE Call (Recall Param 미호출)
목표 Recall != 적용 Recall      → RecallChange → NR/LTE Call
목표 Recall 변경 + Anchor 변경  → RecallChange → NSA Handover
Recall 동일 + Anchor 변경      → NSA Handover
Anchor 동일 + NR 설정 변경     → NR Handover
그 외                          → Call 전환 없음
```

### Factor 적용 — [states/tdf.py](../src/app/core/fsm/states/tdf.py)

| 상태 | 역할 | next |
| --- | --- | --- |
| `ApplyTdf` | 현재 TC의 `factor_keyword`가 직전 적용 성공 Factor와 같으면 생략. 다르면 `get_tdf_list` 결과 전체를 `tdf_file_list_changed`로 emit하고, 대소문자를 구분해 키워드를 포함하는 단일 매칭 파일만 `set_tdf`로 적용한다. 성공 시 적용 기록을 갱신하고 `active_tdf_file_changed`를 emit한다. | OK→`measurement_start_state_for(test_type)` / FAIL→종료 |

매칭 파일이 없거나 둘 이상인 경우와 `set_tdf=False`/예외는 FAIL이다. 임시 장비 정책에 따라
FSV40 미연결 상태에서는 명령과 성공 기록 없이 OK로 스킵한다. 목록 조회가 성공했다면 이후
매칭 또는 적용에 실패해도 조회된 전체 목록은 UI에 전달한다.

### 측정 공유 스텝 — [states/measurement/common.py](../src/app/core/fsm/states/measurement/common.py)

Harmonic/InBand/Bilog가 공유한다.

| 상태 | 동작 |
| --- | --- |
| `InitialTurntableZero` | 시험 시작 전 현재 각도 조회 후 0° 또는 360°(가까운 쪽)로 speed 6 정렬 → `AntPolChange` |
| `SetupSpectrumAnalyzerStartupLevel` | `setup_sa_startup_levels(atten, next_peak_search_level)` 1회 → HARMONIC은 `PrepareFundamentalSwitchBoxBeforeCall`, 그 외는 Generation별 Call 진입 |
| `PrepareFundamentalSwitchBox(BeforeCall)` | Fundamental 측정 전 안전 경로(INPUT2/THRU) 보장 |
| `SetSwitchBox` | TestRange의 input_path + `resolve_filter_path(filter_mode, band)`로 시험 경로 설정 |
| `SetupSpectrumAnalyzer` | `setup_sa(TestRange)` (Start/Stop/RBW/VBW/SweepPoint/Limit) → saturation 대기 |
| `RotateTurntable` | 0↔360 토글 각도로 `rotate_turntable` 후 **비동기 Event** (`turntable_progress`/`turntable_complete`/`equipment_error`) 대기. 타임아웃 300초 시 `stop_turntable` 후 FAIL |
| `ResetSwitchBox` | 측정 후 INPUT2/THRU 복원 → `CheckNextCase` |

test_type별 분기 허브는 `measurement_start_state_for(test_type, after_rotate, manual_marker)`:

| test_type | 진입(after_rotate=False) | 회전 후 | 회전 후 + 수동 마커 |
| --- | --- | --- | --- |
| HARMONIC | `MeasureFundamental` | `MeasureHarmonics` | `MeasureHarmonicsManual` |
| INBAND | `SetSwitchBox` | `MeasureInBand` | `MeasureInBandManual` |
| BILOG | `SetSwitchBox` | `MeasureBilog` | `MeasureBilogManual` |

### 측정 상태 — harmonic / inband / bilog

- **Harmonic** ([harmonic.py](../src/app/core/fsm/states/measurement/harmonic.py)):
  - `MeasureFundamental` — Excel에 이미 기본파가 있으면 **측정을 생략하고 캐시 재사용**
    (같은 Band 재측정 시 기본파를 다시 재지 않음). 없으면 `measure_fundamental(target MHz)` →
    LV가 Peak Search + `fundamental.png` 저장 → `write_fundamental`.
  - `MeasureHarmonics` — `measure_harmonics(fundamental)` → 2~5차 마커 4개 수신·검증 →
    limit−10dB 초과 피크만 기록 → `write_harmonic`. amplitude ≥ limit−3dB인 마커는
    정밀측정 후보로 적재.
  - `MeasureHarmonicPrecision` — 후보별로 `setup_sa_precision(peak, 100ms sweep)` →
    턴테이블 인라인 재회전 → `measure_harmonic_precision`. 여전히 limit−3dB 이상이면
    500ms sweep으로 반복. **결과는 스크린샷만 저장하고 Excel에는 쓰지 않는다.**
- **InBand** ([inband.py](../src/app/core/fsm/states/measurement/inband.py)):
  Fundamental/Precision 없음. `measure_inband(limit−10)` → 단일 amplitude → `write_inband`.
- **Bilog** ([bilog.py](../src/app/core/fsm/states/measurement/bilog.py)): 구조는 InBand의
  미러. **LV 프로토콜 수준에서는 In-band와 완전히 동일한 명령**을 보낸다
  (`measure_bilog`는 `measure_inband`에 위임, 스크린샷 파일명도 `inband.png`).
  차이는 앱 내부 결과 타입(`BilogResult`)과 Excel 기록 위치뿐 — 챔버 실측으로 확정된 정책.

임계값 규약 두 가지: **기록 임계 = limit−10dB** (미만이면 결과 None → Excel에 "-"),
**Harmonic 정밀측정 후보 임계 = limit−3dB**. amplitude 0.0은 '수동측정 범위' 센티널로
정밀측정에서 스킵된다.

### 수동 마커 모드 — [manual_marker.py](../src/app/core/fsm/states/measurement/manual_marker.py)

`TestRunSettings.manual_marker_enabled=True`면 회전 후 `Measure*Manual` 상태로 분기한다.
흐름: LV `measure_*_manual` 명령으로 자동 마커까지 찍음 → `manual_marker_edit_required`
시그널로 UI에 다이얼로그 요청 → FSM 워커는 `user_action_completed` 폴링 블로킹 →
사용자가 SA 마커를 직접 편집(다이얼로그의 Peak/Next/OFF 버튼이 `Runner.marker_*`를 반복 호출)
→ 완료 시 SA 레벨 원복(`setup_sa_startup_levels`) → `get_screenshot`으로 편집 화면을
`screenshot.png`로 캡처 → 이 스크린샷으로 결과 기록.

## 3. 전체 흐름도

```text
SessionInit ──OK──► Idle ──Start──► PrepareReport ──OK──► InitialTurntableZero ──► AntPolChange(초기 셋업)
                                                                    │
                     ┌──────────────────────────────────────────────┘
                     ▼
        SetupSpectrumAnalyzerStartupLevel
                     │ HARMONIC                        │ INBAND/BILOG
                     ▼                                 ▼
   PrepareFundamentalSwitchBoxBeforeCall      (Generation별 Call 진입)
                     │                                 │
                     ▼                                 ▼
        NRCallConnect / LTECallConnect ◄── Generation별 CallDisconnected
                     │ OK (pending 전환 우선 소비)          ▲ FAIL 시
                     ▼                                    │
                  ApplyTdf                                │
                     │                                    │
       ┌─────────────┴────────────┐                       │
       ▼ HARMONIC                 ▼ INBAND/BILOG           │
 MeasureFundamental          SetSwitchBox                  │
       │                          │                        │
       ▼                          ▼                        │
  SetSwitchBox ──► SetupSpectrumAnalyzer ──► RotateTurntable
                                                  │
                    ┌─────────────────────────────┤ (manual_marker면 *Manual)
                    ▼                             ▼
             MeasureHarmonics              MeasureInBand / MeasureBilog
                    │ 후보 있으면                  │
                    ▼                             │
          MeasureHarmonicPrecision                │
                    └──────────┬──────────────────┘
                               ▼
                        ResetSwitchBox
                               ▼
                        CheckNextCase ──큐 끝──► TestEnd ──► Idle
                               │ 다음 TC 있음
                               ▼
        (적용 Recall ID + diff 기반 전환: RecallChange | Handover | DUTAxisChange | AntPolChange | TestTypeChange)
                               │ 전환 모두 소비 후
                               ▼
                  ApplyTdf ──► 측정 진입 상태 (전환 불필요 시 ApplyTdf 직행)
```

## 4. 복합 전환 계획과 체이닝

TC 간에 여러 파라미터가 동시에 바뀌면 `CheckNextCaseState`가
`_transition_states_for(prev, cur, last_applied_recall_id)`로 전환 상태 이름 **리스트**를 만든다.
리스트 순서 = 실행 순서:

1. 목표 Recall ID가 적용 ID와 다름 → `RecallChange` 후 Generation별 풀 Call.
   단, NSA Anchor도 바뀌면 풀 NR Call 대신 `NSAHandover`
2. Recall은 같고 NSA Anchor가 다름 → `NSAHandover`
3. Recall/Anchor는 같고 Call 설정이 다름(NR: band/BW/Channel/RB/Modulation,
   LTE: band/BW/Channel/RB) → Generation별 `Handover`
4. `dut_axis` 다름 → `DUTAxisChange`
5. 편파 셋업 필요(편파 값 또는 input_path→mast 매핑 변화) → `AntPolChange`
6. generation 다름 → TODO(spec), 현재 no-op
7. `test_type` 다름 → `TestTypeChange`

첫 항목으로 전이하고 나머지는 `ctx.pending_transition_states`에 저장한다. 이후 각 전환
상태의 `next_state`가 [transition_flow.py](../src/app/core/fsm/transition_flow.py)의
`next_transition_or(ctx, fallback)`으로 큐를 하나씩 소비해 체이닝하고, 소진되면 fallback인
`ApplyTdf`로 간다. TDF 적용이 성공하거나 임시 장비 정책으로 스킵된 뒤 시험 타입별 측정
진입 상태로 분기한다.

`RecallChange`는 pending의 첫 상태인 풀 Call 또는 `NSAHandover`를 소비한다. 이후 Call/Handover
상태의 `next_state`가 잔여 전환을 이어서 소비한다. **예외**: `DUTAxisChange`는 pending을 직접
소비하지 않고 `call_entry_state_for`(Generation별 풀 재연결)로 가며, 재연결된 Call 상태가
잔여 전환을 이어서 소비한다.

같은 Band에서도 BW/Channel/RB가 바뀌면 Generation별 `Handover`를 실행하고,
NR은 Modulation 변경도 같은 기준으로 처리한다. Call 설정이 모두 같을 때만 `ApplyTdf`로 직행한다.

## 5. UI ↔ FSM 상호작용

| 방향 | 수단 | 사례 |
| --- | --- | --- |
| FSM → UI | `RunnerEvents` 시그널 ([events.py](../src/app/core/events.py)) | `state_changed`(모든 전이), `tc_started/finished`, `progress`, `tdf_file_list_changed`, `active_tdf_file_changed`, `user_action_required`, `manual_marker_edit_required`, `*_info_changed`(SA/SwitchBox/턴테이블/편파), `screenshot_saved`, `session_finished` |
| UI → FSM | `threading.Event` set | 장비 준비(`equipment_connect_requested`), 시험 시작(`test_start_requested`), 수동 확인(`user_action_completed`) |
| UI → FSM | bool 플래그 | 정지(`stopped`), 현재 TC만 중단(`current_case_stop_requested`) |

사용자 개입 상태(LTE Anchor, 비행기 모드, DUT 축 변경, 수동 마커)는 모두
"`user_action_completed.clear()` → `user_action_required` emit → 0.1~0.2초 폴링 대기"
패턴을 따른다. 새 대기 로직을 추가할 때 `ctx.stopped` / `ctx.current_case_stop_requested`
확인을 빠뜨리면 정지 버튼이 듣지 않게 된다.

`session_finished`는 FSM(CheckNextCase→TestEnd)이 emit하지만, `session_stopped` /
`session_failed`는 Runner의 스레드 종료 훅이 emit한다 — 발신 주체가 다르다.

## 6. 신규 개발자가 놓치기 쉬운 점

- 스크린샷은 "LV가 `ctx.temp_dir`에 PNG를 남긴다"는 **파일시스템 암묵 계약**이다. 측정 상태는
  실행 전 stale 파일을 지우고 실행 후 파일 존재를 검증한다 — 파일이 없으면 측정 응답이
  성공이어도 FAIL.
- 장비 미연결 시 측정 상태들은 FAIL이 아니라 **에러 로그 후 OK(스킵)** 가 규약이다.
  이는 개발 단계 임시 정책이며 배포 정책이 아니다 (AGENTS.md 참조).
- `RotateTurntableState`는 threading.Event를 가진 stateful 싱글턴이지만,
  Harmonic 정밀측정은 등록된 인스턴스를 재사용하지 않고 **새 인스턴스를 만들어
  enter/run/exit를 직접 호출**한다. 턴테이블 이벤트는 시그널과 버퍼 양쪽에서 도착할 수
  있어 객체 identity로 dedup한다.
- NR/LTE `Handover`는 이전 TC의 MID 채널을 조회하지 않고 **현재 TC** 목적지 채널만 전달한다.
- `CheckNextCaseState`는 run 결과를 인스턴스 필드(`_previous_case`, `_advanced`)에 저장해
  `next_state`에서 쓴다(매 run마다 리셋됨).
- TODO(spec) 지점: generation 변경 전환 정책, 편파 변경 후 확인 순서, 1m Mast 각도
  readback(H→90°/V→0°는 표시용 임시 매핑), 턴테이블 이벤트 명령명 확정.

## 7. 새 시험 타입 추가 절차 (실제 코드 기준)

1. [models/enums.py](../src/app/models/enums.py) `TestType`에 값 추가,
   [band_group.py](../src/app/models/band_group.py) `RANGE_BY_BAND_TEST`에 band별 매핑 추가,
   [measurement_result.py](../src/app/models/measurement_result.py)에 결과 dataclass 추가.
2. `states/measurement/<type>.py`에 `Measure<Type>State` / `Measure<Type>ManualState` 작성
   ([inband.py](../src/app/core/fsm/states/measurement/inband.py)가 최소 템플릿).
3. [common.py](../src/app/core/fsm/states/measurement/common.py)
   `measurement_start_state_for()`의 **매핑 3개**(진입/회전후/회전후+수동)에 항목 추가.
4. [engine.py](../src/app/core/fsm/engine.py) `build_session_engine()`에 register 추가.
5. [net/commands.py](../src/app/net/commands.py)에 `measure_<type>(_manual)` facade 추가
   (+ [mock_lv_server.py](../src/app/net/mock_lv_server.py) 핸들러).
6. report 계층: `template_map.py` 레이아웃 필드/좌표 함수, `excel_writer.py`/`report_writer.py`에
   `write_<type>` 추가 ([REPORTING.md](REPORTING.md) 참조).
7. UI: [nr_select.py](../src/app/ui/nr_select.py) `_test_range_options_for_group`에
   라벨↔TestType 매핑 추가.
8. 테스트: `tests/core/test_fsm_<type>.py` (harmonic 하네스 재사용),
   `tests/core/test_fsm_routing.py` 분기 케이스, `tests/net/test_commands.py` 계약 테스트.
