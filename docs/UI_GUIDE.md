# UI 계층 가이드 — 심화

> 개요는 [PROJECT_SPEC_1.0.1.md](PROJECT_SPEC_1.0.1.md) §16 참조.
> 이 문서는 잠금 정책·시그널 결선·패널별 동작과 특이점을 다루는 심화 문서다.

[src/app/ui/](../src/app/ui/)는 PySide6 기반 단일 메인 윈도우와 패널/다이얼로그 집합이다.

## 1. 메인 윈도우 구조 — [main_window.py](../src/app/ui/main_window.py)

`resources/main_window.ui`는 titleLabel 하나뿐인 **최소 골격**이고(즉시 숨겨짐), 실제 화면은
`MainWindow._setup_main_layout()`이 코드로 조립한다:

```text
┌──────────┬────────────────────────────────────────────┐
│ 내비게이션 │  QStackedWidget (subWindowStack)            │
│ 버튼 열   │   index 0: InstrumentCheckPanel             │
│ (148px)  │   index 1: ManualTestPanel (placeholder)    │
│          │   index 2: TestManagerPanel                 │
│  + RF    │   index 3: TestPlotScreenshotPanel          │
│  Filter  │                                             │
│  Box 버튼 │  * RF Filter Box는 스택이 아닌 별도          │
│          │    modeless 창(RFSwitchBoxWindow)            │
└──────────┴────────────────────────────────────────────┘
```

- 창 크기는 기본 1760×940 **고정** — Win32 API로 리사이즈 테두리(WS_THICKFRAME)를
  제거하며, 최대화/전체화면 진입 시에만 해제한다.
- MainWindow는 `Runner`를 생성·소유하고, `TdfService`/`RFSwitchBoxService`는 Runner의
  client/commands를 공유한다.
- `_connect_signals()`가 **유일한 시그널 결선 허브**다 — RunnerEvents,
  InstrumentConnectionService, TdfService, 패널 시그널이 전부 여기서 연결된다.
  새 이벤트 구독은 이 함수에 추가한다.
- 종료 정리: closeEvent에서 RF창 → 자식 패널(`findChildren` 덕타이핑으로
  `shutdown()`/`dispose()` 호출) → TdfService → Runner 순으로 정리한다.
  **워커를 가진 새 패널은 `shutdown()` 메서드만 구현하면 자동 정리에 태워진다.**

## 2. 실행 중 UI 잠금 정책

`_build_instrument_operation_lock_state()` 한 곳이 진실 원천이다.
`measurement_active` / `instrument_set_active` / `tdf_operation_active` /
`connection_in_progress` 4개 상태를 종합해:

- **run_settings_locked** — 측정/Set/TDF 중 하나라도 진행 중이면 Test Manager의 실행
  설정(EUT/Index/Custom Option/버튼)을 잠근다. **정지 버튼만 예외**로 실행 중에도 활성.
- **rf_operation_locked** — 위 + 연결 진행 중이면 RF Switch Box 수동 제어를 잠근다.
- Instrument Check의 Connect/Set 버튼은 block_reason이 있으면 비활성 + 사유 툴팁.
- 역방향 주입: MainWindow가 `runner.add_instrument_connection_blocker()`로
  "RF 수동 작업 중이면 장비 연결 금지" 규칙을 core에 등록한다.

## 3. 패널별 요약

### InstrumentCheckPanel — [instrument_check_panel.py](../src/app/ui/instrument_check_panel.py)

- VISA 장비 4종(CO3000/3D Controller/FSV40/MT8000A)의 editable 콤보 + Switch Box IP/Port
  입력, 장비별 상태 라벨(not_connected/connecting/connected/failed 색상).
- 최초 표시 시 250ms 지연 후 VISA 리소스 자동 탐색(비동기 워커, `list_resources()` 한정).
- Connect: 최소 1개 장비 입력 필요, IP/Port는 둘 다 입력 또는 둘 다 공백. 성공한 장비의
  입력값만 `config/instrument_connection.json`에 병합 저장(다음 실행 시 복원).
- Set: 전체 연결 성공 + FSV40/CO3000/3D Controller 중 하나 이상 연결 시 활성.
  진행 중에는 취소 불가 `InstrumentSetProgressDialog`(경과 시간 표시) 표시.
  Set 실패 시(대상 없음 제외) **전체 장비가 미연결 처리**되어 재연결을 강제한다.

### TestManagerPanel — [test_manager_panel.py](../src/app/ui/test_manager_panel.py)

중심 패널 (약 1,900줄). 구성:

- **TestCase 표** (18컬럼): NR 다이얼로그/CSV에서 추가된 케이스 목록. 실행 중 현재 행은
  노란색 + 중앙 스크롤, 완료 행은 회색. 행 삭제 시 완료 인덱스 재매핑.
- **Operation bar**: EUT Name, Excel 템플릿 찾기, 시작 Index 입력(1-based),
  단일시작/시작/정지/삭제/초기화/불러오기(CSV)/저장(CSV) 버튼.
- **FSV Factor List (TDF)**: List Update(`get_tdf_list`)/Select(`set_tdf`)/All Off.
  시험 외 수동 설정을 위한 편의 기능이며, Test Start의 입력이나 자동 적용의 중복
  판단에는 사용하지 않는다. 시험 시작 후에는 각 TC의 Band Group Factor에 맞춰
  `Get TDF List` → `Set TDF`를 자동 수행하며, 자동 경로에서는 All Off를 호출하지 않는다.
- **Custom Option**: 체크 시 Saturation Time/Connection Waiting Time/Atten Level/
  Turn Table Speed(1~10)/Next Peak Search Level(0~80] 오버라이드 + Marker 체크박스
  (수동 마커 모드). 미체크 시 기본값 5/5/0/6/None.
- **스크린샷 미리보기** + 우측 고정 **LogPanel**(280px).
- RAT 버튼(NR/LTE/WCDMA/GSM): **NR만 결선되어 있다** — LTE/WCDMA/GSM은 버튼만 존재.
  "Case 확인" 버튼은 Range 1~6 설정을 read-only 표로 보여준다.

실행 요청은 `start_requested`/`single_start_requested`/`stop_requested` 시그널로
MainWindow에 위임되고, MainWindow가 `build_test_run_settings()` 검증 후 `Runner.start()`를
호출한다(단일 시작은 stop_index=start_index).

### NR TestCase 생성 — [nr_select.py](../src/app/ui/nr_select.py)

2단 다이얼로그:

1. **NRSelectDialog**: band 그룹 4열의 band 체크박스, 그룹 ALL/RESET 토글, SA/NSA 토글,
   Table/Add 버튼.
2. **NRParameterDialog** (Table 버튼): band별 행에 BW/MOD/RB Allocation/Channel/EUT ANT
   콤보와 NARFCN/주파수/RB Size/Offset 자동 미리보기. 그룹 단위로 시험 대역
   (라벨↔TestType 매핑: lb는 `30M-1G`=INBAND·`1-12.75G`=HARMONIC, mhb/uhb는
   BILOG/INBAND/HARMONIC 3종)과 Axis(X/Y/Z/X→Y→Z/Z→Y→X)/Pol(H/V/H→V/V→H) 시퀀스 선택.

Add 시 **band × 시험타입 × axis 시퀀스 × pol 시퀀스** 중첩 루프로 TestCase 리스트를
생성한다(중첩 순서 = 실행 순서). 다이얼로그 입력값은 패널에 보존되어 재열람 시 복원된다.

### RF Switch Box 수동 제어 — [rf_filter_box_panel.py](../src/app/ui/rf_filter_box_panel.py)

- 별도 modeless 창. 회로도 PNG(`resources/images/rf_switch_box_bd.png`) 위에 입력 3버튼
  (Bilog/3M HORN/1M HORN)과 필터 24버튼을 절대좌표로 오버레이하고, 확정된 경로를 빨간
  선으로 그린다.
- 선택(체크) → SET 버튼 → `RFSwitchBoxService.set_switch_box()` → 성공 시 경로 확정 표시.
  Thru! 버튼은 필터만 THRU로.
- `RFSwitchBoxService`는 **UI 스레드에서 동기 실행**한다(짧은 명령 전제 — 확장 시 주의).
- FSM이 경로를 바꾸면 `switch_box_info_changed` 시그널로 이 패널의 표시도 갱신된다.

### 기타

- **TestPlotScreenshotPanel**: 최신 스크린샷 1장 표시. `screenshot_saved(str)` 수신 →
  확장자/존재/로드 검증 후 비율 유지 스케일. 숨겨진 탭에서 수신해도 탭 전환 시 표시.
- **LogPanel**: logging 핸들러를 Qt 시그널로 미러링(스레드 안전). 기본 root logger,
  블록 상한 1000줄. Test Manager/Instrument Check/Test Plot 패널 우측에 내장.
- **ManualTestPanel**: 빈 placeholder (TODO(spec)).
- **ManualMarkerDialog**: 수동 마커 모드에서 FSM이 요청. Marker 1~10 선택 + Excursion
  입력, Peak/Next Peak/OFF/ALL OFF 버튼이 `Runner.marker_*`를 반복 호출.
  "확인 (종료 후 스크린샷)"이 `user_action_completed`로 FSM 재개.
- **_UserActionDialog**: `user_action_required`(LTE Anchor/비행기 모드/Recall/DUT 축) 시
  뜨는 modal — '중단'(stop)과 '완료'(재개)만 제공.

**수동 조작 계열 다이얼로그 공통 패턴**: reject()/ESC/닫기 버튼을 전부 무력화하고
`close_without_action()`으로만 닫는다. 정리 코드에서 `close()` 대신 이 메서드를 호출할 것.

## 4. 알려진 특이점

- `TestManagerPanel._connection_indicators`는 선언만 되고 채워지지 않아 장비 상태 표시
  setter(`set_connection_state` 등)는 현재 사실상 no-op이다(스타일 규칙만 준비됨).
- SA/SwitchBox/턴테이블/편파 정보 setter가 쓰는 QLineEdit 17종은 **hidden read-only
  필드**다 — 값은 들어가지만 화면에 렌더링되지 않는다(테스트 계약 유지용).
- 스크린샷 미리보기는 1600×1244(하단 44px 패딩) SA 캡처 해상도를 가정한 crop 로직이 있다.
- TestCase 표의 CH_No. 컬럼 의미는 TODO(spec).

## 5. 새 화면 추가 절차

1. `.claude/skills/pyside-widget/SKILL.md`의 `.ui → *_ui.py → 로직 클래스` 분리 규약을 따른다.
2. `main_window.py._setup_main_layout()`에서 `_add_navigation_page()`(스택 페이지) 또는
   `_add_window_button()`(별도 창)으로 등록.
3. 시그널 구독은 `_connect_signals()`에, 워커가 있으면 `shutdown()` 구현.
4. 잠금이 필요하면 `_build_instrument_operation_lock_state()`에 사유를 추가.
5. `tests/ui/`에 qtbot + `findChild(objectName)` 스캐폴드 테스트 작성
   (MainWindow 페이지 수가 늘면 `test_main_window_scaffold.py`의 개수 assert도 갱신).
