# 차기 버전 SRS 및 Jira 백로그

## 1. 문서 개요

| 항목 | 내용 |
|---|---|
| 문서 버전 | 1.0 |
| 작성일 | 2026-07-22 |
| 개발 목표 | FSV Factor(TDF)·MT8000A Parameter Recall 자동화 및 LTE Band 시험 지원 |
| 대상 | 개발 요구사항 관리, Jira 백로그 생성, Python/LabVIEW 개발, QA |
| Jira 상태 | 미생성 |

이 문서는 차기 버전 개발에 필요한 시스템 요구사항, LTE 기준 데이터, 시험 흐름, Epic과 Issue를 모두 포함한다. 별도 참고자료 없이 이 문서만으로 요구사항 관리와 Jira 백로그 생성을 진행할 수 있다.

## 2. 프로젝트 현황

| 영역 | 현재 상태 | 차기 버전 목표 |
|---|---|---|
| NR 시험 | NR SA/NSA의 Harmonic, In-band, Bilog 구현 완료 | 기존 동작 유지 |
| FSV Factor | TDF List 조회와 Set TDF 기능은 있으나 시험 전 사용자가 수동 적용 | Band Group에 따라 시험 중 자동 적용 |
| MT8000A Recall | 시험 전 장비 수동 조작 및 시험 중 수동 확인 필요 | Call Stop/Recall/Call Start 자동화 |
| MT8000A Call | NR Call/Handover/상태 확인 중심 | LTE FDD/TDD Call과 Handover 추가 |
| LTE 모델 | 미지원 | LTE Generation, Band, Channel, BW, RB 모델 추가 |
| LTE FSM | 미지원 | 기존 공통 측정 FSM에 LTE Call 경로 연결 |
| LTE UI | LTE 진입 기능 미완성 | LTE 전용 Select+Table 통합 화면 제공 |
| LTE 결과 | LTE RawData 및 SA PNG 저장 미지원 | LTE 양식 검증, 결과 기록, SA PNG 저장 지원 |

## 3. 시스템 요구사항 명세

### 3.1 용어

| 용어 | 정의 |
|---|---|
| Generation | `NR_SA`, `NR_NSA`, `LTE` Test Case 구분값 |
| Factor | FSV40에 적용하는 TDF 파일. Band Group의 `1G HPF`, `3G HPF` 등이 검색 키워드가 됨 |
| Parameter Recall | Band Group이 제공하며 MT8000A 명령에 확장자 없이 전달하는 Recall 식별자 |
| Test Range | 기존 NR에서 사용하는 Spectrum Analyzer 및 Switch Box Range 설정 |
| ARFCN | LTE 전용 Table과 NR/LTE 공용 UI에서 공통으로 사용하는 채널 필드명 |
| SA PNG | Spectrum Analyzer 측정 화면 이미지 |

CSV에는 ARFCN 채널 번호 열을 추가하지 않는다. 채널 번호와 Frequency는 Band, Bandwidth, Test Channel로부터 파생한다.

### 3.2 Generation과 Queue

| ID | 요구사항 | 인수 기준 |
|---|---|---|
| SRS-GEN-001 | Test Case Generation에 `LTE`를 추가한다. | UI와 CSV에서 LTE Test Case를 생성, 저장, 로드할 수 있다. |
| SRS-GEN-002 | 하나의 실행 Queue에 NR 계열과 LTE를 함께 구성할 수 없다. | NR/LTE 혼합 Queue로 시험을 실행할 수 없다. |
| SRS-GEN-003 | LTE canonical 값은 Generation `LTE`, Band `B1` 형식, RB Allocation `low`/`mid`/`high`를 사용한다. | CSV 저장·로드 후 같은 값으로 복원된다. |
| SRS-GEN-004 | LTE 추가로 기존 NR SA/NSA 의미와 실행 동작을 변경하지 않는다. | 기존 NR 대표 Test Case가 종전과 동일하게 실행된다. |

### 3.3 FSV Factor(TDF) 자동 적용

| ID | 요구사항 | 인수 기준 |
|---|---|---|
| SRS-TDF-001 | 현재 Test Case의 Band Group에서 Factor 키워드를 결정한다. | Band Group의 Factor 값이 TDF 검색 키워드가 된다. |
| SRS-TDF-002 | TDF List에서 Factor 키워드를 포함하는 파일을 선택한다. | `3G HPF`가 `2025_MAIN_Bilog Filter+3G HPF(30M-13G)`와 매칭된다. |
| SRS-TDF-003 | 정상 조건에서는 매칭 파일이 한 개이며, 두 개 이상이면 Error로 처리한다. | 복수 파일 중 하나를 임의 선택하지 않는다. |
| SRS-TDF-004 | 첫 Test Case에서 목표 Factor를 적용한다. | 시험 전 사용자의 수동 TDF 적용 없이 시험을 진행할 수 있다. |
| SRS-TDF-005 | 다음 Test Case에서 Factor가 바뀔 때만 새 Factor를 적용한다. | 같은 Factor가 이어지면 Set TDF를 다시 호출하지 않는다. |
| SRS-TDF-006 | Call Start를 수행하는 흐름에서는 Call 연결 확인 후 Factor를 적용한다. | Call 연결 확인보다 Factor 적용이 먼저 실행되지 않는다. |

### 3.4 MT8000A Parameter Recall 자동 적용

#### Recall 식별자 매핑

| Generation | Band Group | Recall 식별자 |
|---|---|---|
| LTE | `lb`, `mhb_fdd` | `LTE_FDD` |
| LTE | `mhb_tdd` | `LTE_TDD` |
| NR_SA | 각 NR Band Group | 해당 Group의 `mt8000_recall` |
| NR_NSA | 각 NR Band Group | 해당 Group의 `mt8000_recall` |

#### 기능 요구사항

| ID | 요구사항 | 인수 기준 |
|---|---|---|
| SRS-RCL-001 | 현재 Test Case의 Band Group에서 Recall 식별자를 조회한다. Group key와 식별자 문자열은 해석하지 않는다. | Band Group profile의 `mt8000_recall` 값을 그대로 사용한다. |
| SRS-RCL-002 | 첫 Test Case에서 목표 Recall을 자동 적용한다. | 시험 시작 전 사용자의 MT8000A 수동 Recall 조작이 필요하지 않다. |
| SRS-RCL-003 | 다음 Test Case의 Recall 식별자가 달라질 때만 Recall을 변경한다. | 같은 Recall 식별자가 이어지면 Recall을 다시 수행하지 않는다. |
| SRS-RCL-004 | 활성 Call 상태에서 Recall이 변경되면 Call Stop → Parameter Recall → Call Start 순서로 제어한다. | 진행 중 Recall 변경에서 Call Stop 후 Recall하고 Call을 다시 시작한다. |
| SRS-RCL-005 | Call Start 후 연결을 확인한 다음 Factor 적용과 측정으로 진행한다. | Call 연결 확인 전 Factor 또는 측정 단계로 넘어가지 않는다. |
| SRS-RCL-006 | MT8000A 제어는 LabVIEW TCP/JSON API를 통해 수행한다. | Python에서 MT8000A VISA/SCPI 제어를 추가하지 않는다. |
| SRS-RCL-007 | Call Stop, Recall, Call Start, 연결 확인의 명령과 요청/응답 규격은 장비 명령 시험 결과로 확정한다. | LabVIEW와 Python이 동일한 검증 결과를 API 계약으로 사용한다. |

### 3.5 LTE 데이터와 장비 설정

| ID | 요구사항 | 인수 기준 |
|---|---|---|
| SRS-LTE-DAT-001 | 지원 LTE Band는 1, 3, 5, 7, 8, 20, 28, 34, 38, 40, 41이다. | 지정된 11개 Band만 LTE Test Case로 생성된다. |
| SRS-LTE-DAT-002 | LTE SCS는 15 kHz로 고정한다. | LTE Test Case에 다른 SCS를 사용하지 않는다. |
| SRS-LTE-DAT-003 | LTE Modulation은 QPSK로 고정한다. | LTE Test Case에 다른 Modulation을 사용하지 않는다. |
| SRS-LTE-DAT-004 | Band별 TestType/Range, Factor, Recall, Turntable speed는 4.1을 따른다. LB Group(Band 5, 8, 20, 28)은 In-band=Range 1, Harmonic=Range 3이며 Bilog를 지원하지 않는다. 그 외 Band는 Bilog=Range 1, In-band=Range 2, Harmonic=Range 4를 사용한다. | 각 Band가 표의 설정으로 해석되고 LB Group에서 Bilog Test Case가 생성되지 않는다. |
| SRS-LTE-DAT-005 | Range 장비 설정은 기존 NR의 같은 Range 설정을 재사용한다. | LTE 전용 Range 설정값을 새로 만들지 않는다. |
| SRS-LTE-DAT-006 | B34에서 BRF Filter 사용 시 Switch Box port 18을 사용한다. | B34 BRF 경로가 port 18로 설정된다. |
| SRS-LTE-DAT-007 | 지원 Bandwidth와 ARFCN/Frequency는 4.2와 4.4를 따른다. | 46개 Band/Bandwidth 조합이 표와 일치한다. |
| SRS-LTE-DAT-008 | RB Allocation은 4.3을 따른다. | 6개 Bandwidth의 low/mid/high 18개 값이 표와 일치한다. |
| SRS-LTE-DAT-009 | Test Channel low/mid/high와 RB Allocation low/mid/high는 별도 Test Case 파라미터다. | Channel 위치값과 RB 위치값을 독립적으로 저장한다. |

### 3.6 LTE Call과 시험 FSM

| ID | 요구사항 | 인수 기준 |
|---|---|---|
| SRS-LTE-CALL-001 | LTE와 NR은 동일한 MT8000A를 사용한다. | LTE 시험에 별도 Callbox를 요구하지 않는다. |
| SRS-LTE-CALL-002 | LTE는 장비 시험으로 검증된 LTE FDD/TDD Call 파라미터와 API를 사용한다. | LTE 대표 Test Case가 검증된 LTE 계약으로 Call된다. |
| SRS-LTE-CALL-003 | LTE는 Band Group이 지원하는 TestType에 한해 기존 NR과 같은 공통 측정 FSM과 로직을 사용한다. LB Group은 In-band와 Harmonic만 지원하고 Bilog를 지원하지 않는다. | LTE 전용 측정 로직을 별도로 복제하지 않으며 LB Group이 Bilog FSM으로 진입하지 않는다. |
| SRS-LTE-CALL-004 | 같은 Recall 내 다음 LTE Test Case 전환은 Handover를 사용한다. | 전환이 LTE Handover API로 수행된다. |
| SRS-LTE-CALL-005 | LTE Call/Handover 설정은 현재 Test Case에 종속된다. | 다음 Test Case 설정으로 Handover한다. |
| SRS-LTE-CALL-006 | Recall이 바뀌는 전환은 SRS-RCL-004의 흐름을 사용한다. | Handover만으로 Recall 변경을 대체하지 않는다. |
| SRS-LTE-CALL-007 | LTE 추가로 기존 NR Call/Handover 동작을 변경하지 않는다. | 기존 NR Call 회귀가 유지된다. |

### 3.7 LTE UI/UX

| ID | 요구사항 | 인수 기준 |
|---|---|---|
| SRS-LTE-UI-001 | Test Manager의 LTE 진입점에서 LTE Test Case 생성 화면을 연다. | LTE 버튼에서 실제 생성 화면으로 진입한다. |
| SRS-LTE-UI-002 | LTE 신규 화면에서 Select와 Parameter Table을 하나의 화면으로 통합한다. | 선택, 파라미터 확인, Test Case 추가를 한 화면에서 수행한다. |
| SRS-LTE-UI-003 | 기존 NR Select/Table 화면은 변경하지 않는다. | LTE UI 개발로 NR 화면 구조가 바뀌지 않는다. |
| SRS-LTE-UI-004 | LTE 화면은 4장의 Band, BW, Channel/Frequency, RB, SCS, QPSK 값을 사용한다. | 지원되지 않는 LTE 조합을 생성하지 않는다. |
| SRS-LTE-UI-005 | LTE 전용 Table과 NR/LTE 공용 UI는 모두 `ARFCN`을 사용한다. CSV에는 ARFCN 채널 번호 열을 두지 않는다. | 각 화면에 지정된 표기가 표시되고 CSV는 Band, Bandwidth, Test Channel로 채널 번호와 Frequency를 파생한다. |

#### LTE 통합 화면 상세 계약

- 기존 NR과 동일한 선택 의미와 Test Case 조합 방식을 사용하되 Select와 Parameter Table을 하나의 화면으로 통합한다.
- Table 열 순서는 Band 선택, LTE Band, BW, RB Allocation, Channel, EUT ANT, ARFCN, Frequency, RB Size, RB Offset, Test 대역, Position이다.
- LTE Band 헤더 체크박스는 전체 11개 Band를, LB/MHB_FDD/MHB_TDD 그룹 체크박스는 해당 그룹의 Band를 모두 선택하거나 해제한다. 개별 Band 체크박스도 제공한다.
- LB Test 대역은 30M-1G(In-band), 1-12.75G(Harmonic)이며 Bilog를 제공하지 않는다.
- MHB_FDD와 MHB_TDD Test 대역은 30M-1G(Bilog), 1-3G(In-band), 3-12.75G(Harmonic)이다.
- Position은 기존 NR과 동일한 Axis X/Y/Z/X->Y->Z/Z->Y->X 및 Pol H/V/H->V/V->H를 제공한다.
- ARFCN, Frequency, RB Size, RB Offset은 읽기 전용 파생값이다. SCS 15 kHz와 QPSK는 같은 화면에서 읽기 전용 고정값으로 확인할 수 있어야 한다.
- 화면 크기와 열 폭은 기존 NR 및 제공된 LTE Table 참고 화면과 크게 다르지 않게 구성하며 엄격한 픽셀 일치는 요구하지 않는다.

### 3.8 LTE Result Write와 SA PNG

| ID | 요구사항 | 인수 기준 |
|---|---|---|
| SRS-LTE-RPT-001 | LTE는 NR과 구분되는 LTE RawData Excel 양식을 사용한다. | LTE 결과를 NR 전용 레이아웃에 기록하지 않는다. |
| SRS-LTE-RPT-002 | 시험 시작 시 선택한 Excel이 Queue의 NR/LTE에 대응하는지 Sheet명으로 확인한다. | Sheet명 외 내용이나 버전을 검증 조건으로 사용하지 않는다. |
| SRS-LTE-RPT-003 | LTE 측정 결과를 LTE RawData Sheet와 셀 매핑에 따라 기록한다. | 해당 Issue 착수 시 제공되는 Sheet명과 셀 좌표를 사용한다. |
| SRS-LTE-RPT-004 | LTE Plot은 Spectrum Analyzer가 생성한 SA PNG다. | LTE Plot 저장 대상이 SA PNG로 처리된다. |
| SRS-LTE-RPT-005 | LTE SA PNG를 지정된 경로와 파일명 규칙으로 저장한다. | 해당 Issue 착수 시 제공되는 저장 규칙을 사용한다. |
| SRS-LTE-RPT-006 | LTE 결과 기능으로 기존 NR RawData와 SA PNG 규칙을 변경하지 않는다. | 기존 NR 결과 저장 회귀가 유지된다. |

### 3.9 기술 제약

- Python은 장비 제어 목적으로 VISA 세션을 열거나 SCPI를 전송하지 않는다.
- 장비 제어는 외부 LabVIEW 프로그램과 TCP/JSON으로 수행한다.
- LTE에서도 기존 TestRange와 공통 측정 FSM을 재사용한다.
- 실제 장비 명령은 장비 시험으로 검증한 뒤 API 규격을 확정한다.
- Python 검증은 Mock/loopback을 우선하며 실제 장비 시험은 승인된 환경에서 수행한다.
- 이번 버전에서 기존 장비 연결/skip 정책을 변경하지 않는다.

### 3.10 목표 시험 흐름

#### 첫 Test Case

1. NR/LTE 혼합 Queue 여부를 확인한다.
2. 선택 Excel의 Sheet명으로 Queue와 양식의 NR/LTE 대응을 확인한다.
3. Test Case의 Band Group에서 Recall 식별자와 Factor 키워드를 조회한다.
4. Parameter Recall을 수행한다.
5. 현재 Test Case 설정으로 Call Start를 수행한다.
6. Call 연결을 확인한다.
7. Factor 키워드 포함 파일 한 개를 찾아 Set TDF를 수행한다.
8. 공통 측정 FSM으로 진입한다.

#### Recall이 변경되는 다음 Test Case

1. Call Stop을 수행한다.
2. 다음 Test Case의 Recall 식별자를 확장자 없이 전달해 적용한다.
3. 다음 Test Case 설정으로 Call Start를 수행한다.
4. Call 연결을 확인한다.
5. Factor가 변경되는 경우 Set TDF를 수행한다.
6. 공통 측정 FSM으로 진입한다.

#### 같은 Recall 내 다음 Test Case

측정 진입 전 다음 항목을 완료한다.

- LTE는 다음 Test Case 설정으로 Handover한다.
- Factor가 변경되는 경우 Set TDF를 수행한다.

같은 Recall 전환에서는 Handover와 필요한 Factor 적용이 모두 완료된 후 측정으로 진입한다.

## 4. LTE 기준 데이터

이 절의 정규화된 Bandwidth, Channel/Frequency, RB Allocation 표를 LTE 구현·검증의 최종 기준으로 사용한다.

### 4.1 Band 설정

| LTE Band | Test Range | Factor 키워드 | Recall 식별자 | SCS | Turntable speed |
|---|---|---|---|---:|---:|
| 5, 8, 20, 28 | 1, 3 | `1G HPF` | `LTE_FDD` | 15 kHz | 5 |
| 1, 3, 7 | 1, 2, 4 | `3G HPF` | `LTE_FDD` | 15 kHz | 5 |
| 34, 38, 40, 41 | 1, 2, 4 | `3G HPF` | `LTE_TDD` | 15 kHz | 3 |

Recall 열은 확장자 없이 외부 명령에 전달하는 불투명 식별자이며, 프로그램은 Group key나 식별자의 FDD/TDD 문자열을 해석하지 않는다. 각 Test Range의 장비 설정은 기존 NR의 같은 Range 설정을 사용한다. TestType/Range 매핑도 기존 NR과 동일하다. LB Group(Band 5, 8, 20, 28)은 In-band=Range 1, Harmonic=Range 3이며 Bilog를 지원하지 않는다. Band 1, 3, 7과 Band 34, 38, 40, 41은 Bilog=Range 1, In-band=Range 2, Harmonic=Range 4를 사용한다. B34에서 BRF Filter를 사용할 때는 Switch Box port 18을 사용한다.

### 4.2 지원 Bandwidth

| LTE Band | Bandwidth (MHz) |
|---:|---|
| 1 | 5, 10, 15, 20 |
| 3 | 1.4, 3, 5, 10, 15, 20 |
| 5 | 1.4, 3, 5, 10 |
| 7 | 5, 10, 15, 20 |
| 8 | 1.4, 3, 5, 10 |
| 20 | 5, 10, 15, 20 |
| 28 | 3, 5, 10, 15, 20 |
| 34 | 5, 10, 15 |
| 38 | 5, 10, 15, 20 |
| 40 | 5, 10, 15, 20 |
| 41 | 5, 10, 15, 20 |

### 4.3 RB Allocation

모든 조합에서 Modulation은 QPSK, RB Size는 1이다.

| Bandwidth (MHz) | `low` Offset | `mid` Offset | `high` Offset |
|---:|---:|---:|---:|
| 1.4 | 0 | 3 | 5 |
| 3 | 0 | 7 | 14 |
| 5 | 0 | 12 | 24 |
| 10 | 0 | 24 | 49 |
| 15 | 0 | 36 | 74 |
| 20 | 0 | 49 | 99 |

### 4.4 LTE ARFCN/Frequency

ARFCN과 Frequency의 값 순서는 `low / mid / high`이며 Frequency 단위는 MHz다.

| Band | BW (MHz) | ARFCN low / mid / high | Frequency low / mid / high (MHz) |
|---:|---:|---|---|
| 1 | 5 | 18025 / 18300 / 18575 | 1922.5 / 1950 / 1977.5 |
| 1 | 10 | 18050 / 18300 / 18550 | 1925 / 1950 / 1975 |
| 1 | 15 | 18075 / 18300 / 18525 | 1927.5 / 1950 / 1972.5 |
| 1 | 20 | 18100 / 18300 / 18500 | 1930 / 1950 / 1970 |
| 3 | 1.4 | 19207 / 19575 / 19943 | 1710.7 / 1747.5 / 1784.3 |
| 3 | 3 | 19215 / 19575 / 19935 | 1711.5 / 1747.5 / 1783.5 |
| 3 | 5 | 19225 / 19575 / 19925 | 1712.5 / 1747.5 / 1782.5 |
| 3 | 10 | 19250 / 19575 / 19900 | 1715 / 1747.5 / 1780 |
| 3 | 15 | 19275 / 19575 / 19875 | 1717.5 / 1747.5 / 1777.5 |
| 3 | 20 | 19300 / 19575 / 19850 | 1720 / 1747.5 / 1775 |
| 5 | 1.4 | 20407 / 20525 / 20643 | 824.7 / 836.5 / 848.3 |
| 5 | 3 | 20415 / 20525 / 20635 | 825.5 / 836.5 / 847.5 |
| 5 | 5 | 20425 / 20525 / 20625 | 826.5 / 836.5 / 846.5 |
| 5 | 10 | 20450 / 20525 / 20600 | 829 / 836.5 / 844 |
| 7 | 5 | 20775 / 21100 / 21425 | 2502.5 / 2535 / 2567.5 |
| 7 | 10 | 20800 / 21100 / 21400 | 2505 / 2535 / 2565 |
| 7 | 15 | 20825 / 21100 / 21375 | 2507.5 / 2535 / 2562.5 |
| 7 | 20 | 20850 / 21100 / 21350 | 2510 / 2535 / 2560 |
| 8 | 1.4 | 21457 / 21625 / 21793 | 880.7 / 897.5 / 914.3 |
| 8 | 3 | 21465 / 21625 / 21785 | 881.5 / 897.5 / 913.5 |
| 8 | 5 | 21475 / 21625 / 21775 | 882.5 / 897.5 / 912.5 |
| 8 | 10 | 21500 / 21625 / 21750 | 885 / 897.5 / 910 |
| 20 | 5 | 24175 / 24300 / 24425 | 834.5 / 847 / 859.5 |
| 20 | 10 | 24200 / 24300 / 24400 | 837 / 847 / 857 |
| 20 | 15 | 24225 / 24300 / 24375 | 839.5 / 847 / 854.5 |
| 20 | 20 | 24250 / 24300 / 24350 | 842 / 847 / 852 |
| 28 | 3 | 27225 / 27375 / 27645 | 704.5 / 719.5 / 746.5 |
| 28 | 5 | 27235 / 27385 / 27635 | 705.5 / 720.5 / 745.5 |
| 28 | 10 | 27260 / 27410 / 27610 | 708 / 723 / 743 |
| 28 | 15 | 27285 / 27435 / 27585 | 710.5 / 725.5 / 740.5 |
| 28 | 20 | 27310 / 27460 / 27560 | 713 / 728 / 738 |
| 34 | 5 | 36225 / 36275 / 36325 | 2012.5 / 2017.5 / 2022.5 |
| 34 | 10 | 36250 / 36275 / 36300 | 2015 / 2017.5 / 2020 |
| 34 | 15 | 36275 / 36275 / 36275 | 2017.5 / 2017.5 / 2017.5 |
| 38 | 5 | 37775 / 38000 / 38225 | 2572.5 / 2595 / 2617.5 |
| 38 | 10 | 37800 / 38000 / 38200 | 2575 / 2595 / 2615 |
| 38 | 15 | 37825 / 38000 / 38175 | 2577.5 / 2595 / 2612.5 |
| 38 | 20 | 37850 / 38000 / 38150 | 2580 / 2595 / 2610 |
| 40 | 5 | 38675 / 39150 / 39625 | 2302.5 / 2350 / 2397.5 |
| 40 | 10 | 38700 / 39150 / 39600 | 2305 / 2350 / 2395 |
| 40 | 15 | 38725 / 39150 / 39575 | 2307.5 / 2350 / 2392.5 |
| 40 | 20 | 38750 / 39150 / 39550 | 2310 / 2350 / 2390 |
| 41 | 5 | 39675 / 40620 / 41565 | 2498.5 / 2593 / 2687.5 |
| 41 | 10 | 39700 / 40620 / 41540 | 2501 / 2593 / 2685 |
| 41 | 15 | 39725 / 40620 / 41515 | 2503.5 / 2593 / 2682.5 |
| 41 | 20 | 39750 / 40620 / 41490 | 2506 / 2593 / 2680 |

## 5. 시스템 인수 시나리오

| ID | 시나리오 | 기대 결과 |
|---|---|---|
| SAT-001 | TDF List에 Factor 키워드 포함 파일이 한 개 존재 | 해당 파일을 Set TDF에 전달한다. |
| SAT-002 | TDF List에 같은 키워드 포함 파일이 두 개 이상 존재 | Error를 발생시키고 임의 파일을 선택하지 않는다. |
| SAT-003 | 첫 NR 또는 LTE Test Case 시작 | Recall → Call Start → 연결 확인 → Factor → 측정 순서로 진행한다. |
| SAT-004 | 같은 Factor가 이어지는 Test Case | Set TDF를 중복 호출하지 않는다. |
| SAT-005 | 다음 Test Case에서 Recall 변경 | Call Stop → 새 Recall → Call Start → 연결 확인 → 필요한 Factor → 측정 순서로 진행한다. |
| SAT-006 | 같은 Recall 내 다음 LTE Test Case | 다음 Test Case 설정으로 Handover한다. |
| SAT-007 | 지원 LTE Test Case 생성 | Band, BW, ARFCN, Frequency, RB, SCS, QPSK가 4장과 일치한다. |
| SAT-008 | LTE B34에서 BRF Filter 사용 | Switch Box port 18을 사용한다. |
| SAT-009 | NR과 LTE가 섞인 Queue 실행 시도 | 혼합 Queue로 시험을 실행하지 않는다. |
| SAT-010 | LTE Test Case 화면 사용 | Select와 Parameter Table이 한 화면에 있으며 기존 NR 화면은 유지된다. |
| SAT-011 | Queue와 다른 RAT의 Excel 선택 | Sheet명 확인에서 NR/LTE 양식 불일치를 검출한다. |
| SAT-012 | LTE 측정 완료 | 지정된 LTE RawData 셀에 결과를 기록하고 SA PNG를 저장한다. |
| SAT-013 | LTE 개발 후 기존 NR 대표 시험 | 기존 NR Call, 측정, RawData, SA PNG가 유지된다. |

## 6. Jira 백로그

Jira에는 Epic 2개와 하위 Issue 13개를 생성한다. 아래 Issue Type은 제안값이며 실제 Jira 프로젝트의 사용 가능한 Type에 맞춰 매핑한다. Priority, Story Point, 담당자, Sprint는 Refinement 전 지정하지 않는다.

### 6.1 Epic A — FSV Factor 및 MT8000A Parameter Recall 자동화

#### Epic 목표

시험원이 시험 전에 FSV Factor와 MT8000A Parameter Recall을 수동 설정하지 않아도 현재 Test Case에 맞는 설정을 시험 시퀀스가 적용한다.

#### Epic 완료 기준

- Band Group 키워드로 TDF 파일을 자동 선택한다.
- 첫 Test Case와 변경 Test Case에서 필요한 경우에만 Factor를 적용한다.
- 현재 Test Case의 Band Group에서 Recall 식별자를 조회하고 이전 식별자와 다른 경우에만 변경한다.
- 활성 Call 상태에서 Recall이 바뀌면 Call Stop → Recall → Call Start 흐름으로 동작한다.
- Call 연결 확인 후 Factor와 측정으로 진행한다.
- 기존 NR 시험 동작이 유지된다.

#### A-01 [Story] Band Group 키워드 기반 TDF 자동 적용

**관련 요구사항:** SRS-TDF-001~006

**구현 범위**

- Band Group에서 Factor 키워드 결정
- TDF List 포함 검색
- 단일 매칭 파일 선택 및 복수 매칭 Error
- Set TDF 호출
- 첫 Test Case 및 Factor 변경 시 자동 적용
- 시험 시작의 수동 TDF 선택 의존 제거

**Acceptance Criteria**

- [ ] `3G HPF`가 예시 파일명과 포함 검색으로 매칭된다.
- [ ] 매칭 파일 한 개를 Set TDF에 전달한다.
- [ ] 같은 키워드 파일이 두 개 이상이면 Error가 발생한다.
- [ ] 같은 Factor가 이어지면 Set TDF를 재호출하지 않는다.
- [ ] 사용자가 시험 전 TDF를 수동 선택하지 않아도 시작할 수 있다.

**의존성:** 없음

#### A-02 [Spike] MT8000A Call Stop/Recall/Call Start 명령 시험 및 API 계약

**관련 요구사항:** SRS-RCL-001, SRS-RCL-004~007

**시험 범위**

- Call Stop 명령
- 여섯 개 확장자 없는 Recall 식별자의 Recall 명령
- Call Start 명령
- Call 연결 확인 명령

**Recall 식별자**

- `LTE_FDD`
- `LTE_TDD`
- `5GNR_SA_FDD`
- `5GNR_SA_TDD`
- `5GNR_NSA_FDD`
- `5GNR_NSA_TDD`

**산출물**

- 각 동작의 command와 Params
- 성공 응답과 완료 판정 방식
- LabVIEW와 Python이 공통으로 사용할 TCP/JSON 계약
- 실제 장비 시험 결과

**Acceptance Criteria**

- [ ] 여섯 개 Recall 식별자가 확장자 없이 시험 입력에 포함된다.
- [ ] Stop → Recall → Start → 연결 확인 순서가 장비에서 검증된다.
- [ ] 구현 가능한 요청/응답 규격이 문서화된다.

**의존성:** 없음

#### A-03 [Task] LabVIEW Call Stop/Parameter Recall/Call Start API 구현

**관련 요구사항:** SRS-RCL-004~007

**구현 범위**

- A-02 계약에 따른 MT8000A 제어 코드
- Stop, Recall, Start, 연결 확인 TCP/JSON API
- 기존 NR Call 기능 영향 확인

**Acceptance Criteria**

- [ ] 네 동작이 A-02의 계약과 동일하게 구현된다.
- [ ] 지정된 Recall 식별자가 확장자 없이 장비 명령에 전달된다.
- [ ] 기존 NR Call API 동작이 유지된다.

**의존성:** A-02

#### A-04 [Task] Python Recall/Call 제어 facade 및 Mock 구현

**관련 요구사항:** SRS-RCL-004~007

**구현 범위**

- Stop, Recall, Start, 연결 확인 facade
- A-02 계약에 맞는 요청/응답 매핑
- Mock/loopback 상태와 호출 순서 검증

**Acceptance Criteria**

- [ ] Python API가 A-02 계약과 일치한다.
- [ ] Mock에서 Stop → Recall → Start → 연결 확인 호출 순서를 검증할 수 있다.
- [ ] Python 장비 직접 제어가 추가되지 않는다.

**의존성:** A-02

#### A-05 [Story] Factor/Recall 자동화 FSM 통합

**관련 요구사항:** SRS-TDF-004~006, SRS-RCL-001~007

**구현 범위**

- 첫 Test Case 프로필 자동 적용
- Recall 변경 감지와 자동 전환
- 같은 Recall 및 같은 Factor 중복 작업 생략
- 자동 시험 시퀀스에서 수동 Recall 확인을 요구하지 않음
- Call 연결 확인 후 Factor 및 측정 진입

**Acceptance Criteria**

- [ ] 첫 Test Case가 Recall → Call Start → 연결 확인 → Factor 순서로 진행된다.
- [ ] Recall이 변경될 때 같은 순서로 새 프로필을 적용한다.
- [ ] 같은 Recall과 Factor는 중복 적용하지 않는다.
- [ ] 기존 NR Harmonic, In-band, Bilog가 공통 FSM으로 실행된다.

**의존성:** A-01, A-03, A-04

### 6.2 Epic B — LTE Band 시험 지원

#### Epic 목표

지원 LTE Band의 Test Case를 생성하고, MT8000A LTE Call/Handover와 기존 측정 FSM을 사용해 측정 결과와 SA PNG를 저장한다.

#### Epic 완료 기준

- 11개 LTE Band와 46개 Band/Bandwidth 조합을 지원한다.
- SCS 15 kHz, QPSK, RB Size 1과 18개 RB Allocation 값을 적용한다.
- LTE FDD/TDD Call과 Handover가 동작한다.
- LTE 신규 통합 화면에서 Test Case를 생성한다.
- LTE RawData와 SA PNG를 저장한다.
- NR/LTE 혼합 Queue를 실행하지 않는다.
- 기존 NR 동작이 유지된다.

#### B-01 [Task] LTE Test Case 모델 및 기준 데이터 구현

**관련 요구사항:** SRS-GEN-001~004, SRS-LTE-DAT-001~009

**구현 범위**

- LTE Generation과 Band 모델
- Band 설정, Range, B34 port 18
- LB Group(Band 5, 8, 20, 28)의 In-band=Range 1, Harmonic=Range 3 및 Bilog 미지원
- 46개 ARFCN/Frequency/Bandwidth 조합
- 18개 RB Allocation 값
- SCS 15 kHz, QPSK, RB Size 1
- `LTE`, `B1`, `low/mid/high` canonical 값
- NR/LTE 혼합 Queue 검증

**Acceptance Criteria**

- [ ] 4장의 모든 LTE 값이 모델 lookup 결과와 일치한다.
- [ ] 지원하지 않는 Band/BW 조합을 LTE Test Case로 만들지 않는다.
- [ ] B34 BRF 경로가 port 18을 사용한다.
- [ ] LB Group에서 In-band=Range 1, Harmonic=Range 3으로 매핑되고 Bilog Test Case가 생성되지 않는다.
- [ ] LTE CSV가 canonical 값으로 round-trip된다.
- [ ] LTE CSV에는 ARFCN 채널 번호 열이 없고 Band, Bandwidth, Test Channel로부터 채널 번호와 Frequency를 파생한다.
- [ ] NR/LTE 혼합 Queue가 시험 실행 대상으로 승인되지 않는다.
- [ ] 기존 NR 모델 결과가 유지된다.

**의존성:** 없음

#### B-02 [Spike] MT8000A LTE FDD/TDD Call 및 Handover 명령 시험

**관련 요구사항:** SRS-LTE-CALL-001, SRS-LTE-CALL-002, SRS-LTE-CALL-004~006

**시험 범위**

- LTE FDD Call Start와 연결 확인
- LTE TDD Call Start와 연결 확인
- 같은 Recall 내 LTE Handover
- Test Case별 LTE Call 파라미터 매핑

**산출물**

- LTE Call/Handover command와 Params
- 성공 응답과 완료 판정 방식
- FDD/TDD 파라미터 매핑
- 실제 장비 시험 결과

**Acceptance Criteria**

- [ ] LTE FDD/TDD 대표 설정으로 Call이 검증된다.
- [ ] Handover가 다음 Test Case 설정으로 검증된다.
- [ ] LabVIEW와 Python 구현에 사용할 API 계약이 문서화된다.

**의존성:** 없음

#### B-03 [Task] LabVIEW LTE Call/Handover 구현

**관련 요구사항:** SRS-LTE-CALL-001~007

**구현 범위**

- B-02 계약에 따른 LTE FDD/TDD Call
- LTE Handover
- LTE Call 연결 확인
- 기존 NR 제어 로직과의 영향 분리

**Acceptance Criteria**

- [ ] LTE FDD/TDD Call과 Handover가 B-02 계약으로 동작한다.
- [ ] LTE Test Case 설정이 장비 Params에 반영된다.
- [ ] 기존 NR Call/Handover가 유지된다.

**의존성:** B-02

#### B-04 [Task] Python LTE Call/Handover facade 및 Mock 구현

**관련 요구사항:** SRS-LTE-CALL-001~007

**구현 범위**

- LTE Call, Handover, 연결 확인 facade
- B-02 계약에 맞는 요청/응답 매핑
- LTE FDD/TDD/Handover Mock/loopback 경로

**Acceptance Criteria**

- [ ] Python API가 B-02 계약과 일치한다.
- [ ] Mock에서 LTE FDD/TDD Call과 Handover를 검증할 수 있다.
- [ ] 기존 NR facade와 Mock 동작이 유지된다.

**의존성:** B-02

#### B-05 [Story] LTE Call 라우팅 및 공통 측정 FSM 통합

**관련 요구사항:** SRS-LTE-CALL-001~007, SRS-TDF-005~006, SRS-RCL-003~006

**구현 범위**

- LTE Generation의 LTE Call 경로 선택
- 같은 Recall 전환의 Handover
- Recall 변경 시 Epic A 자동화 흐름 사용
- 필요한 Factor 적용 후 Band Group이 지원하는 TestType으로 진입

**Acceptance Criteria**

- [ ] LTE FDD/TDD가 LTE Call 경로로 진입한다.
- [ ] 같은 Recall의 다음 LTE Test Case는 LTE Handover API로 전환한다.
- [ ] Recall 변경 시 A-05 흐름을 사용한다.
- [ ] Band Group이 지원하는 TestType이 기존 공통 측정 FSM을 사용한다.
- [ ] LB Group은 In-band와 Harmonic만 사용하며 Bilog FSM으로 진입하지 않는다.
- [ ] 기존 NR FSM 라우팅이 유지된다.

**의존성:** A-05, B-01, B-03, B-04

#### B-06 [Story] LTE 통합형 Test Case 생성 화면 구현

**관련 요구사항:** SRS-LTE-UI-001~005, SRS-GEN-001~003

**구현 범위**

- Test Manager LTE 진입점 연결
- 기존 NR과 동일한 선택·조합 UX를 사용하는 LTE Select/Parameter Table 단일 화면
- LB, MHB_FDD, MHB_TDD 및 전체·그룹·개별 Band 체크박스
- BW, RB Allocation, Channel, EUT ANT 선택과 ARFCN/Frequency/RB Size/RB Offset 파생 표시
- 그룹별 Test 대역과 기존 NR 동일 Axis/Pol Position 선택
- SCS 15 kHz와 QPSK 고정값 표시
- CSV에는 ARFCN 채널 번호 열을 추가하지 않고 Band, Bandwidth, Test Channel로 채널 번호와 Frequency 파생
- 직전 Band별 파라미터와 그룹별 설정 복원
- 기존 NR 화면 유지

**Acceptance Criteria**

- [ ] LTE 버튼으로 신규 LTE 화면을 연다.
- [ ] 한 화면에서 LTE Test Case를 선택, 확인, 추가할 수 있다.
- [ ] LTE Band 헤더 체크박스로 전체 11개 Band가 선택·해제된다.
- [ ] 각 Band Group 체크박스로 해당 그룹 Band가 선택·해제된다.
- [ ] 개별 Band 체크박스와 전체·그룹 체크박스 상태가 일관된다.
- [ ] Table 열 순서와 ARFCN 표기가 확정 계약과 일치한다.
- [ ] LB에는 Bilog가 없고 MHB_FDD/MHB_TDD에는 Bilog, In-band, Harmonic이 제공된다.
- [ ] Position과 Test Case 조합 순서가 기존 NR과 동일하다.
- [ ] 화면 값이 지원 데이터와 일치하고 SCS 15 kHz와 QPSK 외 값을 생성하지 않는다.
- [ ] 화면 크기와 열 폭이 기존 NR 및 참고 화면과 크게 다르지 않다.
- [ ] 기존 NR Select/Table 화면이 변경되지 않는다.

**의존성:** B-01

#### B-07 [Story] LTE RawData 검증·결과 기록 및 SA PNG 저장

**관련 요구사항:** SRS-LTE-RPT-001~006

**착수 입력**

- LTE RawData 실제 Sheet명과 셀 매핑
- LTE SA PNG 저장 경로와 파일명 규칙

**구현 범위**

- Sheet명에 따른 NR/LTE 양식 판별
- LTE RawData 결과 기록
- LTE SA PNG 저장
- 기존 NR 결과 저장 유지

**Acceptance Criteria**

- [ ] 시험 시작 시 Sheet명으로 선택 양식의 NR/LTE 대응을 확인한다.
- [ ] Sheet 내용이나 버전을 추가 검증하지 않는다.
- [ ] 제공된 셀 매핑에 LTE 결과를 기록한다.
- [ ] 제공된 규칙으로 SA PNG를 저장한다.
- [ ] 기존 NR RawData와 SA PNG 저장이 유지된다.

**의존성:** B-01, 착수 입력 제공

#### B-08 [Task] LTE 통합 및 기존 NR 회귀 검증

**관련 요구사항:** 전체 SRS

**검증 범위**

- Epic A 자동화 흐름
- LTE FDD/TDD 대표 Band
- LTE B34 BRF port 18
- Band Group별 지원 TestType과 Range 매핑
- LB Group의 Bilog 선택·실행 차단
- NR/LTE 혼합 Queue 차단
- LTE RawData와 SA PNG
- 기존 NR Call, 측정, 결과 저장

**Acceptance Criteria**

- [ ] SAT-001~SAT-013의 검증 증적이 남는다.
- [ ] Mock/loopback 통합 검증이 통과한다.
- [ ] 승인된 환경에서 LTE 대표 실장비 시험이 완료된다.
- [ ] 기존 NR 대표 회귀가 통과한다.

**의존성:** A-05, B-05, B-06, B-07

## 7. Issue 의존성

```text
A-01 ───────────────────────────────┐
A-02 ──┬─> A-03 ───────────────────┼─> A-05 ──────────────┐
       └─> A-04 ───────────────────┘                       │
                                                          ├─> B-05 ──┐
B-01 ──────────────────────────────────────────────────────┤          │
B-02 ──┬─> B-03 ──────────────────────────────────────────┤          │
       └─> B-04 ──────────────────────────────────────────┘          ├─> B-08
B-01 ──> B-06 ───────────────────────────────────────────────────────┤
B-01 ──> B-07 ───────────────────────────────────────────────────────┘
```

## 8. 요구사항 추적성

| SRS 영역 | 구현 Issue | 시스템 인수 시나리오 |
|---|---|---|
| SRS-GEN | B-01, B-06, B-08 | SAT-007, SAT-009, SAT-010 |
| SRS-TDF | A-01, A-05, B-05, B-08 | SAT-001~SAT-005 |
| SRS-RCL | A-02~A-05, B-05, B-08 | SAT-003, SAT-005 |
| SRS-LTE-DAT | B-01, B-06, B-08 | SAT-007, SAT-008 |
| SRS-LTE-CALL | B-02~B-05, B-08 | SAT-006, SAT-013 |
| SRS-LTE-UI | B-06, B-08 | SAT-010 |
| SRS-LTE-RPT | B-07, B-08 | SAT-011~SAT-013 |

