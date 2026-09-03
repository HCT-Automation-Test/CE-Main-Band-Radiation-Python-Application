# v3.0 개발 요구사항 PM 검토 및 후속 Agent 인수인계

> 이 문서는 최종 개발 요구사항 명세서(SRS/PRD)나 Jira 백로그가 아니다.  
> 요구사항 관리 Agent가 명세를 작성하고 Jira 관리 Agent가 실행 가능한 백로그를 만들 수 있도록, 사용자 입력과 현재 구현의 차이, 확정 정책, 구현 의존성과 후보 작업 묶음을 정리한 PM 검토 자료다.

## 1. 문서 정보와 사용 원칙

| 항목 | 내용 |
|---|---|
| 계획 대상 | v3.0(사용자 지정 작업명) |
| 검토 기준일 | 2026-08-24 (Asia/Seoul) |
| Anchor/Command 계약 정정 | 2026-08-24 — MID/5 MHz/RB Size 1/RB Offset 0/QPSK, Band→UL/DL lookup, `ULCHAN` 전용 HO, LV 내부 NR Call helper 재사용 단일 composite 반영 |
| 구현 상태 동기화 | 2026-08-31 — `H2026E014-41/44/45/43/42` 기준, RawData source·결과 lifecycle·FSM 준비·수동 선택 제거·회귀 검증 반영 |
| Recall ID 정정 동기화 | 2026-09-03 — `H2026E014-47`, 코드 커밋 `0f475e7`, NR SA/NSA×FDD/TDD 네 ID와 `.PRM` 제외 계약 반영. 대상 `407 passed`, 기본 전체 `915 passed, 380 skipped` |
| 초기 저장소 기준 | `main` / `7a80d3cdead2b46ac7f7f1fc4055a0ed1b8d31ca` |
| 작업 트리 | 검토 시작 시 clean |
| 검토 방식 | 코드, 문서, 테스트 코드, Git 이력의 정적 검토 |
| 실행 검증 | RawData v3.0 기준 기본 전체 `893 passed, 380 skipped`, Qt focused `64 passed`, RawData/path focused `62 passed`, PyInstaller 원본 위치·시트·SHA-256 검증 |
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

- 초기 PM 검토에서는 `pytest`를 포함한 테스트를 실행하지 않았다.
- H2026E014-39 구현 상태 동기화에서는 report 테스트와 기본 전체 테스트를 실행했으며, 실제 LabVIEW/실장비 검증은 수행하지 않았다.
- H2026E014-41/44/45/43/42에서는 기본 전체, 승인된 Qt focused, RawData/path focused와
  PyInstaller one-folder 원본 asset 검증을 수행했다. 실제 LabVIEW/실장비는 실행하지 않았다.
- 요구사항 정리와 Jira 백로그 생성 작업도 테스트 실행을 필요로 하지 않는다.
- 후속 구현 검증은 사용자와 실행 환경을 확인한 뒤 관련 범위만 대상으로 진행한다.
- 다른 작업 창 종료 문제가 있으므로 전체 `pytest`를 기본 검증으로 무조건 실행하지 않는다.
- 실제 LabVIEW/실장비 시험은 별도 승인된 환경과 작업으로 분리한다.

## 2. Executive Summary

v3.0은 다음 세 Epic 후보로 정리할 수 있다.

1. NSA 정식 지원
2. 시험 운영 편의 개선
3. Manual Test

사용자 일정 기준으로 NSA 정식 지원과 시험 운영 편의 개선은 테스트 대기 중이며, 현재 다음 계획 대상은 Manual Test다. Manual Test의 제품 요구사항은 4.4를 기준으로 하고, command명·payload·Python/LV 책임 경계는 후속 Interface Contract에서 확정한다.

NSA Track의 주요 작업축은 다음 두 가지다.

1. NSA TestCase의 Anchor Band property·CSV·결과 매핑
2. 확정된 MT8000A 고수준 workflow의 TCP/JSON 계약을 구현하고 terminal 상태 polling을 벤치에서 검증

EUT 기반 RawData 파일 lifecycle은 H2026E014-41/44/45/43/42에서 구현·검증됐다. 기준 양식은
`resources/templates`에 추적되며 dev/frozen resolver, 기존 결과 재사용, 신규 안전 복사,
`PrepareReport` FSM 통합과 수동 Excel 선택 제거까지 완료됐다.

### 2.1 현재 상태 요약

| 영역 | 현재 상태 | v3.0 핵심 Delta |
|---|---|---|
| NR SA | Harmonic/In-band/Bilog 자동시험 경로 구현 | 생성 화면을 LTE형 통합 화면으로 개선 |
| NR NSA | Anchor-aware TestCase/CSV, SA·NSA 분리 UI, 첫 TC `NR Call`, Anchor 변경 전용 `NSA Handover` Python routing, RawData 최초 Anchor 기록 구현 | 실제 LV·승인 장비 통합 인수와 Recall+Anchor 동시 변경 자동화 |
| LTE | 모델, 생성 UI, Call/Handover, 결과 기록이 현재 코드에 존재 | 직접 개발 대상 아님. NSA UI와 Anchor 데이터의 참고 기반 |
| TDF | Band Group 기반 자동 적용 구현 | 기존 동작 유지 |
| MT8000A Recall | 식별자 파생과 TC 간 변경 감지는 존재하나 실제 변경은 수동 팝업 | 첫 실행 TC의 Recall ID를 세션 초기값으로 간주하고 이후 ID 변경 시에만 고수준 Recall Change 수행 |
| RawData | EUT Name 기반 자동 생성·재사용, FSM worker 준비와 Excel live monitoring 구현 | 실제 장비 없이 완료 가능한 회귀·패키징 검증 완료 |
| 자동시험의 Manual Marker | 자동시험 FSM에 결합된 수동 마커 다이얼로그 존재 | Manual Test와는 별개이며 일부 UI/명령만 재사용 |
| Manual Test | 내비게이션과 빈 패널만 존재 | FSV40 설정·Sweep/Marker/Turntable/Mast/Semi Auto/Capture 개발 |
| Range | Range 1~6의 정식 TestCase 설정 모델 | Manual Test preset에 Range 7~9를 추가하되 정식 TestCase 매핑에는 사용하지 않음 |
| 실제 LV | 실행 파일만 있고 소스는 저장소에 없음 | Python Issue와 별도 LV Issue 및 벤치 검증 필요 |

### 2.2 이번 검토에서 확정된 정책

| 정책 ID | 확정 내용 | 명세·백로그 반영 |
|---|---|---|
| POL-NSA-01 | 모든 NR Band는 지원 Anchor Band `B1/B3/B7/B5/B8/B20/B28/B38/B40/B41`과 모두 조합할 수 있다. 별도 NR–Anchor 허용 조합표를 두지 않는다. | Anchor allowlist만 검증하고 NR–Anchor 조합 제한은 두지 않는다. |
| POL-NSA-02 | 한 실행 세션에서 `NR_SA`, `NR_NSA`, `LTE`를 혼용하지 않는다. 두 종류 이상이 섞인 Queue는 LTE 혼용 검증과 같은 시점인 시험 시작 단계에서 차단한다. | 기존 validator가 SA/NSA를 같은 NR family로 허용하는 동작을 변경한다. 세대 간 전환 FSM은 이번 범위에서 만들지 않는다. |
| POL-NSA-03 | NSA 생성 화면은 NR Band 열 옆에 LTE Anchor Band 선택 열을 둔다. LTE Anchor는 모든 Band에서 Test Channel `MID`, Bandwidth `5 MHz`, RB Size `1`, RB Offset `0`, Modulation `QPSK`로 고정하며 별도로 입력받지 않는다. | Python의 Anchor 파생 책임은 `Anchor Band → UL/DL Channel` lookup뿐이다. 고정 profile은 command Params로 보내지 않으며 LV가 내부 read-back으로 검증한다. |
| POL-MT-01 | `CALLSTAT?`는 `REM_DEST`별 상태 머신으로 해석한다. SCG Release 완료는 `8000A == 6`, NSA 연결 완료는 `8000A == 8`, Anchor 연결 유지는 `8821C == 6`으로 판정한다. | `7/9/13` 과도 상태 관측을 성공 조건으로 요구하지 않고 각 단계의 최종 상태를 polling한다. `8821C == 6`만으로 SCG Release 완료를 판정하지 않는다. |
| POL-MT-02 | 첫 NSA TC는 목표 Anchor가 장비에 미리 준비되어 있다고 간주하고 기존 `NR Call`을 사용한다. 연속 NSA TC의 Anchor가 같으면 기존 `NR Handover`, Anchor가 바뀌면 신규 고수준 `NSA Handover` 단일 composite를 호출한다. LV는 SCG Release → LTE Anchor `ULCHAN` 변경·고정 profile 검증 → 기존 NR Call helper 재사용 → SCG Addition·최종 상태 확인을 수행한다. | Python은 Anchor 변경 시에만 `NSA Handover` 한 번을 호출하며 `NR Call` 또는 `CALLSO`/`CALLSA`/`CALLSTAT?`/`REM_DEST` 순서를 추가로 조합하지 않는다. 기존 `NR Call` 외부 request는 현행을 유지한다. |
| POL-MT-03 | `Recall Change`는 NSA Handover와 분리된 고수준 LV workflow다. 첫 실행 TC에는 Recall을 호출하지 않고 그 TC의 ID를 세션 초기값으로 사용하며, 이후 ID가 바뀔 때만 실행하고 성공 후에만 적용 ID를 갱신한다. | `start_index > 0`이면 해당 TC를 첫 실행 TC로 본다. Call 단절 시 Recall은 유지된 것으로 보고 기존 Call만 재실행하며 신뢰 가능한 조회 방법 전에는 현재 Recall 조회를 요구하지 않는다. |
| POL-MT-04 | 외부 API 경계는 기존 `NR Call`, 신규 `NSA Handover`, 신규 `Recall Change`, 기존 `Check Call Status`의 의미 기반 workflow다. | LV helper는 매 단계 `REM_DEST`를 명시한다. `NSA Handover`는 Default Response를 사용하고 Python은 최종 `status`만 판정한다. |
| POL-RAW-01 | RawData 결과 파일의 논리 경로는 `{EUT 결과 기준 root}/{EUT Name}/{EUT Name}_CE Main_Radiation_{NR\|LTE}.xlsx`다. `NR` 파일은 NR SA/NSA에, `LTE` 파일은 LTE에 사용한다. | 개발 root=`~/Desktop`, frozen root=EXE 폴더. EUT Name은 resolver에서 안전성을 검증한다. |
| POL-RAW-02 | NR SA/NSA source는 `resources/templates/NR_Rawdata_.xlsx`, LTE source는 `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx`다. | 두 asset은 Git 추적 및 PyInstaller 포함·위치·시트·SHA-256 검증 완료. |
| POL-MAN-01 | Manual Test 기능은 장비 연결 상태로 활성화하며 TestCase·Call·Filter 설정과 관계없이 사용할 수 있다. 장비 조작에는 Filter Box와 동일한 배타 정책을 적용한다. | 경쟁 장비 command는 보내지 않고 busy 상태를 알린다. 진행 중인 Manual operation의 Stop은 잠금 중에도 허용한다. |
| POL-MAN-02 | Manual Test의 FSV40 preset은 Range 1~9를 제공한다. Range 7~9는 Start/Stop Frequency와 RBW/VBW만 정의하며 정식 TestCase Range 매핑에는 사용하지 않는다. | Range 7~9의 미확정 속성을 임의로 만들지 않고 Manual preset 범위에만 반영한다. |
| POL-MAN-03 | Capture는 사용자가 저장 폴더와 기준 파일명을 지정한다. 기존 파일은 덮어쓰지 않으며, 성공한 파일만 현재 앱 실행 세션의 목록에 최신순으로 표시한다. | Single/N-Capture의 사전 충돌 확인과 경고, 부분 성공 보존을 Acceptance Criteria에 포함한다. 저장 폴더 전체는 스캔하지 않는다. |
| POL-MAN-04 | Detector Mode는 확정된 9종을 제공하고 기본값은 `RMS`로 한다. `Next Peak Search Level`은 기존 Marker command의 `Excursion`으로 사용한다. UI는 명백한 입력 오류만 차단하며 장비별 상세 제한은 LV/FSV40 오류로 처리한다. | FSV40 상세 허용 범위를 UI에 임의로 고정하지 않고 기존 Marker parameter mapping을 재사용한다. |
| POL-MAN-05 | Saturation Time은 FSV40 설정에서 입력하고 Set으로 적용한다. Semi Auto는 별도로 입력받지 않고 적용된 값만큼 Continuous Sweep 후 대기한다. 초기 기준점은 `현재 각도 <= 180° → 0°`, `> 180° → 360°`, 속도 6으로 정렬하며 전 과정에서 Stop할 수 있다. | Stop 후 남은 단계를 실행하지 않으며 회전 중이면 Turntable을 정지한다. |
| POL-PRIO-01 | Manual Test의 제품 동작은 4.4로 확정한다. command명·payload·Python workflow·LV 복합 명령 단위는 후속 Interface Contract에서 확정한다. | 확정된 UX를 Refinement 대상으로 되돌리지 않는다. 기술 계약만 후속 작업으로 관리한다. |

RawData filename의 `*` 표기는 Markdown 강조 기호로 해석했으며 실제 파일명 문자로 사용하지 않았다. 이 문서의 canonical filename은 `{EUT Name}_CE Main_Radiation_{NR|LTE}.xlsx`다.

### 2.3 SRS와 Jira 작성 기준

현재 확정사항으로 NSA/Recall의 SRS 및 Jira Issue를 작성할 수 있다. RawData는
H2026E014-41/44/45/43/42에서 구현·검증 완료됐으며 추가 Discovery Issue를 만들지 않는다.

- 첫 NSA TC는 목표 LTE Anchor가 장비에 미리 준비되어 있다고 간주하고 NR SA와 동일한 기존 `NR Call`로 NR SCG를 연결해야 한다.
- Recall ID와 Anchor Band가 함께 바뀌면 목표 Recall과 Anchor를 모두 적용하고 NSA 최종 연결 상태를 복구해야 한다. 세부 단계 순서는 `Recall Change` LV 구현 Issue에서 설계·검증한다.
- RawData는 기존 결과 파일이 있으면 재사용하고 없으면 확정 source template을 복사한다.
  경로 안전성, 파일 열림·손상, resource lookup, FSM/UI와 packaging은
  H2026E014-41/44/45/43/42에서 검증됐다.

실제 TCP/JSON 명칭·필드, LV helper 순서, timeout·polling·retry 수치와 파일 처리 알고리즘은 관련 구현 Issue의 interface contract·subtask·DoD로 관리한다. 성공 판정은 확정된 terminal 상태 polling을 사용하며 별도의 stable-state 요구는 만들지 않는다. Manual Test는 4.4의 제품 요구사항을 사용하고 command명·payload·Python/LV 책임 경계만 후속 Interface Contract에서 확정한다.

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
- Range 7~9는 Manual Test preset에만 포함하고 정식 TestCase Range 매핑에는 추가하지 않는다.
- WCDMA/GSM Test Case와 자동시험 구현은 이번 범위가 아니다.
- `src/app/ui/generated/**`는 직접 수정하지 않는다. 이번 대상 화면은 현재 Python 코드로 동적 구성된다.

### 3.3 문서와 코드의 불일치

| 항목 | 확인 내용 | PM 처리 |
|---|---|---|
| 버전 | `README`, `pyproject.toml`, `app.__version__`은 여전히 `1.0.1`; 사용자는 v3.0 계획을 요청 | Jira `fixVersion`과 배포 버전 체계를 별도로 확인 |
| NSA 상태 | 첫 NSA TC는 기존 `NR Call`, 연속 TC의 Anchor 변경은 `NSA Handover`, 같은 Anchor의 NR 설정 변경은 `NR Handover`로 라우팅 | 첫 Anchor는 외부 절차로 사전 준비하며 수동 확인 state나 런타임 검증을 두지 않음 |
| LTE 상태 | 과거 UI 문서는 LTE 버튼 미결선으로 설명하지만 현재 코드는 LTE UI를 연결 | 코드 기준으로 완료/재사용 상태 처리 |
| Recall 식별자 | NR은 `5GNR_SA_FDD/5GNR_SA_TDD/5GNR_NSA_FDD/5GNR_NSA_TDD`, LTE는 `LTE_FDD/LTE_TDD`를 사용 | `.PRM` 확장자 없이 모델 값을 `Recall Change` interface에 그대로 전달한다. |
| NSA RawData | H2026E014-39에서 `A7=NR Band`, `B7=최초 Anchor Band` 기록과 writer 실행 단위 최초 값 유지 구현 | SRS v5와 report 문서 동기화 완료, 실제 LV 통합 인수에서 회귀 확인 |

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
| PM-NSA-FSM-02 | 첫 NSA TC는 기존 `NR Call`을 사용한다. 연속 NSA TC의 LTE Anchor Band가 바뀔 때만 신규 고수준 `NSA Handover` 단일 composite로 `NR SCG Release → LTE Anchor UL Channel Handover·검증 → 기존 NR Call helper 재사용 → NR SCG Addition`을 수행한다. |
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
→ ULCHAN <목표 UL Channel>
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

`NSA Handover` wire request는 `Anchor UL Channel`만 추가한다. LV 내부에서는 해당 값으로 `ULCHAN`만 변경한다. Anchor BW는 항상 `5 MHz`이므로 `CHBWDLCHAN`을 사용하지 않는다. `CHBWDLCHAN`으로 BW를 다시 적용해 RB 설정이 바뀌는 부작용을 만들지 않으며, BW/RB/Modulation 고정값은 Params로 전달하지 않고 Handover 후 LV 내부 read-back 검증 대상으로 취급한다. 기존 LTE 전용 `LTE Handover`의 `CHBWDLCHAN` 계약은 이 정책의 대상이 아니다.

`NSA Handover`는 내부에서 기존 NR Call helper를 재사용하는 단일 composite다. 성공 조건은 중간 단계의 SCG Release 완료 `8000A CALLSTAT == 6`, Anchor 연결 유지 `8821C CALLSTAT == 6`, 목표 DL/UL Channel과 고정 profile read-back 일치, 최종 SCG Addition 완료 `8000A == 8`과 Anchor `8821C == 6` 유지다.

NSA TC 사이의 routing은 다음으로 확정한다.

```text
LTE Anchor Band 동일 → 기존 NR Handover
LTE Anchor Band 변경 → 신규 고수준 NSA Handover 단일 composite
```

첫 NSA TC는 선택 Anchor가 장비에 미리 준비되어 있다고 간주하고 기존 `NR Call`을 사용한다.
`NSA Handover`는 이전에 실행한 NSA TC와 Anchor Band가 달라진 경우에만 사용한다.

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
| 신규 `NSA Handover` | SCG Release, LTE Anchor `ULCHAN` 변경, Anchor 고정 profile read-back 검증, 기존 NR Call helper를 재사용한 SCG Addition과 최종 상태 확인 |
| 신규 `Recall Change` | Generation별 Call/SCG 정리, Recall, 기존 Call 재사용 재연결 |
| 기존 `Check Call Status` | 모니터링과 장애 진단에 재사용 |

공유 TCP/JSON 계약의 command별 입력은 다음으로 고정한다.

| Command | request Params | 명시적으로 보내지 않는 값 |
|---|---|---|
| 기존 `NR Call` | 현행 유지: `Band`, `BandWidth`, `Center Channel`, `RB Size`, `RB Offset`, `Modulation`, `Max Retry Count`, `Waiting Time` | LTE Anchor 설정 전체 |
| 신규 `NSA Handover` | 기존 `NR Call` 8개 필드: `Band`, `BandWidth`, `Center Channel`, `RB Size`, `RB Offset`, `Modulation`, `Max Retry Count`, `Waiting Time`; 신규 Anchor 제어값: `Anchor UL Channel` | `Anchor Band`, `DL Channel`, Anchor `BandWidth`, `RB Size`, `RB Offset`, `Modulation`, `Test Channel` |

Python은 `Anchor Band`를 고정 MID/5 MHz 기준의 목표 UL/DL Channel로 lookup한다. Wire request에는 장비 변경에 사용하는 `Anchor UL Channel`만 넣고 `DL Channel`은 보내지 않는다. Anchor의 `5 MHz/RB Size 1/RB Offset 0/QPSK`는 Band별 mapping 결과가 아니라 모든 Band에 동일한 LV 내부 검증 상수다.

`NSA Handover`는 Default Response를 사용한다. Python은 최종 `status`만 신뢰하며 `Result`가 없거나 어떤 형식이더라도 무시한다. 성공은 `status="ok"`, 실패는 `status="error"`와 `Error.message`로 표현하며 성공 read-back Result와 별도 failure envelope는 요구하지 않는다. LV 내부의 단계별 terminal 상태와 profile 검증 책임은 유지된다.

`CALLSO`, `CALLSTAT?`, LTE Anchor Handover, Parameter Recall과 기존 NR Call 로직은 LV 내부 helper로 재사용한다. 각 workflow는 단계마다 `REM_DEST`를 명시적으로 설정하며 이전 destination에 의존하지 않는다. Python은 `NSA Handover` 단일 composite만 호출하고 NR Call 또는 LV primitive 순서를 제어하지 않는다. `Check Call Status` 재사용은 workflow 내부 terminal polling을 Python polling으로 대체한다는 의미가 아니다.

`NSA Handover`의 실제 command, Params와 Default Response는 Python/LV 구현 Issue의 공유 interface contract로 관리한다. Python은 실패 envelope를 해석하지 않고 Default Error의 `Error.message`만 오류 표시에 사용한다.

### 4.3 시험 운영 편의 개선

| 임시 코드 | 확정 입력 |
|---|---|
| PM-RAW-01 | 사용자가 RawData 파일을 UI에서 직접 선택하지 않는다. |
| PM-RAW-02 | RawData 결과 파일은 EUT 결과 기준 root 아래 `{EUT Name}` 폴더에서 자동으로 찾는다. |
| PM-RAW-03 | 결과 파일명은 `{EUT Name}_CE Main_Radiation_{NR\|LTE}.xlsx`를 사용하며 NR SA/NSA는 `NR`, LTE는 `LTE` 파일로 구분한다. |
| PM-RAW-04 | 대응 파일이 없으면 NR SA/NSA는 `resources/templates/NR_Rawdata_.xlsx`, LTE는 `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx`를 복사해 결과 파일을 만든다. |
| PM-RCL-01 | v2.0에서 연기된 MT8000A Parameter Recall 요구는 4.2의 세션 정책으로 대체한다. 첫 TC에는 호출하지 않고 세션 중 Recall ID 변경만 자동 처리한다. |
| PM-RCL-02 | 첫 실행 TC의 Recall ID를 세션 초기값으로 사용하고 이후 목표 ID가 달라질 때만 신규 고수준 `Recall Change`를 호출한다. |
| PM-RCL-03 | `Recall Change` 성공 후에만 적용 ID를 갱신한다. Call 단절 시 Recall은 유지된 것으로 보고 Recall 없이 기존 Call만 재실행한다. |

과거 v2 문서의 “첫 TestCase Recall 자동 적용”과 단순 `Call Stop → Recall → Call Start` 순서는 이번 4.2 확정사항으로 대체한다. Recall 문자열을 프로그램이 해석하지 않는 불투명 식별자로 다루는 원칙은 유지하되, 과거 Recall ID 목록은 현재 코드와 충돌하므로 그대로 복사하지 않는다.

### 4.4 Manual Test

#### 장비별 활성화

| 기능 | 활성 조건 |
|---|---|
| FSV40 설정, Sweep, Marker, Capture | `FSV40 == connected` |
| Turntable 및 3m Mast | `CO3000 == connected` |
| 1m Mast | `3D Controller == connected` |
| Semi Auto | `FSV40 == connected` 그리고 `CO3000 == connected` |

각 기능은 위 장비 연결 조건을 충족하면 TestCase 존재 여부, Call 상태, Switch Box Filter 설정과 관계없이 사용할 수 있다.

장비 조작에는 기존 Filter Box와 같은 배타 정책을 적용한다. 다른 장비 operation이 진행 중이면 Manual 장비 조작을 시작하지 않고 busy 상태를 알리며, Manual operation 중에는 다른 장비 operation을 시작할 수 없다. 잠금 중에도 현재 Manual operation의 Stop은 허용한다. 입력 편집과 저장된 Screenshot 열람처럼 장비 command를 발생시키지 않는 동작은 허용한다.

#### FSV40 설정과 Sweep

- Frequency Range preset은 Range 1~9를 사용한다.
- `Custom Off`에서는 선택한 Range의 Start/Stop Frequency, RBW, VBW를 사용하고, `Custom On`에서는 네 값을 직접 입력한다.
- Sweep Point, Sweep Time, Saturation Time, Attenuation, Detector Mode, Line Limit를 직접 입력한다.
- Detector Mode는 `Auto Peak`, `Positive Peak`, `Negative Peak`, `Sample`, `RMS`, `Average`, `Quasipeak`, `CISPR Average`, `RMS Average`를 제공하며 기본값은 `RMS`다.
- Preset 버튼은 LabVIEW를 통해 FSV40 `*RST`를 수행한다.
- Set 버튼은 Saturation Time을 포함한 입력 설정을 적용한다.
- Single Sweep와 Continuous Sweep를 제공한다.

필수값 누락, 숫자 형식 오류, Start Frequency가 Stop Frequency 이상인 경우, 음수 주파수나 0 이하의 RBW/VBW처럼 명백한 입력 오류만 UI에서 차단한다. FSV40의 상세 허용 범위와 option·설정 조합 제약은 UI에 별도로 고정하지 않고 LV/FSV40 오류를 사용자에게 표시한다.

#### Marker

- Target Marker를 선택한다.
- Next Peak Search Level을 입력하며 기존 Marker command의 `Excursion` 값으로 사용한다.
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

Semi Auto 실행 시 Saturation Time을 다시 입력받지 않고 마지막 Set으로 적용된 값을 사용한다.

```text
현재 각도 조회
→ 현재 각도가 180° 이하면 0°, 초과면 360°로 속도 6 초기 정렬
→ Clear Write
→ Max Hold
→ Continuous Sweep
→ Set으로 적용된 Saturation Time 대기
→ 입력 속도로 반대 기준점까지 한 바퀴 회전
→ Max Hold 유지
```

Semi Auto 전 과정에서 Stop할 수 있다. Stop하면 이후 단계를 실행하지 않고, Turntable 회전 중이면 회전을 정지한다. Single Sweep와 자동 Screenshot은 수행하지 않으며 정상 완료 후 Max Hold를 유지한다.

#### Screenshot Capture

- 사용자는 저장 폴더와 기준 파일명을 지정하며 결과 형식은 PNG다.
- Single Capture는 현재 FSV40 화면을 `{기준 파일명}.png`로 저장한다. 같은 파일이 있으면 저장하지 않고 경고한다.
- N-Capture는 Interval과 N Shots를 입력받고 `{기준 파일명}_001.png`, `{기준 파일명}_002.png`, ... 순으로 저장한다.
- 생성 예정 파일 중 하나라도 있으면 경고하고 Capture 전체를 시작하지 않는다.
- 첫 Capture 후 각 다음 Capture까지 `Clear Write → Max Hold → Interval Wait → Capture`를 반복한다.
- 중간 실패 시 이후 작업을 중단하고 이미 성공한 파일은 유지한다.
- 성공한 Screenshot을 최신순 목록에 추가하고 선택 이미지를 표시한다.
- 목록에는 현재 앱 실행 세션에서 성공한 Screenshot만 표시하며 기존 저장 폴더 전체는 스캔하지 않는다.

#### Range 7~9

| Range | Start Frequency | Stop Frequency | RBW | VBW |
|---|---:|---:|---:|---:|
| 7 | 1000 MHz | 3000 MHz | 0.1 MHz | 0.3 MHz |
| 8 | 1000 MHz | 4000 MHz | 3 MHz | 3 MHz |
| 9 | 3000 MHz | 4000 MHz | 3 MHz | 3 MHz |

Range 7~9는 Manual Test preset에 포함하지만 정식 TestCase Range 매핑에는 사용하지 않는다. 위 네 값 이외의 Range 속성은 이번 요구사항에서 임의로 정의하지 않는다.

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

NSA Call 전환 흐름은 첫 TC와 연속 TC를 구분한다.

```text
첫 NSA TC
  NRCallConnect
  → 기존 측정

다음 NSA TC
  Recall ID 변경 → RecallChange
  Recall 동일 + Anchor 변경 → NSAHandover
  Anchor 동일 + NR Call 설정 변경 → Handover
  → 기존 측정
```

- 첫 NSA TC는 SA와 동일하게 `NRCallConnectState`에서 기존 `NR Call` facade를 호출한다.
- `NSAHandoverState`는 이전에 실행한 NSA TC와 비교해 Anchor가 변경된 경우에만 단일 `NSA Handover` facade를 호출한다.
- Anchor가 같고 NR Call 설정만 변경되면 일반 `HandoverState`가 기존 `NR Handover` facade를 호출한다.
- 첫 TC의 목표 Anchor는 장비에 사전 준비된 것으로 간주하며 수동 확인 state나 런타임 검증을 두지 않는다.
- SA↔NSA generation 변경은 현재 TODO/no-op이지만, v3.0에서는 혼합 Queue를 시작 단계에서 차단하므로 세대 간 전환 FSM을 구현하지 않는다. 필요한 변경은 validator와 시작 차단 안내다: `src/app/core/fsm/states/session.py:89`.
- 기존 `LTE Handover`를 재사용하지 않고 NSA 전용 고수준 `NSA Handover` workflow를 제공해야 한다. NSA Anchor는 BW가 고정이므로 `CHBWDLCHAN` 대신 `ULCHAN`만 변경한다: `src/app/net/commands.py:183`.

목표 NSA 전환 routing은 다음과 같다.

| 이전 TC 대비 변경 | Python FSM이 호출할 외부 workflow | LV 내부 완료 판정 |
|---|---|---|
| LTE Anchor 동일, NR Call 설정 변경 | 기존 `NR Handover` | 기존 NR Handover 완료 조건 |
| 첫 NSA TC | 기존 `NR Call` | 목표 Anchor가 사전 준비됐다는 전제에서 기존 NR Call 완료 조건 |
| LTE Anchor 변경 | 신규 `NSA Handover` 단일 composite | 중간=`8000A == 6`, `8821C == 6`, Anchor profile read-back 일치 → 내부 NR Call helper 후 최종=`8000A == 8`, `8821C == 6` |
| Recall ID 변경 | 신규 `Recall Change` | Generation별 정리·Recall·재연결 후 Generation별 최종 연결 상태 |

`8000A`의 `7/9`와 `8821C`의 `13`은 과도 상태이므로 관측 누락이 실패가 아니다. 각 LV workflow는 매 단계 `REM_DEST`를 다시 설정하고 terminal 상태를 polling한다. 첫 NSA TC는 기존 `NR Call` 계약을 그대로 사용하며, Recall+Anchor 동시 변경의 자동 적용 순서는 후속 Recall 통합 Issue에서 정의한다.

### 5.4 RawData와 Plot

| 요청 | 현행 | Gap 및 영향 | 근거 |
|---|---|---|---|
| NSA 전용 결과 영역 | NR SA layout을 LB `-37`, 그 외 `-42`행 이동해 사용 | 재사용 | `src/app/report/template_map.py:14`, `src/app/report/template_map.py:165` |
| Anchor 기록 | NR default `B49`, NR LB `B44` 상대 좌표가 NSA offset 후 `B7`로 매핑되고 writer가 최초 Anchor를 기록함 | H2026E014-39 구현 및 실제 template 복사본 단위 테스트 완료 | `src/app/report/template_map.py:44`, `src/app/report/excel_writer.py:220` |
| Plot 유지 | SA/NSA 디렉터리와 filename prefix 구분 구현 | 기존 로직 회귀 확인만 수행 | `src/app/report/screenshot_store.py:50` |

현재 NSA layout에서 NR Band가 A7이므로 요구사항의 “Band 옆 셀”은 B7에 `B1` 형식으로 기록한다. 다른 layout도 같은 상대 위치 규칙을 template map에 적용한다.

Band info와 Anchor는 `ExcelReportWriter` 실행 중 `sheet + layout`당 최초 한 번만 기록한다. 예를 들어 `B1`이 먼저 기록된 뒤 같은 writer에서 `B3` TC를 처리해도 `B7`과 최초 Band info는 바꾸지 않으며, 새 writer 실행에서는 그 실행의 최초 값으로 다시 기록할 수 있다. Anchor별 sheet/row block이나 별도 결과 영역은 추가하지 않는다. 서로 다른 Anchor가 같은 NSA 측정 좌표를 사용하는 상황은 운영자가 Queue를 관리해 방지하고, 코드는 혼합 Anchor Queue를 자동 차단하거나 경고하지 않는다. NR source template은 변경하지 않는다.

## 6. 시험 운영 편의 개선: 현행과 Gap

### 6.1 EUT Name 기반 RawData 자동 관리

H2026E014-41/44/45/43/42 구현 후 파일 흐름은 다음과 같다.

```text
Runner.start(cases, settings, start_index, stop_index)
→ 저비용 검증 후 pending RunPreparationRequest 저장
→ FSM QThread의 PrepareReport
→ Generation별 read-only source 조회·관리 시트 검증
→ EUT/RAT별 result workbook exclusive-create 또는 기존 파일 재사용
→ ExcelReportWriter(result_workbook_path) + live monitoring 준비
→ 성공한 경우에만 측정 FSM 진입
```

| 요청 | 구현 결과 | 근거 |
|---|---|---|
| Excel 선택 제거 | Excel 행·browse handler·저장 경로 설정과 `template_path` 제거 | `test_manager_panel.py`, `test_run_settings.py`, `excel_writer.py` |
| EUT 기반 결과 | `<root>/<EUT>/<EUT>_CE Main_Radiation_<NR\|LTE>.xlsx` 계산 | `rawdata_workbook.py` |
| 미존재 시 양식 복사 | target exclusive-create 후 복사·검증, 실패 시 자신이 만든 부분 파일만 제거 | `rawdata_source.py`, `rawdata_workbook.py` |
| 기존 파일 재사용 | 검증된 파일은 덮어쓰지 않고 재사용, 손상·읽기 실패는 Start 차단 | `rawdata_workbook.py` |
| EUT filename 안전성 | 공백, trailing dot, Windows 금지문자·예약명과 root 이탈 차단 | `rawdata_workbook.py` |

원본 양식과 결과 파일은 다음 lifecycle로 분리됐다.

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

source-to-result mapping은 다음과 같다.

| 결과 RAT | source template | 확인된 sheet |
|---|---|---|
| NR SA/NSA | `resources/templates/NR_Rawdata_.xlsx` | 현재 지원 NR Band 15개의 `Sub6 n*` sheet. SA/NSA가 같은 NR 결과 파일 공유 |
| LTE | `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx` | 현재 지원 LTE Band 11개의 `LTE_BAND *` sheet. WCDMA 등 비관리 sheet 허용 |

두 파일은 Git에 추적되며 `CE_NR_Radiated.spec`의 `resources` datas에 포함된다. 개발 실행은
`<repository>/resources/templates`, frozen 실행은 `<sys._MEIPASS>/resources/templates`만
조회한다. 런타임은 SHA-256을 산출하지만 고정값 비교는 테스트와 PyInstaller 검증에서 수행한다.

결과 경로 규칙은 다음과 같이 확정됐다.

```text
{EUT 결과 기준 root}/
└─ {EUT Name}/
   ├─ screenshots/Traffic/...                       # SA PNG
   ├─ {EUT Name}_CE Main_Radiation_NR.xlsx          # NR SA/NSA
   └─ {EUT Name}_CE Main_Radiation_LTE.xlsx         # LTE
```

개발 실행의 root는 `~/Desktop`, frozen 실행은 EXE 폴더다. 호환 필드명
`screenshot_root_dir`도 이 **EUT 결과 기준 root**를 뜻한다. 기존
`<root>/screenshots/<EUT>` 경로는 조회·이동·재사용하지 않고 `AppConfig.excel_template_path`도
source나 결과 fallback으로 사용하지 않는다.

Prepare 중 Stop은 UI를 막지 않지만 이미 진행 중인 openpyxl/COM 호출을 강제 중단하지 않는다.
호출 반환 직후 Stop을 관찰해 장비 command와 측정 상태에 진입하지 않고 `Idle`로 복귀한다.

### 6.2 MT8000A Parameter Recall 자동 적용

| 요청 | 현행 | Gap 및 영향 | 근거 |
|---|---|---|---|
| Recall ID 파생 | NR은 SA/NSA와 FDD/TDD를 조합한 네 ID, LTE는 `LTE_FDD/LTE_TDD` 사용 | `.PRM` 확장자 없는 모델 값을 TCP/JSON Params에 그대로 전달 | `src/app/models/band_group.py:31`, `src/app/models/lte_band_group.py:23` |
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

NSA에서는 `CALLSO`가 전체 LTE Call 종료가 아니라 SCG Release로 동작한다. Recall과 Anchor가 동시에 바뀌면 목표 Anchor의 `ULCHAN`만 변경하고 고정 profile을 read-back 검증한 뒤 기존 `NR Call`로 SCG를 재연결한다. 정확한 helper 순서는 고수준 `Recall Change` LV 구현 Issue에서 설계한다.

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
| Saturation Time | 자동시험의 실행 설정과 Python 대기값 | Manual Set 적용과 Semi Auto 재사용 필요. 저장·전달 책임은 Interface Contract 대상 |
| Screenshot | `get_screenshot()` 요청 후 LV가 `temp/screenshot.png`를 생성하는 계약 | 재사용 가능하나 저장 workflow 신규 |
| Peak/Next/OFF/ALL OFF | 기존 marker facade | 재사용 가능 |
| Turntable move/stop/angle | 기존 CO3000 facade | 재사용 가능 |
| 1m/3m Horn/Bilog 편파 | `set_antenna_pol()`과 Mast Index mapping | 재사용 가능 |
| FSV40 `*RST` Preset | 없음 | 신규 LV/Python command |
| Single/Continuous Sweep | 없음 | 신규 LV/Python command |
| Clear Write/Max Hold | 없음 | 신규 LV/Python command |
| Detector Mode | 없음 | 신규 모델/command |
| Marker Auto Peak | 없음 | 신규 LV/Python command |
| Mkr→Center | 없음 | 신규 LV/Python command |

관련 command 근거는 `src/app/net/commands.py:494-901`다.

기존 Manual Marker의 `Next Peak Search Level` 입력은 Peak/Next/OFF facade의 `Excursion` payload로 전달된다. Manual Test도 이 입력과 기존 parameter mapping을 재사용한다. Marker Auto Peak와 Marker to Center만 신규 command 계약 대상이다.

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

Manual Test는 FSV40 설정에서 입력해 Set으로 적용한 Saturation Time을 Semi Auto에서 별도 입력 없이 재사용한다.

관련 로직은 `src/app/core/fsm/states/measurement/common.py:289-568`에 있다. 이 state는 SessionContext와 TestCase에 결합되어 있으므로 Manual Test에서 직접 호출하지 않고 알고리즘과 event handling을 Manual service로 재구성한다.

기존 `InitialTurntableZeroState`에는 `현재 각도 <= 180° → 0°`, `현재 각도 > 180° → 360°`, 초기 속도 6 규칙이 구현·검증되어 있다. Manual Test는 이 판정 규칙을 그대로 재사용한다. timeout, 실패 시 안전 상태와 회전 완료 event correlation만 `MAN-09`의 구현·검증 범위로 둔다.

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

현행 `TestRange`는 Range 1~6만 정의하며 limit, sweep point, input path, filter mode까지 필수로 요구한다: `src/app/models/test_range.py:52`. Range 7~9는 4.4의 네 FSV40 값만 확정됐으므로 Manual preset에는 추가하되 정식 TestCase의 Band×TestType Range 매핑과 Test Manager의 TestCase Range 표시에는 추가하지 않는다.

Manual preset 표현을 별도로 둘지 기존 Range 표현을 분리할지는 구현 설계에서 결정한다. 어느 방식을 사용하더라도 Range 7~9의 미확정 속성에 임의 값을 채우지 않는다.

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
| DEC-NSA-04B | 첫 NSA TC는 기존 `NR Call`을 사용한다. 연속 NSA TC의 Anchor가 같으면 기존 `NR Handover`, Anchor가 바뀌면 내부에서 NR Call helper를 재사용하는 신규 `NSA Handover` 단일 composite를 호출한다. | Python은 Anchor 변경 시 한 번의 고수준 workflow만 호출하며 NR Call/primitive sequencing을 추가하지 않는다. |
| DEC-MT-01 | `CALLSTAT?`의 `REM_DEST`별 상태 의미와 terminal polling 기준은 4.2.1을 따른다. | SCG Release=`8000A==6`, NSA 연결=`8000A==8`, Anchor 유지=`8821C==6`; 과도 상태는 필수 관측하지 않는다. |
| DEC-MT-02 | 외부 API는 기존 `NR Call`, 신규 `NSA Handover`, 신규 `Recall Change`, 기존 `Check Call Status`의 의미 기반 workflow로 제공한다. | `CALLSO`/`CALLSTAT?`/Anchor HO/Recall은 명시적 `REM_DEST`를 사용하는 LV 내부 helper다. |
| DEC-MT-03 | `NSA Handover` 응답은 Default Response를 사용한다. | Python은 최종 `status`만 판정하고 `Result`를 무시한다. 실패 시 `Error.message`만 요구한다. |
| DEC-RCL-02 | 첫 실행 TC에는 Recall을 호출하지 않고 `start_index`를 반영한 해당 TC의 ID를 세션 초기값으로 사용한다. | first-TC Recall command를 제거한다. |
| DEC-RCL-03 | 목표 ID 변경 시에만 Recall Change를 실행하고 성공 후에만 applied ID를 갱신한다. Call 단절 시 Recall은 유지되며 현재 Recall 조회는 요구하지 않는다. | session context·복구 Acceptance Criteria에 반영한다. |
| DEC-RCL-04 | Recall Change는 NSA Handover와 분리된 고수준 LV workflow다. NSA의 `CALLSO`는 SCG Release로 처리한다. | Generation별 정리→Recall→기존 Call 재연결→최종 상태 확인을 LV에서 수행한다. |
| DEC-RAW-01 | 결과 경로와 filename은 `POL-RAW-01`을 따른다. | H2026E014-44/43에서 구현 완료. |
| DEC-RAW-02 | NR source는 `resources/templates/NR_Rawdata_.xlsx`, LTE source는 `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx`다. | H2026E014-41/42에서 추적·dev/frozen lookup·패키징 검증 완료. |
| DEC-MAN-01 | Filter Box와 같은 전역 배타 장비 operation 정책을 적용한다. | 경쟁 command 차단과 busy 안내를 고정 입력으로 사용하고 구현 방식은 설계에서 정한다. |
| DEC-MAN-02 | FSV40 preset은 Range 1~9를 사용하고 Detector Mode 9종을 제공하며 기본값은 `RMS`다. `Next Peak Search Level`은 기존 `Excursion` parameter로 사용한다. | 명백한 입력 오류만 UI에서 차단하고 장비별 상세 제한은 LV/FSV40 오류로 처리하며 기존 Marker mapping을 재사용한다. |
| DEC-MAN-03 | Capture는 저장 폴더와 기준 파일명을 입력받고 기존 파일을 덮어쓰지 않는다. Screenshot 목록은 현재 앱 실행 세션의 성공 파일만 표시한다. | Single/N-Capture 충돌 경고, N-Capture 순번, 부분 성공 보존과 최신순 목록을 적용한다. |
| DEC-MAN-04 | Range 7~9는 확정된 Start/Stop Frequency와 RBW/VBW로 Manual preset에 포함하되 정식 TestCase Range에는 매핑하지 않는다. | 미확정 Range 속성은 추가하지 않고 기존 Manual 설정 Story에서 처리한다. |
| DEC-MAN-05 | Saturation Time은 FSV40 설정의 Set으로 적용한다. Semi Auto는 별도 입력 없이 적용된 값을 사용하고 `현재 각도 <= 180° → 0°`, `> 180° → 360°`, 속도 6으로 초기 정렬하며 전 과정에서 Stop할 수 있다. | Continuous Sweep 후 적용값만큼 대기한다. Stop 후 남은 단계는 실행하지 않고 회전 중이면 Turntable을 정지한다. |
| DEC-PLAN-01 | Manual Test의 제품 요구사항은 4.4로 확정하고 기술 인터페이스만 후속 계약으로 남긴다. | command명·payload·Python/LV 책임 경계를 Interface Contract에서 확정한다. |

### 8.2 추가 제품 결정 상태

현재 NSA/Recall SRS 및 Jira Issue 작성을 막는 추가 제품 결정은 없다. RawData 관련 결정은
H2026E014-41/44/45/43/42 구현과 검증으로 닫혔다. 다음 사항은 결정 Register에 올리지 않고
해당 구현 Issue에서 구체화한다.

| 기술사항 | 관리 위치 | 요구되는 결과 |
|---|---|---|
| 첫 NSA TC 연결 순서 | `NSA-05` | 목표 Anchor가 사전 준비됐다고 간주하고 기존 `NR Call` 사용 |
| Recall+Anchor 동시 변경 내부 순서 | `RCL-02-LV` | 목표 Recall·Anchor 적용 후 NSA 최종 연결 상태 복구 |
| Anchor CSV 필드와 결과 cell mapping | `NSA-01`, `NSA-06` | NSA TC에 Anchor 필수, 결과는 NR Band 옆 셀에 `B*` 형식으로 기록 |
| Manual command·payload·Python/LV 책임 경계 | Manual Test Interface Contract | 4.4의 확정 요구사항을 바꾸지 않는 기술 계약으로 작성 |

### 8.3 구현 Issue의 기술 설계·검증 산출물

| 산출물 | 포함할 Issue | 관리 원칙 |
|---|---|---|
| MT8000A TCP/JSON command·Params·응답 계약 | `NSA-04-PY/LV`, `RCL-02-PY/LV` | 고수준 workflow 경계와 command별 Default Response/오류 계약을 정의 |
| timeout·polling·retry 값과 벤치 결과 | `NSA-04-LV`, `RCL-02-LV`, 통합 인수 | 무한 대기 없이 terminal 상태 또는 명시적 실패로 종료되도록 구현·검증 |
| RawData resolver와 배포 resource 검증(완료) | `H2026E014-41/44/45/43/42` | dev/frozen source, copy/reuse 실패, FSM/UI와 패키징 결과 검증 완료 |
| Manual Test Interface Contract | 관련 `MAN-*` Python/LV Issue | command명·payload·Result/Error와 Python/LV workflow 책임을 구현 전에 합의 |

위 항목은 독립적인 ‘결정용 Issue’가 아니다. 구현에 별도 실장비 검증이 필요하면 해당 Story의 subtask 또는 DoD로 관리한다. terminal 성공은 4.2의 최종 상태 polling으로 판정하며, 근거 없는 추가 유지 시간 기준은 요구하지 않는다.

### 8.4 PM 계획 원칙

- MT8000A 외부 경계는 의미 기반 고수준 LV workflow로 확정됐다. Python FSM은 LV helper primitive의 순서를 직접 제어하지 않는다.
- 각 LV workflow는 단계마다 `REM_DEST`를 명시하고 terminal 상태를 polling한다. `NSA Handover`의 외부 응답 판정은 `DEC-MT-03`을 따른다.
- Manual의 N-Capture/Semi Auto Python workflow와 LV 복합 명령 경계는 Manual Test Interface Contract에서 결정한다.
- v3.0 장비 동시성 정책은 전역 배타 동작으로 확정하되 기존 guard 확장과 신규 coordinator 중 구현 방식은 설계에서 정한다.
- Range 7~9는 Manual preset에 포함하고 정식 TestCase Range 매핑에서는 제외한다.
- Manual Capture의 저장 폴더·기준 파일명·순번·덮어쓰기 금지는 확정값으로 사용하고 Screenshot 전달과 오류 응답만 Interface Contract에서 정한다.

## 9. 권장 개발 순서와 의존성

### 9.1 전체 흐름

```text
1차: NSA 정식 지원
  확정 정책 적용
    ├─ 모든 NR–Anchor 조합 허용
    ├─ Anchor Band 선택 열 추가, 별도 설정 입력 없음
    ├─ SA/NSA/LTE 혼합 Queue 시작 차단
    ├─ Anchor 동일 → 기존 NR Handover
    ├─ 첫 NSA TC → 기존 NR Call
    └─ Anchor 변경 → NR Call helper를 내부 재사용하는 신규 고수준 NSA Handover 단일 composite
  구현 Issue 내부 설계·검증
    ├─ Anchor CSV field / 결과 cell mapping
    ├─ 첫 NSA TC의 기존 NR Call routing과 Recall+Anchor 동시 변경
    └─ Python/LV wire contract / timeout·poll·retry / terminal polling 벤치 검증
  구현 흐름
    └─ Anchor domain/CSV → SA·NSA UI → 고수준 Python/LV workflow → FSM/결과 → 통합 인수

2차 또는 비충돌 병렬 Track: 운영 편의
  ├─ RawData asset/resolver/lifecycle/FSM/UI 통합 완료 (H2026E014-41/44/45/43/42)
  └─ 확정된 고수준 Recall Change 기반 Recall FSM

현재 계획 Track: Manual Test
  구현 전 Interface Contract
    └─ command/payload/Python-LV workflow 경계
  구현
    ├─ 확정된 전역 배타 operation 정책 적용
    ├─ 현재 세션 Screenshot 목록 적용
    └─ Range 7~9 Manual preset 적용, TestCase 매핑 제외

각 Track: Mock/정적 계약 검증 → 승인된 LV/실장비 인수 → 문서/배포 동기화
```

### 9.2 병렬화 가능한 Track

| Track | 착수·조정 기준 | 주요 충돌 파일 |
|---|---|---|
| NSA Domain/UI/Report | 확정된 Anchor property·allowlist·결과 위치를 사용해 바로 착수하고 CSV/writer 세부 mapping은 Issue 안에서 완성 | `test_case.py`, `test_manager_panel.py`, `excel_writer.py` |
| NSA/Recall FSM | 확정된 고수준 workflow와 terminal 상태를 기준으로 착수하고 Python/LV wire contract는 양쪽 Issue가 함께 작성 | `session.py`, `transition.py`, `commands.py` |
| RawData(완료) | H2026E014-41/44/45/43/42에서 source/path/lifecycle/FSM/UI/회귀·패키징 검증 완료 | `run_preparer.py`, `runner.py`, `test_run_settings.py`, report 계층 |
| Manual Test | 4.4를 요구사항 기준으로 사용하고 구현 전 Python/LV Interface Contract를 합의 | `main_window.py`, `commands.py`, mock |
| LabVIEW | Python counterpart와 같은 interface contract를 사용하고 벤치 결과를 해당 Issue에 첨부 | 외부 LV source/release |

NSA와 Recall은 `session.py`, `transition.py`, `commands.py`, Mock LV를 공유하므로 서로 다른 브랜치에서 독립 구현하지 않는 편이 안전하다. RawData 자동화는 H2026E014-41/44/45/43/42에서 `run_preparer.py`, `runner.py`, `excel_writer.py`와 report lifecycle 조정을 완료했다. Manual Test 역시 command catalog와 Mock LV를 확장하므로 공통 파일 담당자 또는 순차 merge 계획이 필요하다.

## 10. Jira Agent용 후보 작업 패키지

아래는 Jira Issue가 아니라 backlog 변환 입력이다. Priority, 담당자, Story Point, Sprint는 Refinement 전 임의로 정하지 않는다.

### 10.1 별도 결정용 Issue를 만들지 않는 범위

NSA/Recall은 현재 확정사항으로 구현 Story를 작성한다. RawData Story는
H2026E014-41/44/45/43/42로 구현·검증 완료됐으며 별도 Discovery/Spike를 추가하지 않는다.

Manual Test의 확정 UX를 별도의 미결정 Issue로 만들지 않는다. command명·payload·Python/LV 책임 경계는 구현 전 Interface Contract 작업으로 등록한다.

### 10.2 NSA 정식 지원 후보 패키지

| 후보 ID | Outcome | 의존성 | 예상 주 영향 |
|---|---|---|---|
| NSA-01 | Anchor-aware TestCase/CSV와 Generation 혼합 시작 차단 validation | POL-NSA-01/02/03 | models, loader, validator |
| NSA-02 | NR SA·NR NSA 각각의 LTE형 통합 생성 화면과 별도 진입 버튼 | NSA-01 | UI |
| NSA-03 | Manager `n5-B1` 표시와 generation별 UI state | NSA-01 | UI |
| NSA-04-PY | 기존 `NR Call` request Params 호환 유지, Anchor Band→MID 5 MHz UL/DL Channel lookup, 목표 NR 설정과 `Anchor UL Channel`을 전송하는 신규 단일 `NSA Handover` facade, Default Response의 status-only 판정, stateful Mock와 Default Error 처리 | NSA-01 | models, net, mock, protocol docs |
| NSA-04-LV | `ULCHAN`만 변경하고 MID/5 MHz/RB Size 1/RB Offset 0/QPSK를 read-back 검증한 뒤 기존 NR Call helper로 SCG Addition까지 완료하는 신규 `NSA Handover` 단일 composite, timeout·polling·retry 벤치 검증 | 4.2 확정 workflow | 외부 LV. `CHBWDLCHAN` 사용 금지, 단계별 REM_DEST, terminal polling과 최소 failure 정보 포함 |
| NSA-05 | 첫 NSA TC는 기존 `NR Call`, Anchor 변경 시 단일 `NSA Handover`, Anchor 동일 시 기존 `NR Handover`를 호출하는 FSM routing | NSA-01, NSA-04-PY | core/fsm |
| NSA-06 | NR Band 옆 cell에 `B*` 형식으로 Anchor Band 기록 | NSA-01 | report/template map |
| NSA-07 | 실제 LV를 포함한 NSA 통합 인수와 임시 문서 정식화 | NSA-02~06, NSA-04-LV | tests/docs/release |

### 10.3 시험 운영 편의 개선 구현 결과와 Recall 후보 패키지

| 후보 ID | Outcome | 의존성 | 예상 주 영향 |
|---|---|---|---|
| RAW-01 (완료) | 확정 경로·filename을 사용하는 EUT/RAT RawData resolver와 safe copy/reuse | H2026E014-44 | report/assets |
| RAW-02 (완료) | FSM worker에서 결과 workbook을 확보한 뒤 writer 생성 | H2026E014-45 | Runner/context/report |
| RAW-03 (완료) | Excel 선택 UI와 사용자 path validation 제거 | H2026E014-43 | Test Manager/config |
| RAW-04 (완료) | 두 `resources/templates` asset의 tracking/검증과 dev/frozen runtime lookup | H2026E014-41 | resources/spec |
| RAW-05 (완료) | 신규/기존/손상/열림/복사 실패와 cross-layer·패키징 검증 | H2026E014-42 | tests/docs |
| RCL-02-PY | 현재 모델의 Recall 식별자를 wire Params에 매핑하는 신규 고수준 `Recall Change` facade, wire contract, failure parsing과 REM_DEST별 Mock 확장 | 4.2 확정 workflow | models/net/mock |
| RCL-02-LV | Generation별 정리→Recall→기존 Call 재연결과 Recall+Anchor 동시 변경을 수행하는 고수준 `Recall Change` LV workflow 및 벤치 검증 | 4.2 확정 workflow | 외부 LV |
| RCL-03 | 첫 TC 미호출, `start_index` 초기화, ID 변경 시만 호출, 성공 후만 갱신, Call 단절 시 Call만 복구하는 FSM | RCL-02-PY | core/fsm |
| RCL-04 | 실제 LV를 포함한 SA/NSA/LTE/Recall/TDF 통합 인수와 문서화 | RCL-02-LV, RCL-03, NSA-05 | tests/docs |

`RCL-03`은 Recall 변경용 수동 확인만 대체한다. DUT Axis 변경, Call 복구 등에서 사용하는 공용 `user_action_required`와 `_UserActionDialog`까지 제거하는 작업이 아니다.

### 10.4 Manual Test 후보 패키지

| 후보 ID | Outcome | 의존성 | 예상 주 영향 |
|---|---|---|---|
| MAN-01 | 확정된 Manual 설정/Capture 입력과 Range 1~9 preset 모델, 명백한 입력 오류 validation | 4.4 | models/core |
| MAN-02-PY | FSV40/Marker 신규 Python facade, Interface Contract와 Mock | MAN-01 | net/mock |
| MAN-02-LV | Python counterpart와 합의한 실제 LV command/API 구현 | MAN-02-PY와 공동 Refinement | 외부 LV |
| MAN-03 | ManualTestService worker lifecycle과 cancel/error/progress | MAN-01, MAN-02-PY | core |
| MAN-04 | Filter Box와 같은 전역 배타 operation 적용과 busy 처리 | POL-MAN-01 | MainWindow/services. 기존 guard 확장/신규 coordinator는 설계 선택 |
| MAN-05 | 장비 capability별 Manual Panel 활성화 | MAN-03/04 | UI |
| MAN-06 | Range 1~9를 포함한 FSV40 Set/Preset/Single/Continuous Sweep UI+service | MAN-02-PY, MAN-03, MAN-05 | UI/core |
| MAN-07 | Next Peak Search Level→`Excursion` mapping을 포함한 Marker UI+service | MAN-02-PY, MAN-03, MAN-05 | UI/core |
| MAN-08 | Turntable/1m/3m Horn/Bilog UI+service | MAN-03/05 | UI/core |
| MAN-09 | Set으로 적용된 Saturation Time과 기존 `<= 180° → 0°`, `> 180° → 360°`, 속도 6 기준점 판정을 사용하는 Semi Auto 및 Stop/timeout/failure 처리 | MAN-02-PY/LV, MAN-03, MAN-04, MAN-08 | Python/LV 공동. sequence 소유권은 Interface Contract에서 확정 |
| MAN-10 | strict no-overwrite Single Capture store/workflow | MAN-03 | report/core/UI |
| MAN-11 | N-Capture 반복 수행, preflight와 부분 성공 보존 통합 | MAN-02-PY/LV, MAN-03, MAN-10 | Python/LV/report/UI. 반복 sequence 소유권은 Interface Contract에서 확정 |
| MAN-12 | 현재 세션 최신순 Screenshot 목록과 viewer | POL-MAN-03, MAN-10/11 | UI |
| MAN-14 | 실제 LV를 포함한 Mock/실장비 통합 인수와 운영 문서 | MAN-02-LV, MAN-05~12 | tests/docs/release |

Range 7~9는 별도 결정 Issue를 만들지 않고 `MAN-01`의 preset 모델과 `MAN-06`의 FSV40 preset UI에 포함한다. 정식 TestCase Range 매핑은 변경하지 않는다.

### 10.5 Jira 구성 권고

- 사용자의 세 분류를 상위 Epic으로 유지한다.
- NSA/운영 편의의 남은 검증과 Manual Test 계획·개발을 각각의 Track으로 관리한다.
- 기술 설계·벤치 검증은 별도 결정용 Spike로 분리하기보다 관련 구현 Story의 subtask/DoD로 연결한다. 실장비 접근 자체가 독립 일정이면 검증 subtask만 분리한다.
- 실제 LabVIEW 작업은 Python facade 작업과 별도 Issue로 만들고 같은 protocol ADR을 첨부한다.
- command Issue는 이름만 적지 말고 target, Params, Result, unit, timeout, failure와 Mock까지 범위에 포함한다.
- `CALLSO`/`CALLSTAT?`/Anchor HO/Recall primitive를 별도 외부 API Story로 만들지 않고 고수준 `NSA Handover`·`Recall Change` LV Issue의 helper/subtask로 관리한다.
- 과도 상태 `8000A 7/9`, `8821C 13` 관측을 Acceptance Criteria로 요구하지 않는다. 명시적 `REM_DEST`와 terminal 상태 polling을 검증한다.
- UI Story는 연결 상태만이 아니라 worker 진행/중단/오류/lock 상태를 Acceptance Criteria에 포함한다.
- 외부에서 확인 가능한 Outcome과 Acceptance Criteria가 있으면 구현 Issue를 Ready로 만들 수 있다. 내부 command 이름·순서·timeout 값은 Ready 선행 제품 결정으로 취급하지 않는다.
- Manual command명·payload·Python/LV 책임 경계는 구현 전 Interface Contract에서 확정하고, 4.4의 UX를 다시 미결정으로 올리지 않는다.
- Range 7~9는 기존 Manual 설정 Story에 포함하고 TestCase Range 매핑에는 추가하지 않는다. Screenshot 목록 source와 전역 배타 동작도 미결정 질문으로 되돌리지 않는다.
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
9. 첫 NSA TC의 기존 `NR Call`, Anchor 변경 전용 `NSA Handover`, Recall+Anchor 동시 변경, terminal 상태와 Default Response 실패 처리의 관찰 가능한 인수 기준
10. Manual 기능별 enablement, 확정된 전역 배타 정책, validation, busy/cancel/error 상태
11. 요구사항→Jira→검증 시나리오 traceability

### 11.1 용어 정규화 권고

| 입력 표현 | 문서 canonical 표현 | 비고 |
|---|---|---|
| `MT8800a`, `MT8000a` | `MT8000A` | 이번 확정 입력에 따라 오탈자로 정규화 |
| NSA Anchor | `LTE Anchor Band` | 값은 `B1` 형식 |
| SCG Addiation | `NR SCG Addition` | 오탈자 정정 |
| Rawdata/RawData | `RawData workbook` | source template과 result workbook 구분 |
| Spectrum Analyzer 관련 Manual 기능 | `FSV40 설정`, `FSV40 Sweep` | `NR SA`와 구분 |
| Cont Sweep | `Continuous Sweep` | UI label은 별도 가능 |
| Mkr→Center | `Marker to Center` | protocol command 이름은 계약에서 확정 |

### 11.2 요구사항 Agent 작성 원칙

- SRS에는 자동 수행 여부, 입력 제약, 최종 상태, 결과 기록, 실패 응답처럼 사용자와 시스템 경계에서 관찰 가능한 동작을 작성한다.
- LV helper 순서, 실제 wire field 이름, timeout·retry 수치와 path 정규화 알고리즘은 제품 미결정으로 만들지 않는다. 관련 구현 Issue의 설계·검증 산출물로 연결한다.
- terminal 상태 polling 외의 추가 stable-state 유지 시간은 요구하지 않는다. 실장비에서 필요성이 확인될 때만 결함 보강 또는 기술 subtask로 추가한다.
- RawData 기존 파일 재사용과 미존재 시 source 복사는 구현 완료된 동작이다. 열림·손상·권한·경로 오류의 safe-failure 회귀는 H2026E014-42가 보유한다.
- Manual Test의 제품 동작은 4.4를 사용하며 command명·payload·Python/LV 책임 경계만 후속 Interface Contract에서 정한다.
- 모든 NR–Anchor 조합 허용, SA/NSA/LTE 혼합 시작 차단, `REM_DEST`별 상태 의미, 고수준 NSA Handover/Recall Change API 경계, 첫 TC Recall lifecycle, RawData 논리 경로·filename과 두 source template mapping, 전역 배타 operation 동작, 현재 세션 Screenshot 목록, Range 7~9의 Manual preset 전용 정책은 다시 미결정 항목으로 올리지 않는다.

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
- 첫 NSA TC에서 목표 Anchor가 사전 준비됐다고 간주하고 기존 `NR Call`로 NR SCG를 연결함
- Anchor 동일 변경은 기존 `NR Handover`, Anchor 변경은 단일 `NSA Handover`를 호출함
- SCG Release 완료는 `REM_DEST 8000A`의 최종 `6`으로 판정하고 `8821C == 6`만으로 완료 처리하지 않음
- Anchor HO는 `ULCHAN`만 변경하고 `REM_DEST 8821C` 최종 `6` 및 고정 profile read-back으로 판정하며 `CHBWDLCHAN`을 사용하지 않음
- `NSA Handover` 내부 NR Call helper는 `REM_DEST 8000A` 최종 `8`과 Anchor `8821C == 6` 유지로 판정함
- 과도 상태 `8000A 7/9`, `8821C 13`을 관측하지 못해도 terminal 상태가 충족되면 성공함
- 모든 단계가 이전 destination에 의존하지 않고 `REM_DEST`를 명시적으로 재설정함
- `NSA Handover` 성공은 Default OK의 `status`만으로 판정하고 Result 유무·형식을 무시함
- `NSA Handover` 실패는 Default Error의 `status`와 `Error.message`로 처리하며 별도 failure envelope를 요구하지 않음
- NSA 최초 Band 정보 기록 시 `A7=NR Band`, `B7=Anchor Band`가 기록되고, 같은 writer에서 Anchor가 바뀌어도 최초 Anchor와 Band info가 유지됨
- 새 writer 실행에서는 다른 Band info와 동일하게 그 실행의 최초 Anchor를 다시 기록할 수 있음
- Anchor별 별도 결과 영역 없이 동일 측정 좌표를 사용하며 운영자가 Queue를 관리하고, 코드가 혼합 Anchor를 자동 차단·경고하지 않음
- SA/LTE 셀 계약과 기존 Plot naming 불변

### RawData와 Recall

- 개발은 `~/Desktop`, frozen은 EXE 폴더를 기준으로 `<root>/<EUT>/` 결과 구조를 계산함
- Excel 결과는 `<EUT>_CE Main_Radiation_{NR|LTE}.xlsx`, Screenshot은 같은 EUT 폴더의 `screenshots/Traffic/...`에 배치함
- 기존 `<root>/screenshots/<EUT>` 파일은 fallback 없이 무시함
- 개발 source는 저장소 `resources/templates`, frozen source는 `sys._MEIPASS/resources/templates`만 사용함
- NR 15개 `Sub6 n*`, LTE 11개 `LTE_BAND *` 관리 시트와 LTE 비관리 WCDMA 시트 허용을 검증함
- 런타임 SHA-256 산출과 테스트/PyInstaller 고정 checksum 비교의 책임을 구분함
- 신규 EUT 파일 생성, 열린 정상 파일을 포함한 기존 EUT 재사용, 잘못된/손상 파일의 명확한 실패
- source template 누락과 result directory 권한 오류 시 FSM 미시작
- Prepare 중 Stop은 openpyxl/COM 반환 직후 관찰하고 장비 command 없이 Idle 복귀
- 첫 실행 TC와 `start_index > 0`의 첫 TC에서 Recall command를 보내지 않고 해당 ID를 세션 초기값으로 기록함
- 같은 Recall에는 command를 보내지 않고 변경된 Recall에만 고수준 `Recall Change`를 호출함
- Recall Change 성공 후에만 적용 ID를 갱신하고 실패 시 Factor/측정으로 진입하지 않음
- Call 단절 시 Recall을 다시 적용하거나 조회하지 않고 기존 Call만 재실행함
- Recall ID와 Anchor Band가 함께 바뀌면 둘 다 적용한 뒤 NSA 최종 연결 상태를 확인하고 성공 후에만 적용 Recall ID를 갱신함
- TC/model이 제공하는 Recall ID를 불투명 식별자로 사용하고 Generation 혼합 Queue의 시작을 차단함

### Manual Test

- 장비별 연결 조합의 capability 활성화와 TestCase·Call·Filter 비종속
- 연결 해제/실패 중 진행 operation 정리
- Manual preset Range 1~9, Custom 입력, Detector Mode 9종과 기본 `RMS`
- 명백한 입력 오류 차단과 LV/FSV40 상세 오류 표시
- Next Peak Search Level→`Excursion` mapping을 포함한 Marker 전체 기능
- Turntable 기준점 `현재 각도 <= 180° → 0°`, `> 180° → 360°`와 Stop
- 1m/3m Horn/Bilog target mapping과 높이 제어 부재
- Semi Auto에서 별도 입력 없이 Set으로 적용된 Saturation Time 대기, 전 과정 Stop, Single Sweep/Capture 미실행과 Max Hold 유지
- 저장 폴더·기준 파일명·순번 적용과 Single/N-Capture 충돌 시 장비 command 미호출·경고
- N-Capture 중간 실패 시 성공 파일 보존과 이후 중단
- 현재 실행 세션의 성공 파일만 최신순 목록에 표시하고 선택 이미지 표시
- 자동시험/Manual/Connect/Set/TDF/RF 장비 operation 배타 동작과 busy 안내
- Range 7~9의 네 확정값 반영과 정식 TestCase Range 미매핑

## 13. 근거 파일 지도

| 관심 영역 | 우선 확인 파일 |
|---|---|
| TestCase/CSV/Anchor | `src/app/models/test_case.py`, `src/app/models/enums.py`, `src/app/core/tc_loader.py`, `src/app/core/tc_validator.py` |
| NR/NSA/LTE 생성 UI | `src/app/ui/test_manager_panel.py`, `src/app/ui/nr_select.py`, `src/app/ui/lte_select.py` |
| NSA/Recall FSM | `src/app/core/fsm/call_routing.py`, `src/app/core/fsm/states/nr_setup.py`, `src/app/core/fsm/states/session.py`, `src/app/core/fsm/states/transition.py`, `src/app/core/fsm/engine.py` |
| Command/Mock | `src/app/net/commands.py`, `src/app/net/protocol.py`, `src/app/net/tcp_client.py`, `src/app/net/mock_lv_server.py` |
| RawData/Excel | `src/app/models/test_run_settings.py`, `src/app/core/runner.py`, `src/app/core/run_preparer.py`, `src/app/report/rawdata_source.py`, `src/app/report/rawdata_workbook.py`, `src/app/report/excel_writer.py`, `resources/templates/NR_Rawdata_.xlsx`, `resources/templates/_CE MAIN Radiation Auto Test Rawdata(3G,4G).xlsx` |
| NSA result/Plot | `src/app/report/template_map.py`, `src/app/report/screenshot_store.py` |
| Manual Test | `src/app/ui/manual_test_panel.py`, `src/app/ui/main_window.py`, `src/app/ui/manual_marker_dialog.py`, `src/app/models/test_range.py`, `src/app/net/commands.py`, `src/app/net/mock_lv_server.py`, `src/app/net/tcp_client.py`, `src/app/report/screenshot_store.py`, 신규 core service 후보 |
| Turntable/Event 참고 | `src/app/core/fsm/states/measurement/common.py` |
| 설정/패키징 | `src/app/config/file_dialog_directory_settings.py`, `app_config.py`, `CE_NR_Radiated.spec` |
| 과거 Recall 요구 | `docs/NEXT_VERSION_SRS_AND_JIRA_BACKLOG.md:63-84`, `340-430` |

## 14. PM 결론

v3.0은 세 Epic으로 관리한다. 사용자 일정 기준으로 NSA 정식 지원과 시험 운영 편의 개선은 테스트 대기 중이며, 현재 계획 대상은 Manual Test다. 이번 검토로 Manual Test의 장비별 활성화와 배타 정책, FSV40 입력·Detector Mode, `Next Peak Search Level`→`Excursion`, Turntable/Mast, Semi Auto의 기존 기준점 판정, Capture와 현재 세션 목록, Range 7~9의 Manual preset 전용 적용이 확정됐다. 후속 Agent는 이를 다시 Discovery 질문으로 되돌리지 않는다.

현재 확정사항으로 NSA/Recall SRS 및 Jira Issue를 작성할 수 있으며, 추가 제품 결정 blocker는 없다. RawData는 H2026E014-41/44/45/43/42에서 구현·검증 완료됐다. 첫 NSA TC에는 별도 NSA 순서가 없고 기존 `NR Call`을 사용한다. Recall+Anchor 동시 변경의 자동 적용 순서와 실제 TCP/JSON 표현, timeout·retry 값은 각각의 Python/LV 구현 Issue에서 설계하고 벤치 검증한다. 이를 별도 ‘결정을 위한 Issue’로 만들지 않는다.

`anchor_band` CSV field와 Generation별 검증은 H2026E014-33에서, NR Band 옆 `B*` 형식의 최초 Anchor 결과 mapping은 H2026E014-39에서 구현·검증됐다. 남은 NSA report 작업은 H2026E014-40의 실제 LV·승인 장비 통합 인수와 기존 SA/LTE/Plot 회귀 증빙이다.

RawData source는 Git에 추적된 `resources/templates`의 NR/LTE workbook을 사용한다. dev/frozen 전용 lookup, EUT별 결과 생성·재사용, 오류 rollback, `PrepareReport` FSM 통합, Excel 선택 제거, 결과·Screenshot의 EUT 중심 배치와 패키징 검증까지 완료됐다.

NSA FSM과 Recall FSM은 확정된 고수준 MT8000A workflow와 하나의 승인된 TCP/JSON 계약 아래에서 통합한다. Python과 실제 LabVIEW Issue는 분리하되, Python이 LV 내부 primitive sequencing을 다시 구현하지 않는다. Manual Test는 4.4를 제품 요구사항 기준으로 사용하고 command명·payload·Python/LV 책임 경계만 후속 Interface Contract에서 확정한다.
