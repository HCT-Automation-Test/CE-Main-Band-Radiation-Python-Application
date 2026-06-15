# Project: CE NR Radiated 측정 자동화 SW (PySide6)

이 파일의 범위는 저장소 루트 전체다. Codex는 이 파일을 프로젝트 작업 지침으로 사용한다.
내용은 기존 `CLAUDE.md`의 핵심 규칙을 Codex용으로 정리한 것이다.

## Project Overview

이 프로젝트는 **CE 규격 NR Radiated 방사 측정 자동화 소프트웨어**다. PySide6 기반 데스크톱 앱으로,
시험 오퍼레이터가 Test Case를 관리하고 시퀀스를 실행하며 결과 리포트를 생성하는
**오케스트레이션 + UI + 리포트** 계층을 담당한다.

- 도메인: NR SA (MVP), 이후 NSA / LTE 확장 예정
- 시험 종류: Harmonic, In-band, Bilog
- 장비:
  - `MT8000A`: NR Callbox
  - `FSV40`: Spectrum Analyzer
  - `Switch Box`: 입력/필터 경로 선택
  - `CO3000`: Turntable
- 장비의 **VISA 직접 제어는 외부 LabVIEW 프로그램 책임**이다.
- Python 앱은 장비 제어를 위해 VISA 세션을 직접 열거나 SCPI/장비 명령을 직접 전송하지 않는다.
- 장비 연결, 설정, 측정, 상태 확인은 외부 프로그램과 **TCP 기반 JSON 프로토콜**로만 수행한다.
- 예외적으로 UI 입력 편의를 위한 로컬 VISA Resource 주소 목록 조회는 허용한다.

## Bilog / In-band Protocol Policy

현장 챔버 1차 컨펌 기준으로 Bilog는 In-band와 시험 과정상 동일한 LV 측정 프로토콜을 사용한다.
Bilog와 In-band의 차이는 방사원 신호와 스펙트럼 분석 대역/Range 설정 표시 차이에 한정된다.

- Bilog 측정 command는 In-band와 동일하게 `FSV40 / Mark Inband`를 사용한다.
- Python `measure_bilog()`가 `measure_inband()` 경로를 위임하는 것은 현재 명세상 의도된 동작이다.
- LV가 측정 중 `temp_dir/inband.png`를 생성하고 Bilog 상태가 그 파일을 소비하는 것도 현재 명세상 의도된 동작이다.
- Bilog 전용 command 또는 별도 임시 스크린샷 파일명은 외부 LV 명세가 변경될 때만 검토한다.

## Python Responsibilities

1. CSV Test Case 로드, 편집, Range 확장
2. 코드 상수 기반 TestRange 정의 및 매핑
3. FSM 기반 시퀀스 실행
4. 외부 프로그램과 TCP/JSON 명령 송수신
5. Excel 템플릿 결과 매핑 및 SA 스크린샷 저장
6. UI에서 장비 상태, TC 편집, 실행 모니터링, 스크린샷, 로그 제공

## Tech Stack

- Python 3.11+
- PySide6 (`QTcpSocket`, `QThread`)
- Package manager: `uv`
- VISA Resource 목록 조회: `pyvisa` (`ResourceManager().list_resources()` 용도에 한정)
- Excel: `openpyxl`
- YAML/JSON: `PyYAML`, 표준 `json`
- Test: `pytest`, `pytest-qt`

## Key Paths

- `src/app/core/`: 테스트케이스 로딩, 검증, runner, FSM
- `src/app/net/`: TCP client, protocol, commands, mock server
- `src/app/report/`: Excel writer, template loader, screenshot store
- `src/app/ui/`: PySide6 UI 로직
- `src/app/ui/generated/`: `pyside6-uic` 생성물, 직접 수정 금지
- `testcases/`: 샘플 CSV
- `config/`: 앱 설정, Excel template 매핑 예시

## Build / Run / Test

```bash
uv sync
uv run pyside6-uic resources/main_window.ui -o src/app/ui/generated/main_window_ui.py
uv run python -m app
uv run --no-sync pytest -q
uv run --no-sync pytest tests/core -k harmonic
```

- 테스트 실행은 기본적으로 `uv run --no-sync pytest ...`를 사용한다.
- 의존성 변경 후 환경 갱신이 필요할 때만 `uv sync`를 별도로 실행한다.
- `uv` 캐시는 저장소 내부 `.uv-cache/`를 사용한다.

## Coding Rules

- 레이어 방향은 `ui -> core -> (net | report)`를 유지한다.
- `net`과 `report`는 `ui`에 의존하지 않는다.
- `core`는 UI 알림 전달을 위해 `QObject`/시그널 사용이 가능하다.
- TCP 송수신과 파일 I/O는 이벤트 루프를 막지 않도록 `QThread` 또는 비동기 시그널 흐름으로 분리한다.
- `.ui`에서 생성된 `*_ui.py`는 `src/app/ui/generated/`에만 두고 직접 편집하지 않는다.
- UI 로직은 생성물이 아닌 래퍼/상속 클래스에 작성한다.
- 경로는 항상 `pathlib.Path`를 사용한다.
- 파일 I/O에는 `encoding="utf-8"`을 명시한다.
- 코드 주석은 한글로 작성한다.
- 시그널 이름은 `something_changed`, 슬롯 이름은 `on_something_changed` 패턴을 따른다.
- `print` 대신 `logging`을 사용한다.
- UI 로그 출력은 `QPlainTextEdit` 미러 핸들러를 우선한다.
- 명세가 미확정인 부분은 `# TODO(spec): ...` 형식으로 남긴다.

## Scope Control / Responsibility Boundaries

Codex는 요청받은 작업 범위 안에서만 변경한다. 구현 중 더 좋은 구조, 관련 버그, 테스트 보강,
리팩터링 필요성을 발견하더라도 사용자가 명시적으로 요청하지 않은 코드는 수정하지 않는다.

- 작업 시작 전 현재 요청의 목적, 변경 대상 파일/모듈, 건드리지 않을 영역을 스스로 구분한다.
- 수정은 요청을 만족하는 데 필요한 최소 파일과 최소 코드로 제한한다.
- `report` 작업은 기본적으로 `src/app/report/**`, 해당 테스트, 필요한 설정 예시에만 한정한다.
- `net` 작업은 기본적으로 `src/app/net/**`, 해당 테스트, 프로토콜 예시에만 한정한다.
- `core/fsm` 작업은 요청이 FSM, 시퀀스, 측정 흐름을 직접 대상으로 할 때만 수정한다.
- `ui` 작업은 요청이 화면, 위젯, 사용자 동작을 직접 대상으로 할 때만 수정한다.
- 특정 기능의 저장소, writer, loader, mapper를 개발하는 중에는 측정 실행 로직, FSM 전이, 장비 명령 순서를 임의로 변경하지 않는다.
- 책임 경계를 넘는 변경이 필요해 보이면 먼저 사용자에게 이유와 영향 범위를 설명하고 승인을 받은 뒤 진행한다.
- 기존 코드에서 요청과 무관한 결함을 발견하면 코드 변경 대신 최종 응답의 "추가 발견사항"으로 보고한다.
- 테스트를 통과시키기 위해 제품 코드를 우회하거나, 요구사항 밖의 동작을 추가하거나, 공개 API 의미를 바꾸지 않는다.
- 단순 정리 목적의 리팩터링, 이름 변경, 파일 이동, 공통화, 추상화 추가는 요청 범위에 포함되어 있을 때만 수행한다.
- 한 브랜치의 목적과 다른 성격의 변경을 섞지 않는다. 예를 들어 screenshot store 브랜치에서 measurement 로직을 임의로 수정하지 않는다.
- 사용자가 "고쳐줘", "구현해줘"라고만 말했더라도, 변경 범위는 해당 이슈/파일/기능의 직접 원인으로 제한한다.

## Temporary Equipment Policy

현재 개발 단계에서는 Harmonic 1차 테스트 완료 후 In-band / Bilog 및 최종 통합 테스트가 남아 있으므로,
일부 장비가 미연결인 상태에서도 선택 연결된 장비 기준으로 FSM 흐름을 검증할 수 있다.

- 이 임시 정책에서는 선택/연결되지 않은 장비가 필요한 FSM state가 해당 장비 동작을 스킵하고 다음 state로 진행할 수 있다.
- 이 스킵 정책은 개발/검증 편의를 위한 임시 정책이며 실제 배포/운영 정책이 아니다.
- 실제 배포/운영에서는 필수 장비 전체가 연결되어 있지 않으면 시험을 시작하거나 진행하면 안 된다.
- 다른 agent는 `is_selected_equipment_ready`, 장비 미연결 스킵, 관련 `StateResult.OK` 경로를 최종 제품 요구사항으로 해석하지 말아야 한다.
- 최종 통합 단계에서는 필수 장비 전체 연결 확인 정책으로 되돌리거나 별도 production gate를 추가해야 한다.

## When Adding A New Test Type

1. `src/app/core/fsm/<type>/` 아래에 `states.py`, `sequence.py`를 추가한다.
2. `src/app/core/fsm/registry.py`의 `SEQUENCES`에 등록한다.
3. `src/app/net/commands.py`에 필요한 facade 함수를 추가한다.
4. `src/app/models/enums.py`의 `TestType`에 항목을 추가한다.
5. `tests/core/test_fsm_<type>.py`에 테스트를 작성한다.

## Forbidden / Requires Extra Care

- `src/app/ui/generated/**`는 직접 수정하지 않는다. 필요하면 `.ui`를 수정하고 다시 생성한다.
- Python에서 장비 제어 목적의 VISA 직접 호출은 금지한다.
  - 허용: `pyvisa.ResourceManager().list_resources()` 수준의 로컬 VISA Resource 주소 목록 조회.
  - 금지: `open_resource`, `write`, `read`, `query`, 장비 세션 유지, SCPI 전송, 측정/설정/상태 확인.
  - 조회된 VISA 주소는 LabVIEW TCP 명령의 설정값으로 전달하는 용도에만 사용한다.
- 실제 외부 서버나 실제 장비를 대상으로 하는 통합 테스트는 사용자 승인 없이 실행하지 않는다.
- 기본 검증은 `mock_server` 또는 loopback 기반 테스트를 우선한다.
- 의존성 추가/제거는 `uv add`, `uv remove`로 수행하고 `pyproject.toml` 직접 편집은 피한다.
- 요청 범위 밖의 모듈, 레이어, 테스트를 "겸사겸사" 수정하지 않는다.
- 사용자 승인 없이 측정 흐름, FSM 상태 전이, 장비 명령 순서, 결과 판정 기준을 변경하지 않는다.

## Test Strategy

- `core`, `net`, `report`: 순수 Python 단위 테스트를 우선한다.
- `models`, `ui`: Qt 관련 검증은 `pytest-qt`를 사용한다.
- 통합 테스트는 `src/app/net/mock_server.py` 기반 loopback 테스트를 우선한다.

## Reference Notes

- 기존 프로젝트 설명 문서는 `CLAUDE.md`에 남아 있다.
- Claude 전용 스킬/에이전트 경로가 문서에 남아 있을 수 있지만, Codex 작업 시에는 이 `AGENTS.md`를 우선 지침으로 사용한다.
