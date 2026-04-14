---
name: pyside-widget
description: Use when adding a new PySide6 widget, dialog, or main window to this project. Standardizes the .ui → *_ui.py → logic class split so generated files stay untouched. Trigger when the user asks to add/create a new screen, dialog, panel, or window.
---

# PySide6 Widget 추가 표준 절차

이 프로젝트는 `.ui`(Qt Designer) → `pyside6-uic`로 생성한 `*_ui.py` → 로직을 담는 상속 클래스, **3단 분리 구조**를 따른다. 생성 파일(`*_ui.py`)은 절대 직접 수정하지 않는다.

## 디렉터리 규약

```
resources/<name>.ui                     # Qt Designer 소스
src/app/ui/generated/<name>_ui.py       # pyside6-uic 산출물 (수정 금지)
src/app/ui/<name>.py                    # 로직 클래스 (Ui_*를 상속)
```

## 절차

### 1) `.ui` 파일 생성
`resources/<name>.ui`를 Qt Designer로 만들거나, 간단한 경우 직접 XML을 작성한다. 루트 objectName은 `PascalCase`(예: `MainWindow`, `TestCaseEditorDialog`).

### 2) UI 컴파일
```bash
uv run pyside6-uic resources/<name>.ui -o src/app/ui/generated/<name>_ui.py
```
`src/app/ui/generated/__init__.py`가 없다면 빈 파일로 생성한다.

### 3) 로직 클래스 작성
`src/app/ui/<name>.py`:

```python
from PySide6.QtWidgets import QMainWindow  # 또는 QDialog, QWidget
from PySide6.QtCore import Slot

from app.ui.generated.<name>_ui import Ui_<RootObjectName>


class <ClassName>(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ui = Ui_<RootObjectName>()
        self._ui.setupUi(self)
        self._connect_signals()

    def _connect_signals(self) -> None:
        self._ui.runButton.clicked.connect(self.on_run_clicked)

    @Slot()
    def on_run_clicked(self) -> None:
        ...
```

핵심 규칙:
- 생성된 `Ui_*` 클래스는 **인스턴스 속성** `self._ui`로 보유 (다중 상속 대신 컴포지션).
- 슬롯은 `on_<widget>_<signal>` 패턴, `@Slot()` 데코레이터로 명시.
- 위젯에서 **core/net 로직을 직접 호출하지 말고** 컨트롤러/서비스 객체를 주입받아 호출.

### 4) 엔트리/라우팅에 등록
`src/app/__main__.py` 또는 상위 윈도우에서 생성·표시.

### 5) 검증
- `uv run python -m app` 실행 후 새 화면이 뜨는지 확인.
- 가능한 경우 `pytest-qt` 로 버튼 클릭 → 시그널 방출 테스트 추가.

## 체크리스트

- [ ] `resources/<name>.ui` 생성됨
- [ ] `pyside6-uic`로 컴파일, `src/app/ui/generated/<name>_ui.py` 생성 (직접 편집 안 함)
- [ ] `src/app/ui/<name>.py`에 로직 클래스 작성, `Ui_*`는 컴포지션으로 보유
- [ ] 시그널/슬롯 연결은 `_connect_signals()`에 몰아서 관리
- [ ] core/net 의존성은 생성자에서 주입받음 (UI 안에서 직접 생성 금지)
- [ ] 이벤트 루프를 막는 호출 없음 (무거운 작업은 QThread/QtAsyncio)
