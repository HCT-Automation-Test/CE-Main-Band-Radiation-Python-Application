# v3.0 개발 요구사항 PM 검토 및 후속 Agent 인수인계

> 이 문서는 최종 개발 요구사항 명세서(SRS/PRD)나 Jira 백로그가 아니다.  
> 요구사항 관리 Agent가 명세를 작성하고 Jira 관리 Agent가 실행 가능한 백로그를 만들 수 있도록, 사용자 입력과 현재 구현의 차이, 확정 정책, 구현 의존성과 후보 작업 묶음을 정리한 PM 검토 자료다.

## 1. 문서 정보와 사용 원칙

| 항목 | 내용 |
|---|---|
| 계획 대상 | v3.0(사용자 지정 작업명) |
| 검토 기준일 | 2026-08-24 (Asia/Seoul) |
| Anchor/Command 계약 정정 | 2026-08-24 — MID/5 MHz/RB Size 1/RB Offset 0/QPSK, Band→UL/DL lookup, `DLCHAN` 전용 HO, LV 내부 NR Call helper 재사용 단일 composite 반영 |
| 저장소 기준 | `main` / `7a80d3cdead2b46ac7f7f1fc4055a0ed1b8d31ca` |
| 작업 트리 | 검토 시작 시 clean |
| 검토 방식 | 코드, 문서, 테스트 코드, Git 이력의 정적 검토 |
| 실행 검증 | 수행하지 않음 |
| 실제 LabVIEW 검증 | 소스와 승인된 장비 환경이 없어 수행하지 않음 |

### 1.1 이 문서에서 구분하는 정보

| 표기 | 의미 | 후속 Agent 처리 |
|---|---|---|
| 확정 입력 | 사용자가 이번 요청에서 명시한 동작 | 명세의 원문 추적 대상으로 사용 |
| 현행 | 현재 `main` 코드에서 확인한 동작 | 변경 전 기준선으로 사용 |
| PM 권고 | 의존성·위험을 줄이기 위한 계획 제안 | 제품/기술 담당자 승인 전 요구사항으로 단정하지 않음 |
| 기술 설계 | 제품 Outcome은 확정됐지만 내부 구현 방식과 수치가 남은 항목 | 구현 Issue의 subtask·interface contract·DoD로 관리 |

이 문서의 `PM-*` 코드는 추적 편의를 위한 임시 Capability 코드다. 최종 SRS ID나 Jira Issue Key로 사용하지 않는다.

### 1.2 자료 우선순위

이번 v3.0 정리에서는 다음 순서로 자료를 해석한다.

1. 이번 대화에서 제공된 v3.0 상세 요구사항과 예상 작업 사항
2. 현재 `main`의 실제 코드
3. `AGENTS.md`의 아키텍처·책임 경계·임시 장비 정책
4. 현재 심화 문서
5. 과거 계획 문서 `NEXT_VERSION_SRS_AND_JIRA_BACKLOG.md`

과거 계획 문서는 Recall 요구사항의 출처로는 유효하지만, LTE와 TDF가 아직 미구현이던 시점의 상태와 미완료 체크박스를 포함하므로 현재 구현 현황 자료로 사용하면 안 된다.

### 1.3 테스트 실행 제약

- 이 PM 검토에서는 `pytest`를 포함한 테스트를 실행하지 않았다.
- 요구사항 정리와 Jira 백로그 생성 작업도 테스트 실행을 필요로 하지 않는다.
- 후속 구현 검증은 사용자와 실행 환경을 확인한 뒤 관련 범위만 대상으로 진행한다.
- 다른 작업 창 종료 문제가 있으므로 전체 `pytest`를 기본 검증으로 무조건 실행하지 않는다.
- 실제 LabVIEW/실장비 시험은 별도 승인된 환경과 작업으로 분리한다.

## 2. Executive Summary

v3.0은 다음 세 Epic 후보로 정리할 수 있다.

1. NSA 정식 지원
2. 시험 운영 편의 개선
3. Standalone Manual Test

개발 우선순위는 **NSA 정식 지원이 1순위**다. 현재 확정사항으로 NSA SRS와 Jira 백로그를 작성할 수 있다. Standalone Manual Test의 command/payload/workflow 세부 계약은 확정 정책대로 Manual Test 개발 착수 시 해당 구현 Issue 안에서 Refinement한다.

NSA 우선 개발의 주요 작업축은 다음 두 가지다.

1. NSA TestCase의 Anchor Band property·CSV·결과 매핑
2. 확정된 MT8000A 고수준 workflow의 TCP/JSON 계약을 구현하고 terminal 상태 polling을 벤치에서 검증

EUT 기반 RawData 파일 lifecycle은 운영 편의 Track의 선행축이다. 기준 양식은 이미 `resources/templates`에 있으며, 남은 일은 asset 추적·검증, runtime resolver, 기존 결과 파일 lifecycle이다. 이 Track은 NSA 도메인·UI·FSM 전체의 착수 blocker가 아니다.

### 2.1 현재 상태 요약

| 영역 | 현재 상태 | v3.0 핵심 Delta |
|---|---|---|
| NR SA | Harmonic/In-band/Bilog 자동시험 경로 구현 | 생성 화면을 LTE형 통합 화면으로 개선 |
| NR NSA | Generation 구분, 수동 LTE Anchor 확인, NSA Excel 영역, SA/NSA 스크린샷 분리까지 구현 | Anchor-aware TestCase, 자동 SCG 전환, Anchor 결과 기록 |
| LTE | 모델, 생성 UI, Call/Handover, 결과 기록이 현재 코드에 존재 | 직접 개발 대상 아님. NSA UI와 Anchor 데이터의 참고 기반 |
| TDF | Band Group 기반 자동 적용 구현 | 기존 동작 유지 |
| MT8000A Recall | 식별자 파생과 TC 간 변경 감지는 존재하나 실제 변경은 수동 팝업 | 첫 실행 TC의 Recall ID를 세션 초기값으로 간주하고 이후 ID 변경 시에만 고수준 Recall Change 수행 |
| RawData | 사용자가 Excel 파일을 직접 선택하고 해당 파일을 in-place 수정 | EUT Name 기반 자동 탐색·재사용·양식 복사 |
| Manual Marker | 자동시험 FSM에 결합된 수동 마커 다이얼로그 존재 | Standalone Manual Test와는 별개이며 일부 UI/명령만 재사용 |
| Manual Test | 내비게이션과 빈 패널만 존재 | SA/Marker/Turntable/Mast/Semi Auto/Capture 전체 개발 |
| Range | Range 1~6의 완전한 장비 설정 모델 | Range 7~9는 v3.0 필수 범위에서 제외하며 후속 요구가 생길 때 다시 판단 |
| 실제 LV | 실행 파일만 있고 소스는 저장소에 없음 | Python Issue와 별도 LV Issue 및 벤치 검증 필요 |

### 2.2 이번 검토에서 확정된 정책

| 정책 ID | 확정 내용 | 명세·백로그 반영 |
|---|---|---|
| POL-NSA-01 | 모든 NR Band는 지원 Anchor Band `B1/B3/B7/B5/B8/B20/B28/B38/B40/B41`과 모두 조합할 수 있다. 별도 NR–Anchor 허용 조합표를 두지 않는다. | Anchor allowlist만 검증하고 NR–Anchor 조합 제한은 두지 않는다. |
| POL-NSA-02 | 한 실행 세션에서 `NR_SA`, `NR_NSA`, `LTE`를 혼용하지 않는다. 두 종류 이상이 섞인 Queue는 LTE 혼용 검증과 같은 시점인 시험 시작 단계에서 차단한다. | 기존 validator가 SA/NSA를 같은 NR family로 허용하는 동작을 변경한다. 세대 간 전환 FSM은 이번 범위에서 만들지 않는다. |
| POL-NSA-03 | NSA 생성 화면은 NR Band 열 옆에 LTE Anchor Band 선택 열을 둔다. LTE Anchor는 모든 Band에서 Test Channel `MID`, Bandwidth `5 MHz`, RB Size `1`, RB Offset `0`, Modulation `QPSK`로 고정하며 별도로 입력받지 않는다. | Python의 Anchor 파생 책임은 `Anchor Band → UL/DL Channel` lookup뿐이다. 고정 profile은 command Params로 보내지 않으며 LV가 내부 read-back으로 검증한다. |
| POL-MT-01 | `CALLSTAT?`는 `REM_DEST`별 상태 머신으로 해석한다. SCG Release 완료는 `8000A == 6`, NSA 연결 완료는 `8000A == 8`, Anchor 연결 유지는 `8821C == 6`으로 판정한다. | `7/9/13` 과도 상태 관측을 성공 조건으로 요구하지 않고 각 단계의 최종 상태를 polling한다. `8821C == 6`만으로 SCG Release 완료를 판정하지 않는다. |
| POL-MT-02 | NSA TC 전환에서 Anchor가 같으면 기존 `NR Handover`를 사용한다. 첫 NSA TC 또는 Anchor가 바뀌면 신규 고수준 `NSA Handover` 단일 composite를 호출한다. LV는 SCG Release → LTE Anchor `DLCHAN` 변경·고정 profile 검증 → 기존 NR Call helper 재사용 → SCG Addition·최종 상태 확인을 수행한다. | Python은 `NSA Handover` 한 번만 호출하며 `NR Call` 또는 `CALLSO`/`CALLSA`/`CALLSTAT?`/`REM_DEST` 순서를 조합하지 않는다. 기존 `NR Call` 외부 request는 현행을 유지한다. |
| POL-MT-03 | `Recall Change`는 NSA Handover와 분리된 고수준 LV workflow다. 첫 실행 TC에는 Recall을 호출하지 않고 그 TC의 ID를 세션 초기값으로 사용하며, 이후 ID가 바뀔 때만 실행하고 성공 후에만 적용 ID를 갱신한다. | `start_index > 0`이면 해당 TC를 첫 실행 TC로 본다. Call 단절 시 Recall은 유지된 것으로 보고 기존 Call만 재실행하며 신뢰 가능한 조회 방법 전에는 현재 Recall 조회를 요구하지 않는다. |
| POL-MT-04 | 외부 API 경계는 기존 `NR Call`, 신규 `NSA Handover`, 신규 `Recall Change`, 기존 `Check Call Status`의 의미 기반 workflow다. | LV helper는 매 단계 `REM_DEST`를 명시한다. `NSA Handover`는 Default Response를 사용하고 Python은 최종 `status`만 판정한다. |
| POL-RAW-01 | RawData 결과 파일의 논리 경로는 `{Screenshot 저장 기준 경로}/{EUT Name}/{EUT Name}_CE Main_Radiation_{NR|LTE}.xlsx`다. `NR` 파일은 NR SA/NSA에, `LTE` 파일은 LTE에 사용한다. | 예: `.../DUT-A/DUT-A_CE Main_Radiation_NR.xlsx`. EUT Name의 안전한 경로 변환·검증은 resolver 구현 범위다. |
| POL-RAW-02 | NR SA/NSA source는 `resources/templates/NR_Rawdata_.xlsx`, LTE source는 `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx`다. | 두 asset은 현재 worktree에 존재한다. source 수령은 더 이상 blocker가 아니며 추적·검증·runtime lookup을 구현한다. |
| POL-MAN-01 | 자동시험과 Standalone Manual Test의 장비 조작에는 Filter Box와 동일한 배타 정책을 적용한다. 한쪽이 장비 operation을 소유하는 동안 다른 쪽의 장비 조작은 시작할 수 없다. | 경쟁 장비 command 미전송과 busy 안내를 Acceptance Criteria에 포함한다. 기존 guard 확장 또는 신규 coordinator 여부는 설계에서 정한다. |
| POL-MAN-02 | Range 7~9 세부사항은 이번 v3.0 계획에서 고려하지 않는다. 필요하지 않으면 Range 모델과 Manual preset에 추가하지 않아도 된다. | Range 7~9 구현 Issue는 생성하지 않는다. 추후 WCDMA/GSM 또는 Manual 요구가 생기면 별도 Refinement한다. |
| POL-MAN-03 | Screenshot 목록에는 현재 앱 실행 세션에서 성공적으로 생성된 파일만 최신순으로 표시한다. | 시작 시 저장 폴더 전체를 스캔하지 않는다. 해당 세션에서 생성되지 않은 기존 파일은 목록에 넣지 않는다. |
| POL-PRIO-01 | Manual Test 명령명, payload, Python workflow, LV 복합 명령 단위 등 상세 계약은 Manual Test 개발 시 논의해 확정하며, NSA 개발을 우선한다. | 현재의 제품 미결정이나 NSA blocker로 관리하지 않고 Manual 구현 Issue의 Refinement 범위로 둔다. |

RawData filename의 `*` 표기는 Markdown 강조 기호로 해석했으며 실제 파일명 문자로 사용하지 않았다. 이 문서의 canonical filename은 `{EUT Name}_CE Main_Radiation_{NR|LTE}.xlsx`다.

### 2.3 SRS와 Jira 작성 기준

현재 확정사항으로 NSA/Recall과 RawData의 SRS 및 Jira Issue를 작성할 수 있다. 추가 제품 결정이나 별도 Discovery Issue를 선행 blocker로 두지 않는다.

- 첫 NSA TC는 신규 `NSA Handover` 단일 composite로 선택된 LTE Anchor를 자동 준비하고 내부 NR Call helper로 NR SCG를 연결한 뒤, 측정 전에 `8000A == 8`과 `8821C == 6`을 확인해야 한다.
- Recall ID와 Anchor Band가 함께 바뀌면 목표 Recall과 Anchor를 모두 적용하고 NSA 최종 연결 상태를 복구해야 한다. 세부 단계 순서는 `Recall Change` LV 구현 Issue에서 설계·검증한다.
- RawData는 기존 결과 파일이 있으면 재사용하고 없으면 확정 source template을 복사한다. 경로 안전성, 파일 열림·손상, resource lookup과 packaging은 RawData 구현 Issue의 예외처리·검증 범위다.

실제 TCP/JSON 명칭·필드, LV helper 순서, timeout·polling·retry 수치와 파일 처리 알고리즘은 관련 구현 Issue의 interface contract·subtask·DoD로 관리한다. 성공 판정은 확정된 terminal 상태 polling을 사용하며 별도의 stable-state 요구는 만들지 않는다. Manual Test 상세 계약은 확정 정책대로 Manual Test 착수 시 관련 구현 Issue에서 Refinement한다.

SRS와 Jira Acceptance Criteria는 자동 수행 여부, 최종 상태, 결과 파일, 실패 응답처럼 외부에서 확인 가능한 결과를 기준으로 작성한다.

## 3. 현행 시스템과 변경 경계

### 3.1 시스템 책임 구조

```text
PySide6 UI
  ├─ Test Manager ──► Runner / Session FSM ──► net.commands ──► TCP/JSON ──► LabVIEW ──► 장비
  │                                      └──► report ──► RawData Excel / Plot PNG
  ├─ Instrument Check ──► InstrumentConnectionService ──► 공용 TcpClient
  ├─ RF Filter Box ──► RFSwitchBoxService ───────────────► 공용 TcpClient
  └─ Manual Test(현재 빈 패널) ──► 신규 ManualTestService 후보 ──► 공용 TcpClient
```

Python은 UI, orchestration, 파일 관리와 결과 작성을 담당한다. 장비의 VISA/SCPI 제어는 LabVIEW가 담당한다. Manual Test의 FSV40 `*RST` 요구도 Python이 SCPI를 직접 보내는 방식이 아니라, Python의 고수준 TCP 명령을 받은 LabVIEW가 수행해야 한다.

### 3.2 유지해야 할 기존 정책

- 계층 방향은 `ui -> core -> (net | report)`를 유지한다.
- Python은 장비 제어 목적으로 VISA session을 열거나 SCPI를 직접 보내지 않는다.
- Python은 MT8000A primitive를 직접 순서 제어하지 않고 기존 `NR Call`과 신규 `NSA Handover`·`Recall Change` 고수준 LV workflow를 호출한다.
- LV workflow는 각 단계에서 `REM_DEST`를 명시하고 해당 상태 머신의 terminal 상태를 polling한다.
- Bilog는 In-band와 동일한 LV 측정 command인 `FSV40 / Mark Inband`와 `temp/inband.png`를 사용한다.
- Harmonic/In-band/Bilog의 완성된 공통 측정 로직은 NSA Call 전환 요구만으로 수정하지 않는다.
- Manual Test는 TestCase, Call 상태, Switch Box Filter 설정에 종속시키지 않는다.
- Mast 높이 조절은 v3.0 Manual Test 범위에서 제외한다.
- Semi Auto는 Single Sweep와 자동 Screenshot을 수행하지 않으며, 완료 후 Max Hold를 유지한다.
- `NR_SA`, `NR_NSA`, `LTE`가 섞인 실행 Queue는 시험 시작 단계에서 차단한다.
- Manual 장비 operation과 자동시험 장비 operation은 Filter Box와 같은 배타 정책을 적용한다.
- Range 7~9는 v3.0 필수 범위가 아니며 현재 Range 모델에 추가하지 않아도 된다.
- WCDMA/GSM Test Case와 자동시험 구현은 이번 범위가 아니다.
- `src/app/ui/generated/**`는 직접 수정하지 않는다. 이번 대상 화면은 현재 Python 코드로 동적 구성된다.

### 3.3 문서와 코드의 불일치

| 항목 | 확인 내용 | PM 처리 |
|---|---|---|
| 버전 | `README`, `pyproject.toml`, `app.__version__`은 여전히 `1.0.1`; 사용자는 v3.0 계획을 요청 | Jira `fixVersion`과 배포 버전 체계를 별도로 확인 |
| NSA 상태 | 기존 개요에는 “NSA 구현 완료” 표현이 있으나 실제로는 수동 Anchor 임시 지원 | v3 명세에서 “정식 지원”의 Delta를 명시 |
| LTE 상태 | 과거 UI 문서는 LTE 버튼 미결선으로 설명하지만 현재 코드는 LTE UI를 연결 | 코드 기준으로 완료/재사용 상태 처리 |
| Recall 식별자 | 현재 NR 코드는 `SA_FDD/SA_TDD`, LTE 코드는 `LTE_FDD/LTE_TDD`; 과거 Spike 목록과 표현이 다름 | 현재 모델 값을 구현 기준선으로 유지하고 LV 전달 표현은 `Recall Change` interface contract에서 매핑한다. |
| NSA RawData | 현행 문서는 NSA Anchor 셀을 비워 둔다고 설명 | 신규 요구에 따라 명세와 문서 갱신 |

## 4. 요청 범위 정상화

이 절은 사용자 입력을 누락 없이 묶은 것으로, 아직 최종 인수 기준은 아니다.

### 4.1 NSA 정식 지원

| 임시 코드 | 확정 입력 |
|---|---|
| PM-NSA-UI-01 | Test Manager의 `Case 확인` 버튼을 삭제한다. |
| PM-NSA-UI-02 | RAT 버튼을 `NR SA → NR NSA → LTE → WCDMA → GSM` 순서로 배치한다. |
| PM-NSA-UI-03 | SA와 NSA Test Case 생성 화면을 각각 LTE 화면과 같은 통합형 구조로 개발한다. SA 데이터는 현재 NR Table을 기준으로 한다. |
| PM-NSA-UI-04 | NSA 화면은 NR Band 옆에 LTE Anchor Band 선택 열을 둔다. 지원값은 `B1/B3/B7/B5/B8/B20/B28/B38/B40/B41`이다. |
| PM-NSA-DOM-01 | LTE Anchor는 모든 Band에서 Test Channel `MID`, Bandwidth `5 MHz`, RB Size `1`, RB Offset `0`, Modulation `QPSK`로 고정하며 사용자에게 별도로 입력받지 않는다. Anchor Band에 따라 달라지는 값은 UL/DL Channel뿐이다. |
| PM-NSA-DOM-02 | Test Manager는 예: Generation `NR_NSA`, Band `n5-B1`로 표시한다. |
| PM-NSA-DOM-03 | 모든 NR Band와 지원 Anchor Band의 조합을 허용한다. 조합별 별도 제한은 두지 않는다. |
| PM-NSA-VAL-01 | 한 실행 Queue에는 `NR_SA`, `NR_NSA`, `LTE` 중 하나의 Generation만 허용하고 혼합 Queue는 시험 시작 단계에서 차단한다. |
| PM-NSA-FSM-01 | NSA TC 전환 시 LTE Anchor Band가 같으면 기존 SA와 같은 `NR Handover`를 사용한다. |
| PM-NSA-FSM-02 | 첫 NSA TC 또는 LTE Anchor Band가 바뀌면 신규 고수준 `NSA Handover` 단일 composite로 `NR SCG Release → LTE Anchor DL Channel Handover·검증 → 기존 NR Call helper 재사용 → NR SCG Addition`을 수행한다. |
| PM-NSA-FSM-03 | 기존 고수준 `NR Call`의 외부 request Params는 유지한다. `NSA Handover` LV workflow는 동일 NR Call helper를 내부 재사용하여 NR 설정, `CALLSA`, 최종 NSA 연결 상태 확인을 수행한다. |
| PM-NSA-FSM-04 | Handover 이외의 측정 로직은 기존 SA 로직을 재사용한다. |
| PM-NSA-RPT-01 | NSA RawData에서 NR Band 옆 셀에 Anchor Band를 기록한다. |
| PM-NSA-RPT-02 | Plot 생성·저장 로직은 현재 동작을 유지한다. |

### 4.2 MT8000A NSA/Recall 확정 동작

#### 4.2.1 `CALLSTAT?` 상태 해석

`CALLSTAT?`는 직전에 명시적으로 지정한 `REM_DEST`의 상태 머신을 조회한다.

| `REM_DEST` | 상태 | 의미 |
|---|---:|---|
| `8000A` | `6` | Connected — NR SCG가 해제되고 LTE Anchor만 유지 |
| `8000A` | `7` | SCG Adding |
| `8000A` | `8` | Connected(NSA) |
| `8000A` | `9` | SCG Release |
| `8821C` | `6` | LTE Anchor Connected |
| `8821C` | `13` | Handover |
| `8821C` | `14` | NW Release |

`8821C` 상태 머신에는 NR 전용 상태 `7/8/9`가 없다. SCG Release 완료는 반드시 `REM_DEST 8000A`의 `CALLSTAT? == 6`으로 판정한다. `REM_DEST 8821C`의 `6`은 LTE Anchor 연결 유지 확인이며 SCG Release 완료의 직접 증거가 아니다.

`9=SCG Release`, `7=SCG Adding`, `13=Handover`는 빠르게 지나갈 수 있는 과도 상태다. 이를 반드시 관측해야 성공하는 조건을 만들지 않고 각 절차의 최종 상태를 polling한다.

#### 4.2.2 Anchor 변경 `NSA Handover`

```text
Python Anchor lookup
  Anchor Band + 고정 MID/5 MHz
  → 목표 UL Channel / DL Channel

REM_DEST 8000A
→ CALLSO
→ CALLSTAT? polling
→ 최종 6 확인

REM_DEST 8821C
→ DLCHAN <목표 DL Channel>
→ CALLSTAT? polling
→ 최종 6 확인
→ DL/UL Channel, BW, RB Size/Offset, Modulation read-back
→ MID/5 MHz/RB Size 1/RB Offset 0/QPSK 검증

기존 NR Call helper 재사용
→ REM_DEST 8000A
→ 새 NR 파라미터 설정
→ CALLSA
→ CALLSTAT? polling
→ 최종 8 확인
```

`NSA Handover` wire request는 `Anchor DL Channel`만 추가한다. LV 내부에서는 해당 값으로 `DLCHAN`만 변경한다. Anchor BW는 항상 `5 MHz`이므로 `CHBWDLCHAN`을 사용하지 않는다. `CHBWDLCHAN`으로 BW를 다시 적용해 RB 설정이 바뀌는 부작용을 만들지 않으며, BW/RB/Modulation 고정값은 Params로 전달하지 않고 Handover 후 LV 내부 read-back 검증 대상으로 취급한다. 기존 LTE 전용 `LTE Handover`의 `CHBWDLCHAN` 계약은 이 정책의 대상이 아니다.

`NSA Handover`는 내부에서 기존 NR Call helper를 재사용하는 단일 composite다. 성공 조건은 중간 단계의 SCG Release 완료 `8000A CALLSTAT == 6`, Anchor 연결 유지 `8821C CALLSTAT == 6`, 목표 DL/UL Channel과 고정 profile read-back 일치, 최종 SCG Addition 완료 `8000A == 8`과 Anchor `8821C == 6` 유지다.

NSA TC 사이의 routing은 다음으로 확정한다.

```text
LTE Anchor Band 동일 → 기존 NR Handover
LTE Anchor Band 변경 → 신규 고수준 NSA Handover 단일 composite
```

첫 NSA TC에서도 신규 `NSA Handover` 단일 composite를 사용한다. SCG Release가 필요하지 않은 초기 상태를 허용하고, 선택 Anchor의 `Anchor DL Channel` 적용·고정 profile 검증 후 내부 NR Call helper로 NR SCG를 연결한다. 측정 진입 조건은 `8000A == 8`과 `8821C == 6`이다.

#### 4.2.3 고수준 `Recall Change`

```text
Generation에 맞는 Call/SCG 정리
→ 해당 상태 머신의 최종 상태 확인
→ Parameter Recall 적용
→ 기존 Call workflow를 재사용하여 재연결
→ Generation별 최종 연결 상태 확인
```

NSA Recall Change에서 `CALLSO`는 전체 LTE Call 종료가 아니라 SCG Release다. Recall과 Anchor가 동시에 바뀌면 Anchor Band에서 lookup한 목표 DL Channel만 적용하고 MID/5 MHz/RB Size 1/RB Offset 0/QPSK 고정 profile을 read-back으로 검증한 뒤 기존 `NR Call` workflow로 SCG를 다시 연결하고 최종 상태를 확인한다. 내부 단계 순서는 `Recall Change` LV 구현 설계에 포함한다.

첫 실행 TC의 Recall 정책은 다음과 같다.

- 시험 최초에는 Parameter Recall을 자동 호출하지 않는다.
- 첫 실행 TC에 필요한 Recall이 장비에 이미 적용되어 있다고 간주하고 그 Recall ID를 세션 초기 적용 ID로 기록한다.
- `start_index > 0`이면 해당 인덱스의 TC가 첫 실행 TC다.
- 세션 중 목표 Recall ID가 달라질 때만 `Recall Change`를 실행한다.
- 자동 Recall 성공 후에만 세션의 적용 Recall ID를 갱신한다.
- Call 단절 시 Recall은 유지된 것으로 간주하고 기존 Call만 재실행한다.
- 신뢰할 수 있는 현재 Recall 조회 방법이 확인되기 전에는 Recall 조회 기능을 요구하지 않는다.

#### 4.2.4 외부 API 경계

| 외부 workflow | 책임 |
|---|---|
| 기존 `NR Call` | 현행 request Params 유지, NR 설정, `CALLSA`, 최종 NSA 연결 확인 |
| 신규 `NSA Handover` | SCG Release, LTE Anchor `DLCHAN` 변경, Anchor 고정 profile read-back 검증, 기존 NR Call helper를 재사용한 SCG Addition과 최종 상태 확인 |
| 신규 `Recall Change` | Generation별 Call/SCG 정리, Recall, 기존 Call 재사용 재연결 |
| 기존 `Check Call Status` | 모니터링과 장애 진단에 재사용 |

공유 TCP/JSON 계약의 command별 입력은 다음으로 고정한다.

| Command | request Params | 명시적으로 보내지 않는 값 |
|---|---|---|
| 기존 `NR Call` | 현행 유지: `Band`, `BandWidth`, `Center Channel`, `RB Size`, `RB Offset`, `Modulation`, `Max Retry Count`, `Waiting Time` | LTE Anchor 설정 전체 |
| 신규 `NSA Handover` | 기존 `NR Call` 8개 필드: `Band`, `BandWidth`, `Center Channel`, `RB Size`, `RB Offset`, `Modulation`, `Max Retry Count`, `Waiting Time`; 신규 Anchor 제어값: `Anchor DL Channel` | `Anchor Band`, `UL Channel`, Anchor `BandWidth`, `RB Size`, `RB Offset`, `Modulation`, `Test Channel` |

Python은 `Anchor Band`를 고정 MID/5 MHz 기준의 목표 UL/DL Channel로 lookup한다. Wire request에는 장비 변경에 사용하는 `Anchor DL Channel`만 넣고 `UL Channel`은 보내지 않는다. Anchor의 `5 MHz/RB Size 1/RB Offset 0/QPSK`는 Band별 mapping 결과가 아니라 모든 Band에 동일한 LV 내부 검증 상수다.

`NSA Handover`는 Default Response를 사용한다. Python은 최종 `status`만 신뢰하며 `Result`가 없거나 어떤 형식이더라도 무시한다. 성공은 `status="ok"`, 실패는 `status="error"`와 `Error.message`로 표현하며 성공 read-back Result와 별도 failure envelope는 요구하지 않는다. LV 내부의 단계별 terminal 상태와 profile 검증 책임은 유지된다.

`CALLSO`, `CALLSTAT?`, LTE Anchor Handover, Parameter Recall과 기존 NR Call 로직은 LV 내부 helper로 재사용한다. 각 workflow는 단계마다 `REM_DEST`를 명시적으로 설정하며 이전 destination에 의존하지 않는다. Python은 `NSA Handover` 단일 composite만 호출하고 NR Call 또는 LV primitive 순서를 제어하지 않는다. `Check Call Status` 재사용은 workflow 내부 terminal polling을 Python polling으로 대체한다는 의미가 아니다.

`NSA Handover`의 실제 command, Params와 Default Response는 Python/LV 구현 Issue의 공유 interface contract로 관리한다. Python은 실패 envelope를 해석하지 않고 Default Error의 `Error.message`만 오류 표시에 사용한다.

### 4.3 시험 운영 편의 개선

| 임시 코드 | 확정 입력 |
|---|---|
| PM-RAW-01 | 사용자가 RawData 파일을 UI에서 직접 선택하지 않는다. |
| PM-RAW-02 | RawData 결과 파일은 Screenshot 저장 기준 경로 아래 `{EUT Name}` 폴더에서 자동으로 찾는다. |
| PM-RAW-03 | 결과 파일명은 `{EUT Name}_CE Main_Radiation_{NR|LTE}.xlsx`를 사용하며 NR SA/NSA는 `NR`, LTE는 `LTE` 파일로 구분한다. |
| PM-RAW-04 | 대응 파일이 없으면 NR SA/NSA는 `resources/templates/NR_Rawdata_.xlsx`, LTE는 `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx`를 복사해 결과 파일을 만든다. |
| PM-RCL-01 | v2.0에서 연기된 MT8000A Parameter Recall 요구는 4.2의 세션 정책으로 대체한다. 첫 TC에는 호출하지 않고 세션 중 Recall ID 변경만 자동 처리한다. |
| PM-RCL-02 | 첫 실행 TC의 Recall ID를 세션 초기값으로 사용하고 이후 목표 ID가 달라질 때만 신규 고수준 `Recall Change`를 호출한다. |
| PM-RCL-03 | `Recall Change` 성공 후에만 적용 ID를 갱신한다. Call 단절 시 Recall은 유지된 것으로 보고 Recall 없이 기존 Call만 재실행한다. |

과거 v2 문서의 “첫 TestCase Recall 자동 적용”과 단순 `Call Stop → Recall → Call Start` 순서는 이번 4.2 확정사항으로 대체한다. Recall 문자열을 프로그램이 해석하지 않는 불투명 식별자로 다루는 원칙은 유지하되, 과거 Recall ID 목록은 현재 코드와 충돌하므로 그대로 복사하지 않는다.

### 4.4 Standalone Manual Test

#### 장비별 활성화

| 기능 | 활성 조건 |
|---|---|
| SA 설정, Sweep, Marker, Capture | `FSV40 == connected` |
| Turntable 및 3m Mast | `CO3000 == connected` |
| 1m Mast | `3D Controller == connected` |
| Semi Auto | `FSV40 == connected` 그리고 `CO3000 == connected` |

TestCase 존재 여부, Call 상태, Switch Box Filter 설정은 위 capability 판정에 사용하지 않는다.

다만 기능이 활성 상태여도 장비 operation 실행 권한은 별도다. 자동시험이 장비를 조작 중이면 Manual 장비 action을 시작할 수 없고, Manual operation 중에는 자동시험을 시작할 수 없다. 이 배타 동작은 기존 Filter Box의 동시 조작 방지 정책과 같은 방식으로 사용자에게 busy 상태를 알린다.

#### SA 설정과 Sweep

- Frequency Range preset을 선택한다.
- `Custom On`이면 Start/Stop Frequency, RBW, VBW를 직접 입력한다.
- Sweep Point, Sweep Time, Saturation Time, Attenuation, Det Mode, Line Limit를 직접 입력한다.
- Det Mode 기본값은 RMS다.
- Preset 버튼은 LabVIEW를 통해 FSV40 `*RST`를 수행한다.
- Set 버튼은 입력 설정을 적용한다.
- Single Sweep와 Continuous Sweep를 제공한다.

#### Marker

- Target Marker를 선택한다.
- Peak, Next Peak, Marker OFF, ALL Marker OFF를 제공한다.
- 선택 Marker의 Auto Peak ON/OFF를 제공한다.
- 선택 Marker의 주파수를 Center Frequency로 설정하는 Mkr→Center를 제공한다.

#### Turntable과 Mast

- 입력 속도로 Turntable을 `0°` 또는 `360°`로 이동한다.
- Stop으로 회전을 중지한다.
- 1m/3m Mast를 선택하고 H/V 편파를 변경한다.
- 3m Mast는 Horn/Bilog를 선택한다.
- Mast 높이는 제어하지 않는다.

#### Semi Auto

```text
현재 각도 조회
→ 가까운 0°/360°로 속도 6 초기 정렬
→ Clear Write
→ Max Hold
→ Continuous Sweep
→ 입력 속도로 반대 기준점까지 한 바퀴 회전
→ Max Hold 유지
```

Single Sweep와 자동 Screenshot은 수행하지 않는다.

#### Screenshot Capture

- Single Capture는 지정 PNG가 이미 있으면 저장하지 않고 경고한다.
- N-Capture는 Interval과 N Shots를 입력받는다.
- N-Capture 파일명은 `_001`, `_002`, ... 순번을 사용한다.
- 생성 예정 파일 중 하나라도 있으면 Capture 전체를 시작하지 않는다.
- 첫 Capture 후 각 다음 Capture까지 `Clear Write → Max Hold → Interval Wait → Capture`를 반복한다.
- 중간 실패 시 이후 작업을 중단하고 이미 성공한 파일은 유지한다.
- 성공한 Screenshot을 최신순 목록에 추가하고 선택 이미지를 표시한다.
- 목록에는 현재 앱 실행 세션에서 성공한 Screenshot만 표시하며 기존 저장 폴더 전체는 스캔하지 않는다.

#### Range 7~9

Range 7~9는 v3.0 필수 개발 범위에서 제외한다. 기존에 제시된 WCDMA/GSM용 후보값은 향후 요구를 위한 참고 정보로만 보존하고, 이번 명세와 Jira에는 Range 모델/preset 추가를 요구하지 않는다. 향후 WCDMA/GSM 또는 Manual Test에서 필요해질 때 나머지 속성과 함께 별도 Refinement한다.

## 5. NSA 정식 지원: 현행과 Gap

### 5.1 모델·CSV·Queue

| 요청 | 현행 | Gap 및 영향 | 근거 |
|---|---|---|---|
| NSA Generation | `Generation.NR_NSA` 존재 | 재사용 | `src/app/models/enums.py:43` |
| Anchor Band | `LTEBand`에는 요구된 10개와 B34도 존재 | NSA용 10개 allowlist 또는 전용 타입 필요 | `src/app/models/enums.py:27` |
| Anchor property | `TestCase`에 없음 | `anchor_band`, generation별 필수/금지 검증 필요 | `src/app/models/test_case.py:103` |
| CSV 저장/로드 | 10개 열을 순서까지 엄격히 검사 | Anchor field 추가와 NSA 필수값 검증 필요. schema migration 처리는 `NSA-01` 구현 범위 | `src/app/models/test_case.py:32`, `src/app/core/tc_loader.py:11` |
| SA/NSA/LTE Queue | SA/NSA는 같은 NR family로 취급하여 혼합 허용 | Generation 혼합을 시험 시작 단계에서 차단하도록 validator 변경 | `src/app/core/tc_validator.py:25` |
| Anchor 변경 감지 | 필드가 없어 불가능 | Anchor-only 변경도 Call 전환 판단에 포함 | `src/app/core/fsm/states/session.py:63` |

NSA 모델에는 요구된 Anchor Band property가 필요하다. LTE Anchor profile은 사용자 입력 필드로 추가하지 않고 아래 확정값을 사용한다. Python이 Anchor Band로부터 lookup하는 값은 UL/DL Channel뿐이다.

| LTE Anchor 고정 항목 | 값 | UI 입력 |
|---|---:|---|
| Test Channel | `MID` | 없음 |
| Bandwidth | `5 MHz` | 없음 |
| RB Size | `1` | 없음 |
| RB Offset | `0` | 없음 |
| Modulation | `QPSK` | 없음 |

### 5.2 UI

| 요청 | 현행 | Gap 및 영향 | 근거 |
|---|---|---|---|
| SA/NSA 진입 분리 | `NR` 한 버튼과 화면 안 SA/NSA toggle | 두 진입점과 별도 상태 보존 필요 | `src/app/ui/test_manager_panel.py:1148`, `src/app/ui/nr_select.py:910` |
| LTE형 통합 화면 | NR은 Select→Table의 2단계 | SA/NSA 각각 선택+Parameter 통합 화면 필요 | `src/app/ui/nr_select.py:811`, `src/app/ui/lte_select.py:249` |
| Anchor 열 | NR parameter에 없음 | NSA 화면에서 지원 Anchor Band를 선택하고 결과 TC에 `anchor_band` 저장 | `src/app/ui/nr_select.py:53` |
| 버튼 순서 | `NR/LTE/WCDMA/GSM/Case 확인` | 지정 순서로 교체하고 Case 확인 제거 | `src/app/ui/test_manager_panel.py:1137` |
| Manager 표시 | Generation은 표시, Band는 `case.band.value` | NSA일 때 `NR-Anchor` 조합 표시 | `src/app/ui/test_manager_panel.py:1941` |

### 5.3 FSM과 MT8000A

현행 NSA 흐름은 자동 NSA Handover가 아니다.

```text
첫 NSA TC
  LTECallAnchorBeforeNRCall(사용자 수동 확인)
  → NRCallConnect
  → 기존 측정

다음 NSA Call 설정 변경
  LTECallAnchorBeforeHandover(사용자 수동 확인)
  → 일반 NR Handover
  → 기존 측정
```

- NSA 라우팅은 수동 Anchor 확인 state를 삽입한다: `src/app/core/fsm/call_routing.py:13`.
- `LTECallAnchorState`는 TCP 요청 없이 사용자 확인만 기다린다: `src/app/core/fsm/states/nr_setup.py:27`.
- 일반 `HandoverState`는 단일 `NR Handover` facade를 호출한다: `src/app/core/fsm/states/transition.py:109`.
- SCG Release와 Anchor Handover를 수행하는 `NSA Handover` command는 없다.
- SA↔NSA generation 변경은 현재 TODO/no-op이지만, v3.0에서는 혼합 Queue를 시작 단계에서 차단하므로 세대 간 전환 FSM을 구현하지 않는다. 필요한 변경은 validator와 시작 차단 안내다: `src/app/core/fsm/states/session.py:89`.
- 기존 `LTE Handover`를 재사용하지 않고 NSA 전용 고수준 `NSA Handover` workflow를 제공해야 한다. NSA Anchor는 BW가 고정이므로 `CHBWDLCHAN` 대신 `DLCHAN`만 변경한다: `src/app/net/commands.py:183`.

목표 NSA 전환 routing은 다음과 같다.

| 이전 TC 대비 변경 | Python FSM이 호출할 외부 workflow | LV 내부 완료 판정 |
|---|---|---|
| LTE Anchor 동일, NR Call 설정 변경 | 기존 `NR Handover` | 기존 NR Handover 완료 조건 |
| 첫 NSA TC 또는 LTE Anchor 변경 | 신규 `NSA Handover` 단일 composite | 중간=`8000A == 6`, `8821C == 6`, Anchor profile read-back 일치 → 내부 NR Call helper 후 최종=`8000A == 8`, `8821C == 6` |
| Recall ID 변경 | 신규 `Recall Change` | Generation별 정리·Recall·재연결 후 Generation별 최종 연결 상태 |

`8000A`의 `7/9`와 `8821C`의 `13`은 과도 상태이므로 관측 누락이 실패가 아니다. 각 LV workflow는 매 단계 `REM_DEST`를 다시 설정하고 terminal 상태를 polling한다. 첫 NSA TC 자동 연결과 Recall+Anchor 동시 변경의 내부 순서는 각각 관련 LV 구현 Issue의 설계·벤치 검증에 포함한다.

### 5.4 RawData와 Plot

| 요청 | 현행 | Gap 및 영향 | 근거 |
|---|---|---|---|
| NSA 전용 결과 영역 | NR SA layout을 LB `-37`, 그 외 `-42`행 이동해 사용 | 재사용 | `src/app/report/template_map.py:14`, `src/app/report/template_map.py:165` |
| Anchor 기록 | BandInfo에 Anchor cell이 없고 B열은 비어 있음 | 승인된 cell 좌표와 writer 필드 추가 | `src/app/report/template_map.py:44`, `src/app/report/excel_writer.py:219` |
| Plot 유지 | SA/NSA 디렉터리와 filename prefix 구분 구현 | 기존 로직 회귀 확인만 수행 | `src/app/report/screenshot_store.py:50` |

현재 NSA layout에서 NR Band가 A7이므로 요구사항의 “Band 옆 셀”은 B7에 `B1` 형식으로 기록한다. 다른 layout도 같은 상대 위치 규칙을 template map에 적용한다.

또한 Band info는 `sheet + layout`당 한 번만 기록된다. 모든 NR–Anchor 조합을 지원해야 하므로 같은 NR Band의 서로 다른 Anchor 결과가 한 NR workbook에서 서로 덮어쓰지 않도록 결과 mapping을 구성해야 한다. 현재 `resources/templates/NR_Rawdata_.xlsx`에서 조합별 sheet/row block을 확인하고 필요한 writer mapping을 적용하는 것은 report 설계 과제이며, “NR Band당 Anchor를 하나만 허용”하는 제품 제약으로 바꾸지 않는다.

## 6. 시험 운영 편의 개선: 현행과 Gap

### 6.1 EUT Name 기반 RawData 자동 관리

현행 파일 흐름은 다음과 같다.

```text
사용자 Excel 찾기
→ TestRunSettings.template_path
→ Runner.start()
→ ExcelReportWriter(template_path)
→ 선택 파일 자체를 열고 in-place 저장

EUT Name
→ ReportWriter.model_name
→ Plot 경로/파일명에만 사용
```

| 요청 | 현행 | Gap 및 영향 | 근거 |
|---|---|---|---|
| Excel 선택 제거 | 실제 파일 선택이 Start 필수값 | UI, validation, 최근 Excel 경로 설정 정리 | `src/app/ui/test_manager_panel.py:680`, `src/app/ui/test_manager_panel.py:900` |
| EUT 기반 탐색 | 구현 없음 | Screenshot 저장 기준 경로 아래 EUT 폴더와 확정 filename을 계산하는 RawData path resolver 필요 | `src/app/models/test_run_settings.py:22` |
| 미존재 시 양식 복사 | `resources/templates`에 NR/LTE 기준 양식 존재, 자동 resolver/copy는 없음 | asset 추적·검증, source resolver, 안전한 copy 필요 | `resources/templates`, `CE_NR_Radiated.spec:16` |
| 기존 파일 재사용 | writer는 받은 파일을 수정할 수 있음 | 기존 파일을 그대로 재사용하고 열림·손상 등 사용 불가 상태는 오류 처리 | `src/app/report/excel_writer.py:33` |
| EUT filename 안전성 | Plot용 private sanitizer만 존재 | 공용 filename/path 안전성 검증 구현 필요 | `src/app/report/screenshot_store.py:21` |

현재 `template_path`는 원본 양식과 결과 파일 두 의미를 동시에 가진다. v3에서는 최소한 다음 lifecycle로 분리해야 한다.

```text
승인 source template(read-only)
        │ 대상 RawData 없음
        ▼
EUT/RAT 기반 result workbook 생성 또는 기존 파일 확보
        ▼
ExcelReportWriter(result_path)
        ▼
Excel live monitoring + in-place 결과 갱신
```

source-to-result mapping은 다음으로 확정됐다.

| 결과 RAT | source template | 확인된 sheet |
|---|---|---|
| NR SA/NSA | `resources/templates/NR_Rawdata_.xlsx` | 현재 지원 NR Band 15개의 `Sub6 n*` sheet |
| LTE | `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx` | 현재 지원 LTE Band 11개의 `LTE_BAND *` sheet. WCDMA sheet는 이번 범위에서 사용하지 않음 |

두 파일은 현재 worktree에 존재하지만 Git에서는 아직 untracked다. `CE_NR_Radiated.spec`은 이미 `resources` 전체를 datas에 포함하므로 별도 PyInstaller datas 규칙을 새로 요구하기보다, asset을 추적하고 dev/frozen 양쪽에서 올바르게 찾는 runtime resolver를 검증한다.

결과 경로 규칙은 다음과 같이 확정됐다.

```text
{Screenshot 저장 기준 경로}/
└─ {EUT Name}/
   ├─ {EUT Name}_CE Main_Radiation_NR.xlsx    # NR SA/NSA
   └─ {EUT Name}_CE Main_Radiation_LTE.xlsx   # LTE
```

현재 Plot root는 개발 실행에서 `~/Desktop/screenshots`, 패키징 실행에서 실행 파일 옆 `screenshots`로 달라진다. RawData resolver는 별도의 결과 root를 다시 정의하지 않고 Screenshot 저장 기준 경로 해석을 공유해야 한다. source root는 `resources/templates`로 확정됐으므로 `AppConfig.excel_template_path`의 휴면 예시 경로를 source로 사용하지 않는다.

RawData 구현 Issue에는 다음 예외처리와 검증을 포함한다. 이는 추가 제품 결정이 아니다.

- EUT Name으로 안전한 폴더와 파일 경로를 생성하고 사용할 수 없는 이름은 명확한 오류로 차단
- 기존 결과 파일은 재사용하고, 잘못된 sheet·손상·이미 열린 파일은 원인을 표시하고 Start 차단
- 개발 실행과 패키징 실행에서 `resources/templates` runtime lookup 검증
- source 누락, 권한 실패, 부분 복사 시 결과 파일을 사용하지 않고 Start 차단

### 6.2 MT8000A Parameter Recall 자동 적용

| 요청 | 현행 | Gap 및 영향 | 근거 |
|---|---|---|---|
| Recall ID 파생 | NR `SA_FDD/SA_TDD`, LTE `LTE_FDD/LTE_TDD` 존재 | 현재 모델 값을 기준선으로 사용하고 LV 전달 표현은 TCP/JSON Params 계약에서 매핑 | `src/app/models/band_group.py:31`, `src/app/models/lte_band_group.py:23` |
| 변경 감지 | Band와 Recall이 함께 바뀔 때 `RecallChange` 예약 | 첫 실행 TC는 호출하지 않고 이후 목표 Recall ID 자체가 달라질 때만 예약하도록 수정 | `src/app/core/fsm/states/session.py:63` |
| 첫 실행 TC | 별도 적용 상태 초기화 규칙 없음 | `start_index`를 반영한 첫 실행 TC의 Recall ID를 장비에 이미 적용된 세션 초기값으로 기록 | `src/app/core/fsm/context.py:40` |
| 실제 Recall | 사용자 팝업 완료만 대기 | 신규 고수준 `Recall Change` facade/LV workflow와 실패 처리 필요 | `src/app/core/fsm/states/transition.py:225` |
| 적용 ID 갱신 | TDF용 last-applied만 존재 | `Recall Change` 성공 후에만 별도 applied Recall ID 갱신 | `src/app/core/fsm/context.py:40` |
| Call 단절 | 기존 Call 복구 경로 사용 | Recall 재적용·조회 없이 기존 Call만 재실행하도록 정책 고정 | `src/app/core/fsm/call_routing.py:9` |

Python FSM은 `CALLSO`/Recall/Call primitive를 조합하지 않고 다음 의미 기반 외부 workflow 하나를 호출한다.

```text
Recall Change
  Generation에 맞는 Call/SCG 정리
  → 해당 상태 머신 최종 상태 확인
  → Parameter Recall
  → 기존 Call workflow 재사용
  → Generation별 최종 연결 상태 확인
```

NSA에서는 `CALLSO`가 전체 LTE Call 종료가 아니라 SCG Release로 동작한다. Recall과 Anchor가 동시에 바뀌면 목표 Anchor의 `DLCHAN`만 변경하고 고정 profile을 read-back 검증한 뒤 기존 `NR Call`로 SCG를 재연결한다. 정확한 helper 순서는 고수준 `Recall Change` LV 구현 Issue에서 설계한다.

failure Result는 최소 실패 단계, `8000A` 상태, `8821C` 상태와 오류 메시지를 제공한다. 실제 wire command/필드명과 timeout·polling·retry 값은 Python/LV interface contract와 벤치 검증 결과로 해당 구현 Issue 안에 기록한다.

## 7. Manual Test: 현행과 Gap

### 7.1 UI와 연결 상태

- Manual Test 내비게이션은 이미 존재한다: `src/app/ui/main_window.py:329`.
- `ManualTestPanel`은 TODO만 있는 빈 `QWidget`이다: `src/app/ui/manual_test_panel.py:7`.
- MainWindow는 Manual 패널 참조를 보관하지 않고 연결 상태를 Test Manager와 RF Filter Box에만 전달한다: `src/app/ui/main_window.py:275`, `src/app/ui/main_window.py:633`.
- 기능 활성화는 전체 장비 ready 여부가 아니라 `equipment_state`의 장비별 boolean으로 계산해야 한다.

PM 권고 조립 구조는 다음과 같다.

```text
MainWindow
  ├─ self._manual_test_panel
  ├─ ManualTestService(QObject)
  │    └─ operation별 QThread worker
  └─ 공용 operation coordinator / lock
```

N-Capture interval, Turntable event 대기, Semi Auto 다단계와 파일 I/O가 있으므로 UI thread 동기 실행 방식은 적합하지 않다.

### 7.2 재사용 가능한 command와 신규 command

| Manual 기능 | 현행 기반 | 판정 |
|---|---|---|
| Start/Stop/RBW/VBW/Sweep Point/Limit | `setup_sa()` | 부분 재사용 |
| Attenuation | `setup_sa_startup_levels()` | 부분 재사용 |
| Sweep Time | precision 측정용 명령만 존재 | 신규 일반 계약 필요 |
| Screenshot | `get_screenshot()` 요청 후 LV가 `temp/screenshot.png`를 생성하는 계약 | 재사용 가능하나 저장 workflow 신규 |
| Peak/Next/OFF/ALL OFF | 기존 marker facade | 재사용 가능 |
| Turntable move/stop/angle | 기존 CO3000 facade | 재사용 가능 |
| 1m/3m Horn/Bilog 편파 | `set_antenna_pol()`과 Mast Index mapping | 재사용 가능 |
| FSV `*RST` Preset | 없음 | 신규 LV/Python command |
| Single/Continuous Sweep | 없음 | 신규 LV/Python command |
| Clear Write/Max Hold | 없음 | 신규 LV/Python command |
| Det Mode | 없음 | 신규 모델/command |
| Marker Auto Peak | 없음 | 신규 LV/Python command |
| Mkr→Center | 없음 | 신규 LV/Python command |

관련 command 근거는 `src/app/net/commands.py:494-765`다.

현행 Peak/Next/OFF facade는 모두 `Marker Index`와 `Excursion` payload를 요구하지만 신규 Standalone UI 입력에는 Excursion이 없다. 기존 Manual Marker는 Marker 1~10과 Next Peak Search Level을 제공한다. Standalone 구현 시 UI 요구를 유지하면서 실제 payload를 맞추는 adapter/interface contract를 관련 Manual Story 안에서 작성한다. 이를 현재 제품 결정으로 올리지 않는다.

현재 Mast mapping은 다음과 같아 내부 adapter로 재사용할 수 있다.

| 사용자 선택 | 현행 내부 표현 | 제어 대상 |
|---|---|---|
| 3m Bilog | `InputPath.INPUT1`, `Mast Index=2` | CO3000 |
| 3m Horn | `InputPath.INPUT2`, `Mast Index=1` | CO3000 |
| 1m | `InputPath.INPUT3` | 3D Controller |

Manual domain에서는 사용자가 Filter Path를 선택하는 것으로 오해하지 않도록 `ManualMast` 같은 명시적 UI 모델로 표현하고 command adapter에서만 현행 mapping으로 변환하는 편이 안전하다.

### 7.3 Semi Auto

기존 자동시험에는 다음 기반이 있다.

- Turntable command와 progress/complete/error event 처리
- 현재 각도가 `<= 180°`면 0°, 그보다 크면 360°를 가까운 기준점으로 선택
- 초기 정렬 속도 6
- 중단 시 Turntable Stop

관련 로직은 `src/app/core/fsm/states/measurement/common.py:289-568`에 있다. 이 state는 SessionContext와 TestCase에 결합되어 있으므로 Manual Test에서 직접 호출하지 않고 알고리즘과 event handling을 Manual service로 재구성한다.

현행 가까운 기준점 규칙을 재사용하므로 정확히 180°일 때는 현재 알고리즘대로 0°를 선택한다. initial align/본 회전 timeout, Stop 반응, 실패 시 안전 상태와 회전 완료 event correlation은 `MAN-09`의 구현·검증 범위이며 별도 제품 결정으로 만들지 않는다.

### 7.4 Single/N-Capture와 목록

현행 자동 Screenshot 저장은 같은 파일이 있으면 `(1)`, `(2)`를 붙이고, 단순 `ScreenshotStore.save()`는 덮어쓴다. Manual의 “충돌 시 전체 시작 금지” 규칙과 다르므로 전용 store가 필요하다.

Manual Capture에는 최소한 다음 처리가 필요하다.

1. base path와 N개 destination 전체를 먼저 계산한다.
2. 하나라도 존재하면 장비 command를 보내지 않는다.
3. 고정 temp 계약을 유지한다면 각 Capture 전 stale `temp/screenshot.png`를 제거한다.
4. LV 응답 후 실제 PNG 생성과 flush 완료를 확인한다.
5. 성공 파일만 destination에 복사하고 최신순 목록 앞에 추가한다.
6. 실패 시 다음 Capture를 중단하되 기존 성공 파일을 삭제하지 않는다.
7. UI를 닫거나 Stop할 때 interval wait와 worker를 안전하게 종료한다.

현행 Screenshot UI는 목록이 아니라 최신 한 장만 유지하므로 목록 모델과 viewer 결선은 신규다: `src/app/ui/test_plot_screenshot_panel.py:35`.

### 7.5 Range 7~9

Range 7~9는 v3.0 필수 범위에서 제외됐으므로 현행 `TestRange`, `ALL_TEST_RANGES`, Test Manager의 Range 확인 표를 변경하지 않아도 된다. 이에 대한 구현 Story나 모델 의사결정도 이번 백로그에 만들지 않는다.

향후 요구가 다시 생기면 현재 `TestRange`가 limit, sweep point, input path, filter mode를 모두 필수로 요구한다는 제약부터 재검토해야 한다: `src/app/models/test_range.py:52`. 이 메모는 후속 WCDMA/GSM 또는 Manual Refinement용이며 v3.0 Acceptance Criteria가 아니다.

### 7.6 자동시험과 Manual Test 동시성

공용 `TcpClient`는 TCP 요청을 queue에서 직렬 처리하지만 장비 workflow의 소유권은 보호하지 않는다. Manual과 자동시험 요청이 command 단위로 섞일 수 있고, Turntable event와 `temp/screenshot.png`도 operation별 상관관계가 없다.

v3.0 정책은 Filter Box와 같은 전역 장비 operation 배타 동작이다.

- 자동시험 중 Manual 장비 action 차단
- Manual operation 중 Auto Start, Connect, Set, TDF, RF 수동 조작 차단
- Connect/Set/TDF/RF operation 중 Manual action 차단
- 입력값 편집과 이미 저장된 Screenshot 열람은 허용
- 자동시험의 Manual Marker Dialog는 자동시험 소유 operation으로 취급

서로 다른 장비라도 이번 버전에서는 병렬 장비 조작을 허용하지 않는다. 입력값 편집과 이미 저장된 Screenshot 열람처럼 장비 command를 발생시키지 않는 동작만 잠금 대상에서 제외한다. 구체적인 busy UI와 lock 획득·해제 시점은 설계에서 정하되, 동시 장비 조작 금지는 더 이상 제품 미결정 항목이 아니다.

## 8. 결정 Register

### 8.1 이번 검토에서 닫힌 결정

| ID | 결정 결과 | 후속 처리 |
|---|---|---|
| DEC-NSA-01A | 모든 NR Band × 지원 Anchor Band 조합을 허용한다. | 별도 조합표 작업을 만들지 않고 Anchor allowlist만 검증한다. |
| DEC-NSA-01B | LTE Anchor는 모든 Band에서 Test Channel `MID`, Bandwidth `5 MHz`, RB Size `1`, RB Offset `0`, Modulation `QPSK`를 사용한다. | Python은 Anchor Band에서 UL/DL Channel만 lookup한다. 고정 profile은 command Params에서 제외하고 LV 내부 read-back 검증 기준으로 사용한다. |
| DEC-NSA-04A | `NR_SA`/`NR_NSA`/`LTE` 혼합 Queue는 시작 단계에서 차단한다. | SA↔NSA↔LTE 전환 FSM은 만들지 않는다. |
| DEC-NSA-04B | NSA TC의 Anchor가 같으면 기존 `NR Handover`를 호출한다. 첫 NSA TC 또는 Anchor가 바뀌면 내부에서 NR Call helper를 재사용하는 신규 `NSA Handover` 단일 composite를 호출한다. | Python은 한 번의 고수준 workflow만 호출하며 NR Call/primitive sequencing을 만들지 않는다. |
| DEC-MT-01 | `CALLSTAT?`의 `REM_DEST`별 상태 의미와 terminal polling 기준은 4.2.1을 따른다. | SCG Release=`8000A==6`, NSA 연결=`8000A==8`, Anchor 유지=`8821C==6`; 과도 상태는 필수 관측하지 않는다. |
| DEC-MT-02 | 외부 API는 기존 `NR Call`, 신규 `NSA Handover`, 신규 `Recall Change`, 기존 `Check Call Status`의 의미 기반 workflow로 제공한다. | `CALLSO`/`CALLSTAT?`/Anchor HO/Recall은 명시적 `REM_DEST`를 사용하는 LV 내부 helper다. |
| DEC-MT-03 | `NSA Handover` 응답은 Default Response를 사용한다. | Python은 최종 `status`만 판정하고 `Result`를 무시한다. 실패 시 `Error.message`만 요구한다. |
| DEC-RCL-02 | 첫 실행 TC에는 Recall을 호출하지 않고 `start_index`를 반영한 해당 TC의 ID를 세션 초기값으로 사용한다. | first-TC Recall command를 제거한다. |
| DEC-RCL-03 | 목표 ID 변경 시에만 Recall Change를 실행하고 성공 후에만 applied ID를 갱신한다. Call 단절 시 Recall은 유지되며 현재 Recall 조회는 요구하지 않는다. | session context·복구 Acceptance Criteria에 반영한다. |
| DEC-RCL-04 | Recall Change는 NSA Handover와 분리된 고수준 LV workflow다. NSA의 `CALLSO`는 SCG Release로 처리한다. | Generation별 정리→Recall→기존 Call 재연결→최종 상태 확인을 LV에서 수행한다. |
| DEC-RAW-01 | 결과 경로와 filename은 `POL-RAW-01`을 따른다. | path resolver Story의 고정 입력으로 사용한다. |
| DEC-RAW-02 | NR source는 `resources/templates/NR_Rawdata_.xlsx`, LTE source는 `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx`다. | asset 수령 질문을 닫고 추적·검증·runtime lookup만 남긴다. |
| DEC-MAN-01 | Filter Box와 같은 전역 배타 장비 operation 정책을 적용한다. | 경쟁 command 차단과 busy 안내를 고정 입력으로 사용하고 구현 방식은 설계에서 정한다. |
| DEC-MAN-03 | Screenshot 목록은 현재 앱 실행 세션에서 성공한 파일만 표시한다. | 폴더 전체 scan 요구를 제거한다. |
| DEC-MAN-04 | Range 7~9는 v3.0 필수 범위에서 제외한다. | Range 7~9 구현 Story를 만들지 않는다. |
| DEC-PLAN-01 | NSA를 먼저 개발하고 Manual 상세 command/workflow 계약은 Manual 착수 시 확정한다. | Manual 구현 Issue의 Refinement 범위로 두고 NSA 선행 조건으로 연결하지 않는다. |

### 8.2 추가 제품 결정 상태

현재 NSA/Recall과 RawData SRS 및 Jira Issue 작성을 막는 추가 제품 결정은 없다. 다음 사항은 결정 Register에 올리지 않고 해당 구현 Issue에서 구체화한다.

| 기술사항 | 관리 위치 | 요구되는 결과 |
|---|---|---|
| 첫 NSA TC 연결 순서 | `NSA-04-LV`, `NSA-05` | 단일 `NSA Handover` 내부에서 Anchor 준비와 NR Call helper를 수행하고 측정 전 `8000A == 8`, `8821C == 6` 확인 |
| Recall+Anchor 동시 변경 내부 순서 | `RCL-02-LV` | 목표 Recall·Anchor 적용 후 NSA 최종 연결 상태 복구 |
| Anchor CSV 필드와 결과 cell mapping | `NSA-01`, `NSA-06` | NSA TC에 Anchor 필수, 결과는 NR Band 옆 셀에 `B*` 형식으로 기록 |
| RawData path 안전성·열림·손상·runtime lookup | `RAW-01`, `RAW-04`, `RAW-05` | 기존 파일 재사용, 미존재 시 확정 양식 복사, 실패 시 명확한 오류와 Start 차단 |
| Manual command/API/UX 세부 계약 | 각 `MAN-*` 구현 Issue | Manual Test 착수 시 확정 요구사항을 만족하도록 Refinement |

### 8.3 구현 Issue의 기술 설계·검증 산출물

| 산출물 | 포함할 Issue | 관리 원칙 |
|---|---|---|
| MT8000A TCP/JSON command·Params·응답 계약 | `NSA-04-PY/LV`, `RCL-02-PY/LV` | 고수준 workflow 경계와 command별 Default Response/오류 계약을 정의 |
| timeout·polling·retry 값과 벤치 결과 | `NSA-04-LV`, `RCL-02-LV`, 통합 인수 | 무한 대기 없이 terminal 상태 또는 명시적 실패로 종료되도록 구현·검증 |
| RawData resolver와 배포 resource 검증 | `RAW-01`, `RAW-04`, `RAW-05` | dev/frozen에서 동일 source를 찾고 copy/reuse 실패를 안전하게 처리 |
| Manual Test interface contract | 관련 `MAN-*` Python/LV Issue | NSA 개발 이후 Manual Test 착수 시 구현팀과 함께 Refinement |

위 항목은 독립적인 ‘결정용 Issue’가 아니다. 구현에 별도 실장비 검증이 필요하면 해당 Story의 subtask 또는 DoD로 관리한다. terminal 성공은 4.2의 최종 상태 polling으로 판정하며, 근거 없는 추가 유지 시간 기준은 요구하지 않는다.

### 8.4 PM 계획 원칙

- MT8000A 외부 경계는 의미 기반 고수준 LV workflow로 확정됐다. Python FSM은 LV helper primitive의 순서를 직접 제어하지 않는다.
- 각 LV workflow는 단계마다 `REM_DEST`를 명시하고 terminal 상태를 polling한다. `NSA Handover`의 외부 응답 판정은 `DEC-MT-03`을 따른다.
- Manual의 N-Capture/Semi Auto Python workflow와 LV 복합 명령 경계는 Manual Refinement에서 결정한다.
- v3.0 장비 동시성 정책은 전역 배타 동작으로 확정하되 기존 guard 확장과 신규 coordinator 중 구현 방식은 설계에서 정한다.
- Range 7~9는 이번 백로그에서 제외한다.
- Manual Capture의 기존 파일 충돌 시 시작 금지 정책은 유지하되 세부 file contract는 Manual Refinement에서 확정한다.

## 9. 권장 개발 순서와 의존성

### 9.1 전체 흐름

```text
1차: NSA 정식 지원
  확정 정책 적용
    ├─ 모든 NR–Anchor 조합 허용
    ├─ Anchor Band 선택 열 추가, 별도 설정 입력 없음
    ├─ SA/NSA/LTE 혼합 Queue 시작 차단
    ├─ Anchor 동일 → 기존 NR Handover
    └─ 첫 NSA TC/Anchor 변경 → NR Call helper를 내부 재사용하는 신규 고수준 NSA Handover 단일 composite
  구현 Issue 내부 설계·검증
    ├─ Anchor CSV field / 결과 cell mapping
    ├─ 첫 NSA TC 자동 연결과 Recall+Anchor 동시 변경
    └─ Python/LV wire contract / timeout·poll·retry / terminal polling 벤치 검증
  구현 흐름
    └─ Anchor domain/CSV → SA·NSA UI → 고수준 Python/LV workflow → FSM/결과 → 통합 인수

2차 또는 비충돌 병렬 Track: 운영 편의
  ├─ resources/templates asset 추적·검증 → RawData resolver/store → Runner/UI 통합
  └─ 확정된 고수준 Recall Change 기반 Recall FSM

후속 Track: Standalone Manual Test
  Manual 구현 Issue Refinement
    ├─ command/payload/Python-LV workflow 경계
    └─ Capture/Marker/Sweep 세부 계약
  구현
    ├─ 확정된 전역 배타 operation 정책 적용
    ├─ 현재 세션 Screenshot 목록 적용
    └─ Range 7~9 제외

각 Track: Mock/정적 계약 검증 → 승인된 LV/실장비 인수 → 문서/배포 동기화
```

### 9.2 병렬화 가능한 Track

| Track | 착수·조정 기준 | 주요 충돌 파일 |
|---|---|---|
| NSA Domain/UI/Report | 확정된 Anchor property·allowlist·결과 위치를 사용해 바로 착수하고 CSV/writer 세부 mapping은 Issue 안에서 완성 | `test_case.py`, `test_manager_panel.py`, `excel_writer.py` |
| NSA/Recall FSM | 확정된 고수준 workflow와 terminal 상태를 기준으로 착수하고 Python/LV wire contract는 양쪽 Issue가 함께 작성 | `session.py`, `transition.py`, `commands.py` |
| RawData | 확정 source/path/filename으로 착수하고 asset tracking, copy/reuse 예외처리와 runtime lookup을 구현 범위에 포함 | `runner.py`, `test_run_settings.py`, report 계층 |
| Manual Test | NSA 우선순위를 해치지 않는 착수 시점에 각 기능 Issue에서 FSV/CO3000 계약을 Refinement | `main_window.py`, `commands.py`, mock |
| LabVIEW | Python counterpart와 같은 interface contract를 사용하고 벤치 결과를 해당 Issue에 첨부 | 외부 LV source/release |

NSA와 Recall은 `session.py`, `transition.py`, `commands.py`, Mock LV를 공유하므로 서로 다른 브랜치에서 독립 구현하지 않는 편이 안전하다. NSA Anchor 결과와 RawData 자동화는 `excel_writer.py`, `template_map.py`, 실제 Excel 양식과 report lifecycle에서 조정이 필요하다. `runner.py`의 직접 변경 중심은 RawData lifecycle 쪽이다. Manual Test 역시 command catalog와 Mock LV를 확장하므로 공통 파일 담당자 또는 순차 merge 계획이 필요하다.

## 10. Jira Agent용 후보 작업 패키지

아래는 Jira Issue가 아니라 backlog 변환 입력이다. Priority, 담당자, Story Point, Sprint는 Refinement 전 임의로 정하지 않는다.

### 10.1 별도 결정용 Issue를 만들지 않는 범위

NSA/Recall과 RawData는 현재 확정사항으로 구현 Story를 작성한다. 내부 sequence, wire schema, timeout·retry, path 예외처리와 runtime lookup을 확정하기 위한 독립 Discovery/Spike는 만들지 않고 관련 Python/LV/RawData Story의 subtask 또는 DoD로 포함한다.

Manual Test의 상세 command/API/UX 계약도 지금 별도의 미결정 Issue로 만들지 않는다. NSA 우선 개발 후 각 Manual 구현 Story를 Refinement할 때 필요한 계약 작업을 함께 등록한다.

### 10.2 NSA 정식 지원 후보 패키지

| 후보 ID | Outcome | 의존성 | 예상 주 영향 |
|---|---|---|---|
| NSA-01 | Anchor-aware TestCase/CSV와 Generation 혼합 시작 차단 validation | POL-NSA-01/02/03 | models, loader, validator |
| NSA-02 | NR SA·NR NSA 각각의 LTE형 통합 생성 화면과 별도 진입 버튼 | NSA-01 | UI |
| NSA-03 | Manager `n5-B1` 표시와 generation별 UI state | NSA-01 | UI |
| NSA-04-PY | 기존 `NR Call` request Params 호환 유지, Anchor Band→MID 5 MHz UL/DL Channel lookup, 목표 NR 설정과 `Anchor DL Channel`을 전송하는 신규 단일 `NSA Handover` facade, Default Response의 status-only 판정, stateful Mock와 Default Error 처리 | NSA-01 | models, net, mock, protocol docs |
| NSA-04-LV | `DLCHAN`만 변경하고 MID/5 MHz/RB Size 1/RB Offset 0/QPSK를 read-back 검증한 뒤 기존 NR Call helper로 SCG Addition까지 완료하는 신규 `NSA Handover` 단일 composite, timeout·polling·retry 벤치 검증 | 4.2 확정 workflow | 외부 LV. `CHBWDLCHAN` 사용 금지, 단계별 REM_DEST, terminal polling과 최소 failure 정보 포함 |
| NSA-05 | 첫 NSA TC/Anchor 변경 시 단일 `NSA Handover`, Anchor 동일 시 기존 `NR Handover`를 호출하는 FSM routing | NSA-01, NSA-04-PY | core/fsm |
| NSA-06 | NR Band 옆 cell에 `B*` 형식으로 Anchor Band 기록 | NSA-01 | report/template map |
| NSA-07 | 실제 LV를 포함한 NSA 통합 인수와 임시 문서 정식화 | NSA-02~06, NSA-04-LV | tests/docs/release |

### 10.3 시험 운영 편의 개선 후보 패키지

| 후보 ID | Outcome | 의존성 | 예상 주 영향 |
|---|---|---|---|
| RAW-01 | 확정 경로·filename을 사용하는 EUT/RAT RawData resolver와 safe copy/reuse | POL-RAW-01/02 | report/config/assets |
| RAW-02 | Runner가 확정 source template으로 결과 workbook을 자동 확보한 뒤 writer 생성 | RAW-01, RAW-04 | Runner/context/report |
| RAW-03 | Excel 선택 UI와 사용자 path validation 제거 | RAW-02 | Test Manager/config. CSV 경로에도 쓰는 `runtime_base_directory()`는 유지 검토 |
| RAW-04 | 두 `resources/templates` asset의 tracking/검증과 dev/frozen runtime lookup | POL-RAW-02 | resources/spec. 기존 spec의 resources 포함 규칙 검증 |
| RAW-05 | 신규/기존/손상/열림/복사 실패 lifecycle 검증과 문서화 | RAW-01~04 | tests/docs |
| RCL-02-PY | 현재 모델의 Recall 식별자를 wire Params에 매핑하는 신규 고수준 `Recall Change` facade, wire contract, failure parsing과 REM_DEST별 Mock 확장 | 4.2 확정 workflow | models/net/mock |
| RCL-02-LV | Generation별 정리→Recall→기존 Call 재연결과 Recall+Anchor 동시 변경을 수행하는 고수준 `Recall Change` LV workflow 및 벤치 검증 | 4.2 확정 workflow | 외부 LV |
| RCL-03 | 첫 TC 미호출, `start_index` 초기화, ID 변경 시만 호출, 성공 후만 갱신, Call 단절 시 Call만 복구하는 FSM | RCL-02-PY | core/fsm |
| RCL-04 | 실제 LV를 포함한 SA/NSA/LTE/Recall/TDF 통합 인수와 문서화 | RCL-02-LV, RCL-03, NSA-05 | tests/docs |

`RCL-03`은 Recall 변경용 수동 확인만 대체한다. DUT Axis 변경, Call 복구 등에서 사용하는 공용 `user_action_required`와 `_UserActionDialog`까지 제거하는 작업이 아니다.

### 10.4 Manual Test 후보 패키지

| 후보 ID | Outcome | 의존성 | 예상 주 영향 |
|---|---|---|---|
| MAN-01 | Manual 설정/Capture 모델과 validation, 착수 시 필요한 필드 Refinement | NSA 우선순위 반영 | models/core |
| MAN-02-PY | FSV/Marker 신규 Python facade, interface contract와 Mock | MAN-01 | net/mock |
| MAN-02-LV | Python counterpart와 합의한 실제 LV command/API 구현 | MAN-02-PY와 공동 Refinement | 외부 LV |
| MAN-03 | ManualTestService worker lifecycle과 cancel/error/progress | MAN-01, MAN-02-PY | core |
| MAN-04 | Filter Box와 같은 전역 배타 operation 적용과 busy 처리 | POL-MAN-01 | MainWindow/services. 기존 guard 확장/신규 coordinator는 설계 선택 |
| MAN-05 | 장비 capability별 Manual Panel 활성화 | MAN-03/04 | UI |
| MAN-06 | SA Set/Preset/Single/Continuous UI+service | MAN-02-PY, MAN-03, MAN-05 | UI/core |
| MAN-07 | Marker 6종 UI+service | MAN-02-PY, MAN-03, MAN-05 | UI/core |
| MAN-08 | Turntable/1m/3m Horn/Bilog UI+service | MAN-03/05 | UI/core |
| MAN-09 | Semi Auto 기능 통합과 Stop/timeout/failure 처리 | MAN-02-PY/LV, MAN-03, MAN-04, MAN-08 | Python/LV 공동. sequence 소유권은 Manual 착수 시 Refinement |
| MAN-10 | strict no-overwrite Single Capture store/workflow | MAN-03 | report/core/UI |
| MAN-11 | N-Capture 반복 수행, preflight와 부분 성공 보존 통합 | MAN-02-PY/LV, MAN-03, MAN-10 | Python/LV/report/UI. 반복 sequence 소유권은 Manual 착수 시 Refinement |
| MAN-12 | 현재 세션 최신순 Screenshot 목록과 viewer | POL-MAN-03, MAN-10/11 | UI |
| MAN-14 | 실제 LV를 포함한 Mock/실장비 통합 인수와 운영 문서 | MAN-02-LV, MAN-05~12 | tests/docs/release |

Range 7~9는 `POL-MAN-02`에 따라 후보 패키지에서 제외했다. 후속 요구가 생기기 전에는 `MAN-13` 또는 이에 준하는 Jira Issue를 생성하지 않는다.

### 10.5 Jira 구성 권고

- 사용자의 세 분류를 상위 Epic으로 유지한다.
- NSA 정식 지원 Epic을 우선순위 1로 두고 확정 요구사항에서 `NSA-*`와 `RCL-*` 구현 패키지를 바로 Refinement한다.
- 기술 설계·벤치 검증은 별도 결정용 Spike로 분리하기보다 관련 구현 Story의 subtask/DoD로 연결한다. 실장비 접근 자체가 독립 일정이면 검증 subtask만 분리한다.
- 실제 LabVIEW 작업은 Python facade 작업과 별도 Issue로 만들고 같은 protocol ADR을 첨부한다.
- command Issue는 이름만 적지 말고 target, Params, Result, unit, timeout, failure와 Mock까지 범위에 포함한다.
- `CALLSO`/`CALLSTAT?`/Anchor HO/Recall primitive를 별도 외부 API Story로 만들지 않고 고수준 `NSA Handover`·`Recall Change` LV Issue의 helper/subtask로 관리한다.
- 과도 상태 `8000A 7/9`, `8821C 13` 관측을 Acceptance Criteria로 요구하지 않는다. 명시적 `REM_DEST`와 terminal 상태 polling을 검증한다.
- UI Story는 연결 상태만이 아니라 worker 진행/중단/오류/lock 상태를 Acceptance Criteria에 포함한다.
- 외부에서 확인 가능한 Outcome과 Acceptance Criteria가 있으면 구현 Issue를 Ready로 만들 수 있다. 내부 command 이름·순서·timeout 값은 Ready 선행 제품 결정으로 취급하지 않는다.
- Manual 상세 command/workflow는 Manual 개발 착수 시 관련 Story 안에서 Refinement하고 NSA Issue의 blocker로 연결하지 않는다.
- Range 7~9 구현 Issue는 만들지 않으며, Screenshot 목록 source와 전역 배타 동작은 미결정 질문으로 되돌리지 않는다.
- broad regression test 실행을 백로그 정리 단계의 자동 활동으로 두지 않는다. 구현별 검증 범위와 승인 장비 인수는 별도 명시한다.

## 11. 요구사항 관리 Agent 인수인계

요구사항 관리 Agent는 이 문서를 바탕으로 다음 산출물을 만들어야 한다.

1. v3.0 최종 scope와 out-of-scope
2. 용어집과 canonical 명칭
3. Capability별 기능 요구사항과 명확한 인수 기준
4. `REM_DEST`별 `CALLSTAT?` 상태표, terminal 성공 조건과 과도 상태 처리 규칙
5. 기존 `NR Call`, 신규 `NSA Handover`, 신규 `Recall Change`, 기존 `Check Call Status`의 외부 API 책임과 command별 응답 계약
6. 첫 실행 TC를 포함한 Recall session lifecycle과 NSA 전환 diagram
7. Anchor allowlist·고정값(`MID/5 MHz/RB Size 1/RB Offset 0/QPSK`)·Band→UL/DL Channel lookup·CSV/결과 mapping과 Recall 식별자 표
8. 확정 RawData path/filename, 두 source template mapping과 file lifecycle 예시
9. 첫 NSA TC 자동 연결, Recall+Anchor 동시 변경, terminal 상태와 Default Response 실패 처리의 관찰 가능한 인수 기준
10. Manual 기능별 enablement, 확정된 전역 배타 정책, validation, busy/cancel/error 상태
11. 요구사항→Jira→검증 시나리오 traceability

### 11.1 용어 정규화 권고

| 입력 표현 | 문서 canonical 표현 | 비고 |
|---|---|---|
| `MT8800a`, `MT8000a` | `MT8000A` | 이번 확정 입력에 따라 오탈자로 정규화 |
| NSA Anchor | `LTE Anchor Band` | 값은 `B1` 형식 |
| SCG Addiation | `NR SCG Addition` | 오탈자 정정 |
| Rawdata/RawData | `RawData workbook` | source template과 result workbook 구분 |
| Manual Test | `Standalone Manual Test` | 기존 `Manual Marker`와 구분 |
| Cont Sweep | `Continuous Sweep` | UI label은 별도 가능 |
| Mkr→Center | `Marker to Center` | protocol command 이름은 계약에서 확정 |

### 11.2 요구사항 Agent 작성 원칙

- SRS에는 자동 수행 여부, 입력 제약, 최종 상태, 결과 기록, 실패 응답처럼 사용자와 시스템 경계에서 관찰 가능한 동작을 작성한다.
- LV helper 순서, 실제 wire field 이름, timeout·retry 수치와 path 정규화 알고리즘은 제품 미결정으로 만들지 않는다. 관련 구현 Issue의 설계·검증 산출물로 연결한다.
- terminal 상태 polling 외의 추가 stable-state 유지 시간은 요구하지 않는다. 실장비에서 필요성이 확인될 때만 결함 보강 또는 기술 subtask로 추가한다.
- RawData 기존 파일 재사용과 미존재 시 source 복사는 확정 동작이다. 열림·손상·권한·경로 오류는 구현 Issue의 safe-failure Acceptance Criteria로 작성한다.
- Manual 세부 계약은 Manual Test 착수 시 관련 구현 Issue에서 Refinement하며, 현재 NSA/RawData SRS의 미결정 목록으로 복사하지 않는다.
- 모든 NR–Anchor 조합 허용, SA/NSA/LTE 혼합 시작 차단, `REM_DEST`별 상태 의미, 고수준 NSA Handover/Recall Change API 경계, 첫 TC Recall lifecycle, RawData 논리 경로·filename과 두 source template mapping, 전역 배타 operation 동작, 현재 세션 Screenshot 목록, Range 7~9 제외는 다시 미결정 항목으로 올리지 않는다.

## 12. 검증 시나리오 작성 시 포함할 관점

이 절은 테스트를 실행하라는 지시가 아니라, 후속 명세와 Jira의 검증 누락을 막기 위한 체크리스트다.

### NSA

- SA와 NSA 생성 진입점 및 화면 상태가 서로 섞이지 않음
- NSA만 Anchor가 필수이고 SA/LTE에는 허용되지 않음
- 모든 지원 NR Band와 10개 Anchor 조합이 허용됨
- NSA Anchor 설정은 모든 Band에서 Test Channel `MID`, Bandwidth `5 MHz`, RB Size `1`, RB Offset `0`, Modulation `QPSK`이고 별도 UI 입력이 없음
- Python의 Anchor 매핑은 Band에서 UL/DL Channel만 lookup하며 고정 profile을 파생하거나 Params로 전송하지 않음
- SA/NSA/LTE 혼합 Queue가 장비 command 전 시험 시작 단계에서 차단됨
- NSA TestCase 저장·로드 시 `anchor_band`가 보존되고 누락·미지원 값이 차단됨
- 첫 NSA TC에서 단일 `NSA Handover` 내부의 Anchor 준비와 NR Call helper로 NR SCG를 자동 연결하고 측정 전 `8000A == 8`, `8821C == 6`을 확인함
- Anchor 동일 변경은 기존 `NR Handover`, Anchor 변경은 단일 `NSA Handover`를 호출함
- SCG Release 완료는 `REM_DEST 8000A`의 최종 `6`으로 판정하고 `8821C == 6`만으로 완료 처리하지 않음
- Anchor HO는 `DLCHAN`만 변경하고 `REM_DEST 8821C` 최종 `6` 및 고정 profile read-back으로 판정하며 `CHBWDLCHAN`을 사용하지 않음
- `NSA Handover` 내부 NR Call helper는 `REM_DEST 8000A` 최종 `8`과 Anchor `8821C == 6` 유지로 판정함
- 과도 상태 `8000A 7/9`, `8821C 13`을 관측하지 못해도 terminal 상태가 충족되면 성공함
- 모든 단계가 이전 destination에 의존하지 않고 `REM_DEST`를 명시적으로 재설정함
- `NSA Handover` 성공은 Default OK의 `status`만으로 판정하고 Result 유무·형식을 무시함
- `NSA Handover` 실패는 Default Error의 `status`와 `Error.message`로 처리하며 별도 failure envelope를 요구하지 않음
- 같은 NR Band의 여러 Anchor 결과가 한 NR workbook에서 서로 덮어쓰지 않음
- Anchor cell 기록과 기존 Plot naming 불변

### RawData와 Recall

- 확정 EUT 폴더와 `{EUT Name}_CE Main_Radiation_{NR|LTE}.xlsx` 경로 계산
- NR은 `NR_Rawdata_.xlsx`, LTE는 `_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx`를 source로 복사함
- 신규 EUT 파일 생성, 기존 EUT 재사용, 잘못된/손상/열린 파일
- source template 누락과 result directory 권한 오류 시 FSM 미시작
- 첫 실행 TC와 `start_index > 0`의 첫 TC에서 Recall command를 보내지 않고 해당 ID를 세션 초기값으로 기록함
- 같은 Recall에는 command를 보내지 않고 변경된 Recall에만 고수준 `Recall Change`를 호출함
- Recall Change 성공 후에만 적용 ID를 갱신하고 실패 시 Factor/측정으로 진입하지 않음
- Call 단절 시 Recall을 다시 적용하거나 조회하지 않고 기존 Call만 재실행함
- Recall ID와 Anchor Band가 함께 바뀌면 둘 다 적용한 뒤 NSA 최종 연결 상태를 확인하고 성공 후에만 적용 Recall ID를 갱신함
- TC/model이 제공하는 Recall ID를 불투명 식별자로 사용하고 Generation 혼합 Queue의 시작을 차단함

### Manual Test

- 장비별 연결 조합의 capability 활성화
- 연결 해제/실패 중 진행 operation 정리
- FSV field validation, 단위, 기본 RMS
- Turntable 0/360, 180° 경계, Stop/timeout/error
- 1m/3m Horn/Bilog target mapping과 높이 제어 부재
- Semi Auto에 Single Sweep/Capture가 호출되지 않고 Max Hold가 유지됨
- Single/N-Capture 충돌 시 장비 command 미호출
- N-Capture 중간 실패 시 성공 파일 보존과 이후 중단
- 현재 실행 세션의 성공 파일만 최신순 목록에 표시하고 선택 이미지 표시
- 자동시험/Manual/Connect/Set/TDF/RF 장비 operation 배타 동작과 busy 안내

## 13. 근거 파일 지도

| 관심 영역 | 우선 확인 파일 |
|---|---|
| TestCase/CSV/Anchor | `src/app/models/test_case.py`, `src/app/models/enums.py`, `src/app/core/tc_loader.py`, `src/app/core/tc_validator.py` |
| NR/NSA/LTE 생성 UI | `src/app/ui/test_manager_panel.py`, `src/app/ui/nr_select.py`, `src/app/ui/lte_select.py` |
| NSA/Recall FSM | `src/app/core/fsm/call_routing.py`, `src/app/core/fsm/states/nr_setup.py`, `src/app/core/fsm/states/session.py`, `src/app/core/fsm/states/transition.py`, `src/app/core/fsm/engine.py` |
| Command/Mock | `src/app/net/commands.py`, `src/app/net/protocol.py`, `src/app/net/tcp_client.py`, `src/app/net/mock_lv_server.py` |
| RawData/Excel | `src/app/models/test_run_settings.py`, `src/app/core/runner.py`, `src/app/report/excel_writer.py`, `src/app/report/report_writer.py`, `resources/templates/NR_Rawdata_.xlsx`, `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx` |
| NSA result/Plot | `src/app/report/template_map.py`, `src/app/report/screenshot_store.py` |
| Manual Test | `src/app/ui/manual_test_panel.py`, `src/app/ui/main_window.py`, `src/app/ui/manual_marker_dialog.py`, `src/app/models/test_range.py`, `src/app/net/commands.py`, `src/app/net/mock_lv_server.py`, `src/app/net/tcp_client.py`, `src/app/report/screenshot_store.py`, 신규 core service 후보 |
| Turntable/Event 참고 | `src/app/core/fsm/states/measurement/common.py` |
| 설정/패키징 | `src/app/config/file_dialog_directory_settings.py`, `app_config.py`, `CE_NR_Radiated.spec` |
| 과거 Recall 요구 | `docs/NEXT_VERSION_SRS_AND_JIRA_BACKLOG.md:63-84`, `340-430` |

## 14. PM 결론

v3.0은 세 Epic으로 관리하되 NSA 정식 지원을 우선한다. 이번 검토로 NR–Anchor 조합과 고정값, Generation 혼합 차단, `REM_DEST`별 상태 의미, 같은/다른 Anchor routing, 고수준 `NSA Handover`·`Recall Change` API 경계, 첫 TC Recall lifecycle, RawData 논리 경로·filename과 source asset, Manual 장비 배타 정책, Screenshot 목록 source, Range 7~9 범위가 확정됐다. 후속 Agent는 이 항목을 다시 Discovery 질문으로 되돌리지 않는다.

현재 확정사항으로 NSA/Recall과 RawData SRS 및 Jira Issue를 작성할 수 있으며, 추가 제품 결정 blocker는 없다. 첫 NSA TC와 Recall+Anchor 동시 변경의 내부 순서, 실제 TCP/JSON 표현과 timeout·retry 값은 각각의 Python/LV 구현 Issue에서 설계하고 벤치 검증한다. 이를 별도 ‘결정을 위한 Issue’로 만들지 않는다.

`anchor_band` CSV field와 결과 mapping도 요구사항이 아니라 구현이 남은 상태다. NSA에는 Anchor가 필수이고 결과는 NR Band 옆 cell에 `B*` 형식으로 기록한다는 확정 기준으로 관련 Story를 작성한다.

RawData source는 이미 `resources/templates`에 있다. NR SA/NSA는 `NR_Rawdata_.xlsx`, LTE는 `_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx`를 사용한다. 남은 일은 asset을 추적하고 runtime resolver, 기존 파일 reuse와 오류 처리, dev/frozen 동작을 구현·검증하는 것이다.

NSA FSM과 Recall FSM은 확정된 고수준 MT8000A workflow와 하나의 승인된 TCP/JSON 계약 아래에서 통합한다. Python과 실제 LabVIEW Issue는 분리하되, Python이 LV 내부 primitive sequencing을 다시 구현하지 않는다. Manual Test의 상세 계약은 NSA 개발과 분리해 Manual 착수 시 논의한다.
