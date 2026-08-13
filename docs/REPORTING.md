# 리포트 계층 (Excel + 스크린샷) — 심화

> 개요는 [PROJECT_SPEC_1.0.1.md](PROJECT_SPEC_1.0.1.md) §15 참조.
> 이 문서는 셀 좌표 규칙·COM 라이브 모니터링·파일명 규칙을 다루는 심화 문서다.

[src/app/report/](../src/app/report/)는 FSM 측정 결과를 Excel 파일과 스크린샷 폴더 구조로
영속화한다. 결과는 배치가 아니라 **측정 직후 즉시(per-write) 기록·저장**된다.

## 1. 구성

| 모듈 | 역할 |
| --- | --- |
| [report_writer.py](../src/app/report/report_writer.py) `ReportWriter` | FSM이 호출하는 단일 facade — Excel 기록 + 스크린샷 finalize를 묶음 |
| [excel_writer.py](../src/app/report/excel_writer.py) `ExcelReportWriter` | openpyxl + win32com(COM) 이중 경로로 셀 기록·저장 |
| [template_map.py](../src/app/report/template_map.py) | "어느 시트의 어느 셀에 쓸지" — **코드 상수** (JSON 아님) |
| [screenshot_store.py](../src/app/report/screenshot_store.py) | 스크린샷 최종 파일명/디렉터리 규칙과 복사 |

`config/excel_template_map.example.json`은 어떤 코드도 읽지 않는 레거시 자리표시자다.
셀 좌표를 바꾸려면 template_map.py 코드를 수정해야 한다.

생성 경로: `Runner.start()`가 `report_writer_factory`로 `ExcelReportWriter(template_path)` +
`ReportWriter(excel_writer, screenshot_root_dir, model_name=EUT이름, events)`를 조립하고
`prepare_for_run(첫 TC)`를 호출한 뒤 `ctx.report_writer`로 FSM에 전달한다.

## 2. Excel 기록 규칙 — template_map.py

- **출력 파일 = 템플릿 파일**: 별도 산출물 없이 사용자가 고른 `.xlsx`에 in-place 저장한다.
  원본 템플릿을 보존하려면 복사본을 지정해야 한다.
- **시트**: Band당 1장, 시트명 `Sub6 {band}` (예: `Sub6 n78`). NRBand enum에서 자동 파생
  — 새 band를 추가하면 템플릿에 해당 시트만 준비하면 된다.
- **레이아웃 2종**: `default`(mhb/uhb)와 `lb`. band group key로 선택한다.

| 항목 | default | lb |
| --- | --- | --- |
| band info 셀 (Band/channel/BW/RB size/RB offset/Mod/SCS/Ant position) | A49, C49~I49 | A44, C44~I44 |
| fundamental 주파수 셀 | J49 | J44 |
| harmonic base row | 66 | 56 |
| inband base row | 61 | 51 |
| bilog base row | 56 | **None (LB는 Bilog 미지원 — write_bilog 시 ValueError)** |

- **NSA는 별도 시트가 아니라 행 오프셋**: `Generation.NR_NSA`면 전체 행을 위로 이동
  (default −42행, lb −37행) — 같은 시트의 위쪽 블록에 기록된다.
- **셀 좌표 계산**: DUT축이 열(X→B, Y→C, Z→D), 편파가 행 오프셋(V→+0, H→+1),
  하모닉 차수가 행 오프셋(2차+0, 3차+2, 4차+4, 5차+6).
  예: default SA, 3차, Z축, H편파 → `D69`. 하모닉 주파수(기본파×차수)는 A열 고정.
- band info 8셀은 "시트+레이아웃키당 1회"만 기록된다(인스턴스 내 가드 —
  Runner 재시작 시 새 인스턴스가 다시 덮어씀).
- Band/SCS는 다른 band info와 함께 최초 결과 작성 시 기록된다. NR은 SA default
  `A49/H49`, SA LB `A44/H44`, NSA `A7/H7`을 사용하고, LTE는 `A7/G7`을 사용한다.
  NR B열 Anchor Band는 기록하지 않는다.
- peak level이 None(=limit−10dB 미만)이면 셀에 문자열 **"-"** 가 들어간다.

## 3. 저장 경로와 라이브 모니터링 — excel_writer.py

`_save()`의 동작:

1. **라이브 모니터링 모드** (기본 — `prepare_for_run` 성공 시): openpyxl 저장은 건너뛰고
   **COM으로 실제 실행 중인 Excel 창**에 기록한다. 열린 워크북을 ROT(Running Object
   Table)/활성 Excel에서 찾고, 없으면 새 Excel(Visible)로 파일을 연다. 대기 중이던
   `_pending_cells`를 순서대로 쓰고 **마지막 기록 셀을 Select**해 오퍼레이터가 진행 상황을
   실시간으로 보게 한 뒤 `workbook.Save()`. 사용자가 실행 중 Excel을 닫으면 재오픈한다.
2. **비모니터링 모드**: `openpyxl workbook.save(template_path)`. 파일이 Excel에서 열려
   `PermissionError`가 나면 COM 폴백을 시도한다.

`prepare_live_monitoring`은 pywin32가 필요하며, **실패하면 시험 시작 자체가 거부된다**
("시험 시작 실패: Excel report 준비 실패"). 즉 현재 구조상 Windows + Excel 설치가 실행
전제다.

`read_fundamental_frequency`는 FSM이 같은 band 재측정 시 기본파를 재지 않기 위한 캐시
조회다 — init 시점에 로드한 **openpyxl 인메모리 워크북**을 읽으므로, 라이브 모드에서
사용자가 Excel 창에서 손으로 고친 값은 보이지 않는다.

## 4. 기록 순서 — report_writer.py

| 메서드 | 순서 |
| --- | --- |
| `write_fundamental` | Excel 기록 → 성공 시 스크린샷 finalize |
| `write_inband` / `write_bilog` | Excel 기록 → 성공 시 스크린샷 finalize |
| `write_harmonic` | **스크린샷 finalize 먼저 → Excel 기록** (비대칭 — Excel 실패해도 스크린샷은 이미 저장됨) |

모든 `write_*`는 `result.screenshot_path`가 필수이며 원본 파일이 없으면 실패한다.
FSM 쪽 호출은 [reporting.py](../src/app/core/fsm/states/measurement/reporting.py)의
`append_and_write_report()` 단일 관문을 거친다 — writer 미설정/예외/False 반환을 모두
`StateResult.FAIL` + 에러 시그널로 수렴시킨다.

Harmonic **정밀측정 스크린샷은 예외**: ReportWriter를 거치지 않고 FSM 상태가
`finalize_harmonic_precision_screenshot`을 직접 호출하며 Excel에는 아무것도 쓰지 않는다.

## 5. 스크린샷 저장 규칙 — screenshot_store.py

디렉터리 구조 (root = `TestRunSettings.screenshot_root_dir`):

```text
{root}/{model}/Traffic/5G/{band}/{Upper|Lower}/{SA|NSA}/{파일명}.png
```

파일명 3종:

| 종류 | 패턴 | 예 |
| --- | --- | --- |
| 일반(Range 스윕) | `{model}_Traffic_5G_{SA\|NSA}_{band}_{antpos}_{target주파수 .3f}MHz_{range시작}_{range끝}_{축}{편파}.png` | `SM-000_Traffic_5G_SA_n5_LOWER_836.500MHz_30MHz_1GHz_XH.png` |
| Harmonic 정밀 | 위 + `_{sweep_time_ms}ms` | `..._7099.980MHz_XV_100ms.png` |
| 기본파 | `..._{target주파수 .3f}MHz_Fundamental Frequency.png` | |

- Range 시작/끝은 1000MHz 이상이면 GHz 단위로 표기 (예: `1GHz_12.75GHz`).
- 파일명 충돌 시 `이름(1).png`, `이름(2).png`로 순번 회피 — 같은 조건 재측정 시 파일이
  계속 늘어난다.
- finalize는 temp 원본을 `copy2`로 **복사만** 하고 원본은 지우지 않는다.
- 저장 성공 시 `screenshot_saved(str)` 시그널 emit → Test Plot 패널과 Test Manager
  미리보기가 갱신된다.
- 모델명 등은 Windows 금지 문자를 `_`로 치환해 경로에 넣는다.

## 6. 레거시 잔재 (실사용 없음)

- `screenshot_store.ScreenshotStore` 클래스 — bytes 저장 유틸, 사용처 없음.
- `ExcelReportWriter.write()` 배치 API — `NotImplementedError`로 봉인.
- `config/excel_template_map.example.json` — 데드 설정 파일.
- CLAUDE.md 초기 설계의 `template_loader.py`는 존재하지 않는다 — template_map.py가 그 역할.

## 7. 새 시험 타입의 리포트 확장 절차

1. `template_map.py`: `ReportLayout`에 `<type>_base_row` 필드 추가, `LAYOUTS`의
   default/lb 두 항목에 값 정의(미지원이면 None), `offset_layout_rows`에 오프셋 처리,
   `<type>_level_cell()` 좌표 함수 추가.
2. `excel_writer.py`: `write_<type>` 메서드 (write_inband 패턴 — band info 1회 기록 →
   level 셀 → `_save()`).
3. `report_writer.py`: 같은 이름 facade (Excel/스크린샷 순서 결정 포함).
4. 테스트: `tests/report/test_template_map.py` 좌표 목록, `test_report_writer.py` 기록,
   파일명이 바뀌면 `test_screenshot_store.py` 파라미터라이즈.
