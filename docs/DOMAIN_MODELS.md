# 도메인 모델 — 심화

> 개요는 [PROJECT_SPEC_1.0.1.md](PROJECT_SPEC_1.0.1.md) §10 참조.
> 이 문서는 테이블 수치·매핑 규칙·확장 체크리스트를 다루는 심화 문서다.

[src/app/models/](../src/app/models/)는 Qt에 의존하지 않는 순수 Python 상수·데이터클래스·
lookup 함수만 담는 최하위 leaf 계층이다. **모든 테이블(지원 대역폭, RB 파라미터, 채널
lookup, Band 그룹)은 JSON/DB가 아니라 코드 상수로 유지**하는 것이 설계 원칙이다.

## 1. 열거형 — [enums.py](../src/app/models/enums.py)

| Enum | 값 | 용도 |
| --- | --- | --- |
| `NRBand` | n1, n3, n5, n7, n8, n20, n26, n28, n38, n40, n41, n71, n77, n78, n79 (15종) | 지원 NR band |
| `Generation` | `NR_SA`, `NR_NSA`, `LTE` | TestCase Generation. 기본 SA |
| `TestType` | `harmonic`, `inband`, `bilog` | 시험 종류 |
| `AntennaPol` | H, V | 측정 안테나 편파 |
| `DUTAxis` | X, Y, Z | DUT 회전축 |
| `DUTAntPosition` | Upper, Lower | DUT 안테나 위치 |
| `Modulation` | QPSK, `pi/2 BPSK` | NR 변조 |
| `RBAllocation` | Inner_Full, Inner_1RB_Left, Inner_1RB_Right | DFT-s RB allocation 프리셋 (OFDM은 스펙 범위 밖) |
| `TestChannel` | low, mid, high | 시험 채널 위치 |
| `InputPath` (IntEnum) | INPUT1=1(Bilog 안테나), INPUT2=2(3m), INPUT3=3(1m) | Switch Box 입력 경로 |
| `FilterPath` (IntEnum) | THRU=1, DIRECT_AMP=2, HPF_1G/3G/7G/6G, PORT_1~PORT_18 (24종) | 실제 필터 경로. PORT_n은 band별 BRF |
| `FilterMode` (IntEnum) | BRF, HPF_1G, HPF_3G, HPF_6G | Range 정의용 논리 필터. BRF만 band에 따라 실제 경로가 달라짐 |

## 2. TestCase — [test_case.py](../src/app/models/test_case.py)

CSV 한 행 = TestCase 하나. 표준 CSV 컬럼 11개(`CSV_FIELDNAMES`, 순서 고정):

```text
generation, band, anchor_band, bandwidth, test_type, modulation, rb_allocation,
test_channel, antenna_pol, dut_axis, dut_ant_position
```

`anchor_band`는 `NR_NSA`에서만 필수이며 `B1/B3/B7/B5/B8/B20/B28/B38/B40/B41`만
허용한다. `NR_SA`와 `LTE`에서는 비어 있어야 한다. Anchor의 BW/RB/Modulation이나
Anchor Channel lookup은 이 모델에 포함하지 않는다.

기존 10열 CSV는 `NR_SA`와 `LTE`에 한해 읽을 수 있고, 저장하면 빈 `anchor_band`를
포함한 11열로 갱신된다. 10열 `NR_NSA`는 Anchor를 추정하지 않고 마이그레이션 오류로
차단한다.

실행 Queue에는 정확히 하나의 Generation만 허용한다. `NR_SA`, `NR_NSA`, `LTE` 중
둘 이상이 섞이면 `Runner.start()`가 report setup과 FSM 시작 전에 차단한다.

생성 시점(`__post_init__`)에 `resolve_range_id(band, test_type)`와
`validate_supported_bandwidth(band, bandwidth)`로 조합 유효성을 검증한다(실패 시 ValueError).

**파생 프로퍼티** — 입력엔 없지만 band 등에서 계산되는 값:

| 프로퍼티 | 파생 경로 |
| --- | --- |
| `scs_khz` | band → `find_band_group().scs_khz` (LB/FDD=15kHz, TDD=30kHz — SCS는 CSV 입력이 아니라 band에서 파생되는 암묵 규약) |
| `rb_size` / `rb_offset` | (bandwidth, scs, rb_allocation) → [rb_parameters.py](../src/app/models/rb_parameters.py) lookup |
| `test_range` / `range_definition` | (band, test_type) → RangeId → TestRange 상수 |

직렬화: `from_csv_row`(표준 11열, enum 대소문자 무시), `to_csv_row`
(bandwidth는 `.15g` 포맷이라 100.0 → "100").

주의: `TestCase`를 코드에서 직접 생성할 때 문자열 관용 변환이 되는 필드는
generation/band/bandwidth/dut_ant_position/test_channel 5개뿐이다. test_type/modulation/
rb_allocation/antenna_pol/dut_axis는 CSV 경로(`from_csv_row`)에서만 변환된다.

## 3. TestRange — [test_range.py](../src/app/models/test_range.py)

전역 Range 6종. **SA 설정(주파수 구간/RBW/VBW/limit/sweep point)과 Switch Box 경로
(input_path/filter_mode)를 한 단위로 묶은** frozen 상수다. 수치 단위는 MHz/dBm.

| Range | 구간 (MHz) | RBW/VBW | Limit | Sweep | Input | Filter |
| --- | --- | --- | --- | --- | --- | --- |
| RANGE_1 | 30~1000 | 0.1/0.3 | −36.0 | 10001 | INPUT1 | BRF |
| RANGE_2 | 1000~3000 | 1.0/3.0 | −30.0 | 30001 | INPUT2 | BRF |
| RANGE_3 | 1000~12750 | 1.0/3.0 | −30.0 | 30001 | INPUT2 | HPF_1G |
| RANGE_4 | 3000~12750 | 1.0/3.0 | −30.0 | 30001 | INPUT2 | HPF_3G |
| RANGE_5 | 1000~6000 | 1.0/3.0 | −30.0 | 30001 | INPUT3 | BRF |
| RANGE_6 | 6000~18000 | 1.0/3.0 | −30.0 | 30001 | INPUT3 | HPF_6G |

`RangeId.coerce()`는 int/`"range_3"`/`"Range 3"`/`"3"`을 모두 정규화한다.

## 4. Band 그룹 — [band_group.py](../src/app/models/band_group.py)

| 그룹 key | bands | SCS | SA recall | MT8000 recall | 턴테이블 속도 |
| --- | --- | --- | --- | --- | --- |
| `lb` | 5, 8, 20, 26, 28, 71 | 15 | 1G HPF | SA_FDD | 5 |
| `mhb_fdd` | 1, 3, 7 | 15 | 3G HPF | SA_FDD | 5 |
| `mhb_tdd` | 38, 40, 41 | 30 | 3G HPF | SA_TDD | 3 |
| `uhb_tdd` | 77, 78, 79 | 30 | 6G HPF | SA_TDD | 3 |

`RANGE_BY_BAND_TEST`가 (band, TestType) → RangeId를 결정한다:

| 그룹 | BILOG | INBAND | HARMONIC |
| --- | --- | --- | --- |
| lb | **미지원** (ValueError) | RANGE_1 | RANGE_3 |
| mhb_* | RANGE_1 | RANGE_2 | RANGE_4 |
| uhb_tdd | RANGE_1 | RANGE_5 | RANGE_6 |

`mt8000_recall`이 그룹 간에 달라지는 경우(FDD↔TDD)가 FSM의 `RecallChange` 트리거다.

## 5. Lookup 테이블 3종

| 모듈 | 키 → 값 | 비고 |
| --- | --- | --- |
| [supported_bandwidths.py](../src/app/models/supported_bandwidths.py) | band → 지원 BW 목록 | `validate_supported_bandwidth`가 TestCase 생성과 tc_validator 양쪽에서 호출됨 |
| [nr_channel_lookup.py](../src/app/models/nr_channel_lookup.py) | band × BW × TestChannel → `NRChannelProfile(call_channel, target_frequency_mhz)` | **수식 계산이 아니라 하드코딩 3중 dict.** `resolve_call_channel`(NR Call 채널), `resolve_target_frequency_mhz`(Harmonic 기본파 탐색 주파수) |
| [rb_parameters.py](../src/app/models/rb_parameters.py) | (BW, SCS, RBAllocation) → (rb_size, rb_offset) | SCS는 인자가 아니라 band에서 파생. 1RB_LEFT는 항상 (1,1), 1RB_RIGHT는 (1, 대역 끝) |

예: n78 / 100MHz / MID → call channel 636666, 3549.99MHz, INNER_FULL → RB (135, 67).

**중요 — band 정보가 4개 테이블에 분산된다**: supported_bandwidths, nr_channel_lookup,
rb_parameters, band_group(BAND_GROUPS + RANGE_BY_BAND_TEST). 한 곳만 갱신하면 런타임
ValueError로만 드러난다. 알려진 구멍: n28의 25/30MHz는 MID 채널이 정의되어 있지 않다.

## 6. Switch Box 모델 — [switch_box.py](../src/app/models/switch_box.py)

- 표시명: INPUT1→"Bilog", INPUT2→"3m", INPUT3→"1m" (안테나/거리 기준).
- `resolve_filter_path(filter_mode, band)`: HPF 모드는 고정 경로, **BRF 모드는 band별 전용
  포트** — band 순서 (1,3,5,7,8,20,26,28,38,40,41,71,77,78,79)가 PORT_1~PORT_15에 1:1 매핑.
  PORT_16~18과 `FilterPath.HPF_7G`는 미할당 예비 값.
- `parse_band_number("n78"|"N78"|"78") -> 78` — models 전반의 공용 band 파서.

## 7. 측정 결과 — [measurement_result.py](../src/app/models/measurement_result.py)

| dataclass | 필드 요점 |
| --- | --- |
| `HarmonicMarker` / `HarmonicPrecisionCandidate` | order, amplitude_dbm, peak_frequency_mhz |
| `FundamentalResult` | screenshot_path, fundamental_frequency_mhz |
| `HarmonicResult` | screenshot_path + 2nd~5th peak level (각 `float \| None`) |
| `InbandResult` / `BilogResult` | screenshot_path + 단일 peak level |

`MeasurementResult`는 위 4종의 union 타입 별칭. **peak 레벨 None은 '측정 실패'가 아니라
'limit−10dB 미만이라 기록할 peak 없음'** 을 뜻한다 (`has_recordable_peak` 규약, Excel에는 "-"로 기록).

## 8. TestRunSettings — [test_run_settings.py](../src/app/models/test_run_settings.py)

Test Manager의 시작 시점 사용자 입력을 담는 frozen dataclass. 생성 시점에 검증한다:

| 필드 | 검증 |
| --- | --- |
| `eut_name` | 비어 있거나 leading/trailing whitespace가 있으면 오류 |
| `screenshot_root_dir` | 호환성을 위해 유지한 이름. 기존 경로이면 디렉터리여야 하며, EUT별 RawData workbook과 `screenshots` 폴더를 두는 **EUT 결과 기준 root** |
| `saturation_time_sec` ≥ 0, `connection_waiting_time_sec` > 0 (int) | |
| `atten_level_db` ≥ 0, `next_peak_search_level_db` ∈ (0, 80] | |
| `custom_turntable_speed` | None 또는 1~10 (설정 시 BandGroup 속도보다 우선) |
| `manual_marker_enabled` | bool — 수동 마커 모드 스위치 |

활성 TDF 파일명은 `TestRunSettings` 입력이 아니다. Test Start마다 FSM의 적용 기록을
초기화하고, 현재 `TestCase.factor_keyword`가 대소문자까지 동일하게 포함된 TDF 파일을
목록에서 찾는다. 정확히 한 파일일 때만 자동 적용하며, 없거나 둘 이상이면 시험을
중단한다. 같은 세션에서 직전 적용에 성공한 Factor가 연속되면 목록 조회와 적용을
생략한다.

`default_screenshot_root_dir()`: 패키징 실행이면 exe 폴더, 개발 환경이면 `~/Desktop`.
실제 결과는 `<root>/<EUT>/` 아래에 모이며 기존 `<root>/screenshots/<EUT>` 경로는 사용하지 않는다.

## 9. 새 항목 추가 체크리스트

**새 NR band**: `NRBand` 멤버 → `BAND_GROUPS`(해당 그룹 bands) + `RANGE_BY_BAND_TEST`
3종 매핑 → `_SUPPORTED_BANDWIDTHS_BY_BAND` → `_CHANNEL_LOOKUP_BY_BAND`(BW별 low/mid/high)
→ `_BRF_FILTER_PATH_BY_BAND` 포트 순서 → NR RawData 원본에 `Sub6 {band}` 시트 준비
→ tests/models 파라미터라이즈에 대표 조합 추가.

**새 bandwidth 조합**: supported_bandwidths + nr_channel_lookup + rb_parameters
세 테이블 동시 갱신.

**새 시험 타입**: [FSM.md §7](FSM.md) 통합 절차 참조.

기타 관례: 모델 클래스 이름이 `Test*`로 시작하면 pytest 수집 회피용 `__test__ = False`를
넣는다 (TestCase/TestRange/TestRunSettings가 선례).
