# CE NR Radiated Measurement Automation SW

PySide6 기반 **CE NR Radiated 방사 측정 자동화 소프트웨어**입니다. 시험 오퍼레이터가 NR Test Case를 생성/관리하고, 외부 LabVIEW 장비 제어 프로그램과 TCP/JSON으로 연동해 Harmonic, In-band, Bilog 측정 시퀀스를 실행하며, 결과를 Excel 리포트와 Spectrum Analyzer 스크린샷으로 저장합니다.

현재 안정 버전은 **v1.0.1**입니다.

## 핵심 구조

이 저장소의 Python 앱은 **UI + 오케스트레이션 + 리포트** 계층입니다. 실제 장비의 VISA/SCPI 제어는 외부 LabVIEW 프로그램(`LV Inst Manager`)이 담당하며, Python 앱은 장비 제어 목적으로 VISA 세션을 직접 열지 않습니다.

```text
PySide6 UI
  -> core / Runner / FSM
    -> net / TCP JSON command facade -> LabVIEW -> 장비
    -> report / Excel writer + screenshot store
  -> models / NR 도메인 모델과 lookup table
```

대상 장비:

- `MT8000A`: NR Callbox
- `FSV40`: Spectrum Analyzer
- `Switch Box`: RF 입력/필터 경로 선택
- `CO3000`: Turntable
- `3D Controller`: 1m Mast 편파 제어

## 빠른 시작

```bash
uv sync
uv run pyside6-uic resources/main_window.ui -o src/app/ui/generated/main_window_ui.py
uv run python -m app
```

테스트:

```bash
uv run --no-sync pytest -q
uv run --no-sync pytest tests/core -q
uv run --no-sync pytest tests/net -q
uv run --no-sync pytest tests/report -q
uv run --no-sync pytest tests/ui -q
```

실장비/LabVIEW 없이 개발할 때는 모의 LabVIEW 서버를 사용합니다:

```bash
# 터미널 1: 모의 LabVIEW 서버 (기본 127.0.0.1:5025)
uv run python -m app.net.mock_lv_server --temp-dir temp

# 터미널 2: 앱 실행 후 Instrument Check에서 Connect
uv run python -m app
```

PyInstaller 배포 스펙은 `CE_NR_Radiated.spec`에 있습니다. 빌드 산출물 이름은 `CE_MainBand_Radiation`이며, 배포 폴더에는 `resources`, `config`, `testcases`, `LV Inst Manager`가 함께 포함됩니다.

## 문서

처음 프로젝트를 확인하는 개발자는 아래 순서로 보면 됩니다.

1. [상세 프로젝트 설명서 v1.0.1](docs/PROJECT_SPEC_1.0.1.md)
2. [아키텍처 개요](docs/ARCHITECTURE.md)
3. [프로젝트 작업 지침](AGENTS.md)
4. `src/app/__main__.py`
5. `src/app/ui/main_window.py`
6. `src/app/core/runner.py`
7. `src/app/core/fsm/engine.py`

영역별 심화 문서 (코드 수준 상세):

- [docs/FSM.md](docs/FSM.md) — 통합 세션 FSM 전이 규칙, 엔진 동작, 측정 시퀀스, 주의점
- [docs/PROTOCOL.md](docs/PROTOCOL.md) — LabVIEW TCP/JSON 명령 카탈로그, 단위 규약, mock 사용법
- [docs/DOMAIN_MODELS.md](docs/DOMAIN_MODELS.md) — Range/Band 그룹/lookup 테이블 수치와 확장 체크리스트
- [docs/REPORTING.md](docs/REPORTING.md) — Excel 셀 매핑 규칙, 라이브 모니터링, 스크린샷 규칙
- [docs/UI_GUIDE.md](docs/UI_GUIDE.md) — 패널 구성, 시그널 결선, 실행 중 잠금 정책

## 주요 경로

| 경로 | 역할 |
| --- | --- |
| `src/app/models` | NR Band, TestCase, Range, RB/channel lookup 등 순수 도메인 모델 |
| `src/app/core` | CSV loader/validator, Runner, 장비 연결/TDF 서비스 |
| `src/app/core/fsm` | 측정 세션 FSM 엔진과 상태 구현 |
| `src/app/net` | TCP client, frame protocol, LabVIEW command facade, mock server/client |
| `src/app/report` | Excel writer, report facade, screenshot 저장 규칙 |
| `src/app/ui` | PySide6 메인 윈도우와 패널 |
| `resources` | Qt Designer `.ui`, 앱 아이콘, RF Switch Box 이미지 |
| `config` | 설정 예시 파일 |
| `testcases` | 샘플 Test Case CSV |
| `tests` | models/core/net/report/ui 테스트 |

## 개발 원칙 요약

- 의존 방향은 `ui -> core -> (net | report)`를 유지합니다.
- `net`과 `report`는 `ui`에 의존하지 않습니다.
- 장비 설정/측정/상태 확인은 LabVIEW TCP/JSON 명령으로만 수행합니다.
- Python에서 허용되는 VISA 사용은 UI 입력 편의를 위한 `ResourceManager().list_resources()` 조회뿐입니다.
- `src/app/ui/generated/**`는 직접 수정하지 않고, `.ui` 변경 후 `pyside6-uic`로 재생성합니다.
- Bilog 측정은 현장 확인 기준으로 In-band와 동일한 LV 프로토콜(`FSV40 / Mark Inband`)을 사용합니다.
