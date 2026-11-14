"""아이템 필터 섹션: 검색 조건 탭 관리 + 편집기."""
from __future__ import annotations

import os

from PySide6.QtCore import QPoint, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMenu, QVBoxLayout, QWidget

from dialogs import confirm, info
from editor import ProfileEditor
from storage import APP_DIR, Store, clone_tab, new_tab
from titlebar import TabStrip


class FilterPage(QWidget):
    def __init__(self, db, flash, parent=None):
        super().__init__(parent)
        self.db = db
        self.flash = flash
        self.store = Store(db)
        self.state = self.store.load()
        self.state.pop("window", None)
        self.tabs_data: list[dict] = self.state["tabs"]

        self.strip = TabStrip("새 검색 조건 탭 (Ctrl+T)")
        self.editor = ProfileEditor(db)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.editor)

        tb = self.strip.tabs
        for t in self.tabs_data:
            self.strip.add_tab(t["name"])
        tb.currentChanged.connect(self._on_tab_changed)
        tb.tabMoved.connect(self._on_tab_moved)
        tb.tabBarDoubleClicked.connect(lambda i: i >= 0 and self.editor.focus_name())
        tb.customContextMenuRequested.connect(self._tab_context_menu)
        self.strip.addRequested.connect(self.add_tab)
        self.strip.closeTabRequested.connect(self.delete_tab)

        self._save_timer = QTimer(self, singleShot=True, interval=400, timeout=self.save_now)
        self.editor.changed.connect(self._on_editor_changed)
        self.editor.duplicateRequested.connect(lambda: self.duplicate_tab(tb.currentIndex()))
        self.editor.deleteRequested.connect(lambda: self.delete_tab(tb.currentIndex()))

        cur = self.state.get("current", 0)
        tb.setCurrentIndex(cur)
        self._on_tab_changed(cur)

    # ---------- 탭 ----------
    def _on_tab_changed(self, i: int) -> None:
        if 0 <= i < len(self.tabs_data):
            self.state["current"] = i
            self.editor.set_profile(self.tabs_data[i])
            self._save_timer.start()

    def _on_tab_moved(self, frm: int, to: int) -> None:
        self.tabs_data.insert(to, self.tabs_data.pop(frm))
        self.state["current"] = self.strip.tabs.currentIndex()
        self._save_timer.start()

    def _insert_tab(self, tab: dict, index: int) -> None:
        self.tabs_data.insert(index, tab)
        self.strip.add_tab(tab["name"], index)
        self.strip.tabs.setTabToolTip(index, self.db.slot_name(tab["slot"]))
        self.strip.tabs.setCurrentIndex(index)
        self._on_tab_changed(index)

    def add_tab(self) -> None:
        cur = self.strip.tabs.currentIndex()
        slot = self.tabs_data[cur]["slot"] if 0 <= cur < len(self.tabs_data) else self.db.slots[0]["id"]
        self._insert_tab(new_tab(self.db.slot_name(slot), slot), len(self.tabs_data))
        self.editor.focus_name()
        self.flash("새 탭을 만들었습니다")

    def duplicate_tab(self, i: int) -> None:
        if not 0 <= i < len(self.tabs_data):
            return
        self._insert_tab(clone_tab(self.tabs_data[i]), i + 1)
        self.flash(f"'{self.tabs_data[i]['name']}' 탭을 복제했습니다")

    def delete_tab(self, i: int) -> None:
        if not 0 <= i < len(self.tabs_data):
            return
        t = self.tabs_data[i]
        if t["options"] and not confirm(
            self, "탭 삭제", f"'{t['name']}' 탭과 옵션 {len(t['options'])}개를 삭제할까요?", "삭제", danger=True
        ):
            return
        tb = self.strip.tabs
        tb.blockSignals(True)
        self.tabs_data.pop(i)
        tb.removeTab(i)
        if not self.tabs_data:
            self.tabs_data.append(new_tab(self.db.slot_name(t["slot"]), t["slot"]))
            self.strip.add_tab(self.tabs_data[0]["name"])
        tb.blockSignals(False)
        idx = min(i, len(self.tabs_data) - 1)
        tb.setCurrentIndex(idx)
        self._on_tab_changed(idx)
        self.flash(f"'{t['name']}' 탭을 삭제했습니다")

    def _tab_context_menu(self, pos: QPoint) -> None:
        tb = self.strip.tabs
        i = tb.tabAt(pos)
        if i < 0:
            return
        tb.setCurrentIndex(i)
        m = QMenu(self)
        m.addAction("이름 변경", self.editor.focus_name)
        m.addAction("탭 복제", lambda: self.duplicate_tab(i))
        m.addAction("이 탭 내보내기…", lambda: self.export_tabs([self.tabs_data[i]]))
        m.addSeparator()
        m.addAction("탭 삭제", lambda: self.delete_tab(i))
        m.exec(tb.mapToGlobal(pos))

    def _on_editor_changed(self) -> None:
        i = self.strip.tabs.currentIndex()
        if 0 <= i < len(self.tabs_data):
            self.strip.tabs.setTabText(i, self.tabs_data[i]["name"])
            self.strip.tabs.setTabToolTip(i, self.db.slot_name(self.tabs_data[i]["slot"]))
        self._save_timer.start()

    # ---------- 메뉴 ----------
    def fill_menu(self, m: QMenu) -> None:
        m.addAction("새 탭\tCtrl+T", self.add_tab)
        m.addAction("현재 탭 복제\tCtrl+Shift+D", lambda: self.duplicate_tab(self.strip.tabs.currentIndex()))
        m.addSeparator()
        m.addAction("프리셋 불러오기…", self.import_tabs)
        m.addAction("전체 탭 내보내기…", lambda: self.export_tabs(self.tabs_data))
        m.addAction("현재 탭 내보내기…", lambda: self.export_tabs([self.tabs_data[self.strip.tabs.currentIndex()]]))
        m.addSeparator()
        m.addAction("저장 폴더 열기", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(APP_DIR))))

    def export_tabs(self, tabs: list[dict]) -> None:
        default = "exile_delta_preset.json" if len(tabs) > 1 else f"{tabs[0]['name']}.json"
        path, _ = QFileDialog.getSaveFileName(self, "프리셋 내보내기", str(APP_DIR / default), "Exile Delta 프리셋 (*.json)")
        if not path:
            return
        try:
            self.store.export_tabs(path, tabs)
            self.flash(f"{len(tabs)}개 탭을 내보냈습니다 → {os.path.basename(path)}")
        except OSError as e:
            info(self, "내보내기 실패", str(e))

    def import_tabs(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "프리셋 불러오기", str(APP_DIR), "Exile Delta 프리셋 (*.json)")
        if not path:
            return
        try:
            tabs = self.store.import_tabs(path)
        except (OSError, ValueError) as e:
            info(self, "불러오기 실패", f"파일을 읽을 수 없습니다.\n{e}")
            return
        if not tabs:
            info(self, "불러오기", "불러올 수 있는 탭이 없습니다.")
            return
        for t in tabs:
            self._insert_tab(t, len(self.tabs_data))
        self.flash(f"{len(tabs)}개 탭을 불러왔습니다")

    # ---------- 저장 ----------
    def save_now(self) -> None:
        try:
            self.store.save(self.state)
            self.flash("자동 저장됨")
        except OSError as e:
            self.flash(f"저장 실패: {e}")
