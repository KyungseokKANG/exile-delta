"""아이템 만들기 창 (PoB Items 탭의 'Craft item' / 유니크 DB / 아이템 텍스트 편집과 같은 기능).

- 유니크: 그 슬롯에 들어가는 유니크 목록 → 버전(variant)·유동 수치 슬라이더
- 베이스로 만들기: 베이스 종류/베이스/희귀도 → 접두·접미 옵션을 골라 티어·수치 지정 (PoB Craft 와 같은 옵션 목록)
- 텍스트: 게임 Ctrl+C 텍스트(한글/영문) 또는 PoB 아이템 텍스트를 붙여넣어 시작, 지금 장착한 아이템에서 시작
작업 중인 아이템은 PoB 엔진(es_draft_*)이 들고 있고, 바꿀 때마다 '지금 장비 대비' 변화를 다시 계산한다.
"""
from __future__ import annotations

import html
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import ko2en
from overlay import Overlay

DIM = "#968b7a"
RARITY_KO = {"NORMAL": "일반", "MAGIC": "마법", "RARE": "희귀", "UNIQUE": "고유", "RELIC": "유물"}
RARITY_COL = {"UNIQUE": "#d08a4a", "RARE": "#e8d77a", "MAGIC": "#8f9fff", "NORMAL": "#ddd5c6", "RELIC": "#82d68f"}
KIND_KO = {"enchant": "인챈트", "implicit": "implicit", "explicit": ""}
HANGUL = re.compile(r"[가-힣]")


def _nm(en: str) -> str:
    ko = ko2en.name_ko(en)
    return f"{ko}  ({en})" if ko and ko != en else en


class ItemCreator(QWidget):
    def __init__(self, page, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.page = page
        self.client = page.client
        self.slot = ""
        self.slot_label = ""
        self.cid = None
        self.info: dict | None = None
        self.catalog: dict | None = None
        self.busy = 0
        self.edit_mode = False
        self._pending_edit: dict | None = None
        self.setObjectName("CreatorWin")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("#CreatorWin { background: #15120e; } #CreatorWin QLabel { font-size: 10.5pt; }"
                           "#CreatorPanel { background: #1b1712; border: 1px solid #2c251c; border-radius: 8px; }")
        self.resize(1240, 820)

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(12)

        # ---------------- 왼쪽: 어디서 시작할지
        left = QFrame()
        self.left = left
        left.setObjectName("CreatorPanel")
        left.setFixedWidth(400)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(10, 10, 10, 10)
        self.head = QLabel()
        self.head.setObjectName("CardTitle")
        lv.addWidget(self.head)
        self.tabs = QTabWidget()
        lv.addWidget(self.tabs, 1)

        # 유니크
        tu = QWidget()
        uv = QVBoxLayout(tu)
        self.u_search = QLineEdit()
        self.u_search.setPlaceholderText("유니크 검색 (한글/영문)")
        self.u_search.textChanged.connect(self._fill_uniques)
        self.u_list = QListWidget()
        self.u_list.itemClicked.connect(lambda it: self._new({"from": "unique", "name": it.data(Qt.ItemDataRole.UserRole)}))
        uv.addWidget(self.u_search)
        uv.addWidget(self.u_list, 1)
        self.tabs.addTab(tu, "유니크")

        # 베이스로 만들기
        tb = QWidget()
        bv = QVBoxLayout(tb)
        r1 = QHBoxLayout()
        self.b_rarity = QComboBox()
        for k, v in (("RARE", "희귀"), ("MAGIC", "마법"), ("NORMAL", "일반")):
            self.b_rarity.addItem(v, k)
        self.b_title = QLineEdit()
        self.b_title.setPlaceholderText("아이템 이름 (희귀)")
        r1.addWidget(self.b_rarity)
        r1.addWidget(self.b_title, 1)
        bv.addLayout(r1)
        self.b_type = QComboBox()
        self.b_type.currentIndexChanged.connect(self._fill_bases)
        bv.addWidget(self.b_type)
        self.b_search = QLineEdit()
        self.b_search.setPlaceholderText("베이스 검색")
        self.b_search.textChanged.connect(self._fill_bases)
        bv.addWidget(self.b_search)
        self.b_list = QListWidget()
        self.b_list.itemDoubleClicked.connect(lambda _it: self._new_base())
        bv.addWidget(self.b_list, 1)
        bb = QPushButton("이 베이스로 시작")
        bb.setObjectName("Primary")
        bb.clicked.connect(self._new_base)
        bv.addWidget(bb)
        self.tabs.addTab(tb, "베이스로 만들기")

        # 레어 템플릿 (PoB rare DB)
        tr = QWidget()
        rv = QVBoxLayout(tr)
        rl = QLabel("PoB 에 들어 있는 레어 예시 아이템 (옵션을 골라 바꿀 수 있음)")
        rl.setStyleSheet(f"color: {DIM};")
        rl.setWordWrap(True)
        rv.addWidget(rl)
        self.r_list = QListWidget()
        self.r_list.itemClicked.connect(lambda it: self._new({"from": "rare", "name": it.data(Qt.ItemDataRole.UserRole)}))
        rv.addWidget(self.r_list, 1)
        self.tabs.addTab(tr, "레어 예시")

        # 텍스트
        tt = QWidget()
        tv = QVBoxLayout(tt)
        cur = QPushButton("지금 장착한 아이템에서 시작")
        cur.clicked.connect(lambda: self._new({"from": "equipped"}))
        tv.addWidget(cur)
        hl = QLabel("게임에서 Ctrl+C 한 아이템 텍스트(한글/영문) 또는 PoB 아이템 텍스트를 붙여넣으세요.")
        hl.setWordWrap(True)
        hl.setStyleSheet(f"color: {DIM};")
        tv.addWidget(hl)
        self.t_edit = QPlainTextEdit()
        tv.addWidget(self.t_edit, 1)
        tl = QPushButton("이 텍스트로 시작")
        tl.setObjectName("Primary")
        tl.clicked.connect(self._new_text)
        tv.addWidget(tl)
        self.tabs.addTab(tt, "텍스트")
        root.addWidget(left)

        # ---------------- 오른쪽: 편집 + 결과
        right = QVBoxLayout()
        right.setSpacing(10)
        ed = QFrame()
        ed.setObjectName("CreatorPanel")
        ev = QVBoxLayout(ed)
        ev.setContentsMargins(12, 10, 12, 10)
        self.title = QLabel("왼쪽에서 유니크 / 베이스 / 텍스트를 골라 시작하세요")
        self.title.setTextFormat(Qt.TextFormat.RichText)
        self.title.setWordWrap(True)
        ev.addWidget(self.title)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body_l = QVBoxLayout(self.body)
        self.body_l.setContentsMargins(0, 0, 6, 0)
        self.body_l.setSpacing(8)
        self.scroll.setWidget(self.body)
        ev.addWidget(self.scroll, 1)
        right.addWidget(ed, 3)

        res = QFrame()
        res.setObjectName("CreatorPanel")
        resv = QVBoxLayout(res)
        resv.setContentsMargins(12, 10, 12, 10)
        self.res_title = QLabel()
        self.res_title.setTextFormat(Qt.TextFormat.RichText)
        resv.addWidget(self.res_title)
        self.result = QLabel()
        self.result.setTextFormat(Qt.TextFormat.RichText)
        self.result.setWordWrap(True)
        resv.addWidget(self.result)
        btns = QHBoxLayout()
        self.status = QLabel()
        self.status.setStyleSheet(f"color: {DIM};")
        btns.addWidget(self.status, 1)
        self.reset_btn = QPushButton("원래대로")
        self.reset_btn.setToolTip("지금 장착한 아이템 상태로 되돌립니다 (아직 적용 안 한 변경 취소)")
        self.reset_btn.clicked.connect(lambda: self._new({"from": "equipped"}))
        btns.addWidget(self.reset_btn)
        self.equip_btn = QPushButton("이 슬롯에 장착")
        self.equip_btn.setObjectName("Primary")
        self.equip_btn.clicked.connect(self._equip)
        btns.addWidget(self.equip_btn)
        close = QPushButton("닫기")
        close.clicked.connect(self.close)
        btns.addWidget(close)
        resv.addLayout(btns)
        right.addWidget(res, 0)
        root.addLayout(right, 1)

        self._range_timer = QTimer(self, singleShot=True, interval=140, timeout=self._flush_edit)
        self.range_labels: dict[tuple, QLabel] = {}
        self.row_state: dict[tuple, tuple] = {}  # (kind, idx) -> (묶음 key, modId, range) 줄마다 고른 옵션
        self.row_lines: dict[tuple, int] = {}

    # ================================================================ 열기
    def open_for(self, slot: str, label: str, edit: bool = False) -> None:
        """edit=True: 지금 장착한 아이템의 옵션만 고치는 창 (목록 고르기 없이). False: 새 아이템 만들기."""
        c = self.page._cur()
        if c is None:
            return
        self.slot, self.slot_label, self.cid = slot, label, c["id"]
        self.edit_mode = edit
        self.left.setVisible(not edit)
        self.reset_btn.setVisible(edit)
        self.equip_btn.setText("변경 적용" if edit else "이 슬롯에 장착")
        self.resize(900 if edit else 1240, self.height())
        self.setWindowTitle(f"{'옵션 변경' if edit else '아이템 만들기'} — {label} · {c['name']}")
        self.head.setText(f"{label} 에 넣을 아이템")
        self.res_title.setText(f"<span style='color:#c8a96a; font-weight:bold'>장착 시 변화</span>"
                               f" <span style='color:{DIM}'>· {html.escape(label)} · 지금 장비 대비</span>")
        self.info = None
        self._clear_body()
        self.title.setText("왼쪽에서 유니크 / 베이스 / 텍스트를 골라 시작하세요")
        self.result.setText("")
        self.equip_btn.setEnabled(False)
        self.u_list.clear()
        self.r_list.clear()
        self.b_type.clear()
        self.b_list.clear()
        self.page._ensure_loaded()
        if edit:
            self.status.setText("불러오는 중…")
            self._new({"from": "equipped"})
        else:
            self.status.setText("목록 불러오는 중…")
            self.client.call("item_catalog", {"slot": slot}, self._got_catalog, self._err)
        self.show()
        self.raise_()
        self.activateWindow()

    def open_draft(self, slot: str, label: str, draft: dict) -> None:
        """만들어 둔 아이템(베타 최적화 결과)에서 시작: 옵션 체크 해제·교체 후 장착."""
        c = self.page._cur()
        if c is None:
            return
        self.slot, self.slot_label, self.cid = slot, label, c["id"]
        self.edit_mode = False
        self.left.setVisible(False)
        self.reset_btn.setVisible(False)
        self.equip_btn.setText("이 슬롯에 장착")
        self.resize(980, self.height())
        self.setWindowTitle(f"옵션 조정 — {label} · {c['name']}")
        self.res_title.setText(f"<span style='color:#c8a96a; font-weight:bold'>장착 시 변화</span>"
                               f" <span style='color:{DIM}'>· {html.escape(label)} · 지금 장비 대비</span>")
        self.info = None
        self._clear_body()
        self.result.setText("")
        self.status.setText("불러오는 중…")
        # 엔진의 작업 아이템이 그사이 바뀌었을 수 있으니 텍스트로 다시 만든다 (Crafted 접두·접미 그대로 복원됨)
        self._new({"from": "text", "raw": draft.get("raw") or ""})
        self.show()
        self.raise_()
        self.activateWindow()

    def _got_catalog(self, r: dict) -> None:
        self.catalog = r
        self.status.setText("")
        self._fill_uniques()
        self.r_list.clear()
        for x in r.get("rares") or []:
            it = QListWidgetItem(f"{x['name']}  ·  {_nm(x['base'])}")
            it.setData(Qt.ItemDataRole.UserRole, x["name"])
            self.r_list.addItem(it)
        self.tabs.setTabEnabled(2, bool(r.get("rares")))
        self.b_type.blockSignals(True)
        self.b_type.clear()
        for bt in r.get("baseTypes") or []:
            self.b_type.addItem(bt["type"], bt["type"])
        self.b_type.blockSignals(False)
        self._fill_bases()

    def _fill_uniques(self) -> None:
        q = self.u_search.text().strip().lower()
        self.u_list.clear()
        for x in (self.catalog or {}).get("uniques") or []:
            title = x["name"].split(", ")[0]  # PoB 유니크 DB 이름은 "이름, 베이스"
            label = f"{_nm(title)}  ·  {ko2en.name_ko(x['base']) or x['base']}"
            if q and q not in label.lower():
                continue
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, x["name"])
            it.setForeground(Qt.GlobalColor.white)
            self.u_list.addItem(it)

    def _fill_bases(self) -> None:
        self.b_list.clear()
        t = self.b_type.currentData()
        q = self.b_search.text().strip().lower()
        for bt in (self.catalog or {}).get("baseTypes") or []:
            if bt["type"] != t:
                continue
            for b in bt["bases"]:
                label = f"{_nm(b['name'])}   Lv {b.get('level') or 0}"
                if q and q not in label.lower():
                    continue
                it = QListWidgetItem(label)
                it.setData(Qt.ItemDataRole.UserRole, b["name"])
                if b.get("implicit"):
                    it.setToolTip(ko2en.mod_ko(b["implicit"].replace("\n", " / ")))
                self.b_list.addItem(it)

    # ================================================================ 시작
    def _new_base(self) -> None:
        it = self.b_list.currentItem()
        if it is None:
            self.status.setText("베이스를 고르세요")
            return
        self._new({"from": "base", "base": it.data(Qt.ItemDataRole.UserRole),
                   "rarity": self.b_rarity.currentData(), "title": self.b_title.text().strip()})

    def _new_text(self) -> None:
        text = self.t_edit.toPlainText().strip()
        if not text:
            return
        if HANGUL.search(text):
            res = ko2en.translate_item(text)
            text = res.text
            if res.untranslated:
                self.status.setText(f"영문으로 못 바꾼 줄 {len(res.untranslated)}개는 빠집니다")
        self._new({"from": "text", "raw": text})

    def _new(self, spec: dict) -> None:
        spec = dict(spec, slot=self.slot)
        self.row_state.clear()
        self.row_lines.clear()
        self.status.setText("만드는 중…")
        self.page._ensure_loaded()
        self.client.call("draft_new", {"spec": spec}, lambda r: self._show(r, rebuild=True), self._err)

    def _err(self, m: str) -> None:
        self.status.setText(f"실패: {m}")

    # ================================================================ 편집
    def _edit(self, spec: dict, rebuild: bool) -> None:
        self.client.call("draft_edit", {"spec": spec}, lambda r: self._show(r, rebuild=rebuild), self._err)

    def _queue_range(self, key: tuple, value: float) -> None:
        self._pending_edit = {"range": {"kind": key[0], "idx": key[1], "value": value}}
        self._range_timer.start()

    def _flush_edit(self) -> None:
        if self._pending_edit:
            spec, self._pending_edit = self._pending_edit, None
            self._edit(spec, rebuild=False)

    def _clear_body(self) -> None:
        while self.body_l.count():
            it = self.body_l.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())
        self.range_labels = {}

    def _clear_layout(self, lay) -> None:
        while lay.count():
            it = lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())

    def _show(self, r: dict, rebuild: bool) -> None:
        if not isinstance(r, dict) or r.get("error"):
            self._err((r or {}).get("error", "?"))
            return
        prev = self.info or {}
        if not rebuild and (r.get("crafted") and prev.get("prefixGroups")):
            r.setdefault("prefixGroups", prev.get("prefixGroups"))
            r.setdefault("suffixGroups", prev.get("suffixGroups"))
        if r.get("prefixGroups") is None and prev.get("prefixGroups") and r.get("base") == prev.get("base"):
            r["prefixGroups"], r["suffixGroups"] = prev.get("prefixGroups"), prev.get("suffixGroups")
        self.info = r
        self.status.setText("")
        col = RARITY_COL.get(r.get("rarity"), "#ddd5c6")
        name = r.get("title") or r.get("name") or ""
        self.title.setText(
            f"<b style='color:{col}; font-size:13pt'>{html.escape(_nm(name) if r.get('rarity') == 'UNIQUE' else name)}</b>"
            f"<br><span style='color:{DIM}'>{RARITY_KO.get(r.get('rarity'), '')} · {html.escape(_nm(r.get('base') or ''))}</span>"
            + self._extra_tags(r))
        if rebuild:
            self._build_body(r)
        else:
            for ln in r.get("lines") or []:
                lab = self.range_labels.get((ln["kind"], ln["idx"]))
                if lab is not None:
                    lab.setText(self._line_text(ln))
            if hasattr(self, "raw_edit"):
                self.raw_edit.setPlainText(r.get("raw") or "")
            if r.get("crafted"):
                self._fill_crafted_lines(r)
        self._render_result(r)

    @staticmethod
    def _extra_tags(r: dict) -> str:
        from beta_panel import CAT_KO, INFL_KO

        out = []
        for x in r.get("influences") or []:
            out.append(f"<span style='color:#b7a3ff'>[{INFL_KO.get(x, x)}]</span>")
        if r.get("catalyst"):
            out.append(f"<span style='color:#6fd0c4'>[{CAT_KO.get(r['catalyst'], r['catalyst'])} 퀄리티 +{r.get('catalystQuality') or 0}%]</span>")
        return (" &nbsp;" + " ".join(out)) if out else ""

    def _sorted_lines(self, lines: list[dict]) -> list[dict]:
        """고정 → 접두 → 접미 순 (같은 묶음 안에서는 원래 순서). 하이브리드 옵션(여러 줄)은 붙여서 ┌ └ 표시."""
        import affix

        rows = affix.ordered(lines, getattr(self, "slot", None))
        ann = getattr(self, "_ann", {})
        for i, (ln, gid, a) in enumerate(rows):
            mark = ""
            if gid:
                first = i == 0 or rows[i - 1][1] != gid
                last = i == len(rows) - 1 or rows[i + 1][1] != gid
                if not (first and last):
                    mark = "┌" if first else "└" if last else "│"
                if not last:
                    a = ""  # 접두/접미 표시는 묶음 마지막 줄에 한 번
            ann[(ln["kind"], ln["idx"])] = (mark, a)
        self._ann = ann
        return [r[0] for r in rows]

    def _line_text(self, ln: dict) -> str:
        from affix import html_badge

        ko = ko2en.passive_ko(ln["line"])
        tag = KIND_KO.get(ln["kind"], "")
        if ln.get("crafted"):
            tag = "제작"
        mark, a = getattr(self, "_ann", {}).get((ln["kind"], ln["idx"]), ("", ""))
        lead = f"<span style='color:#6b5d48'>{mark}</span> " if mark else ""
        en = f"<br><span style='color:#5f574b; font-size:9pt'>{html.escape(ln['line'])}</span>" if ko != ln["line"] else ""
        return (lead + f"<span style='color:{'#b8a8ff' if ln['kind'] != 'explicit' else '#9fb5ff'}'>{html.escape(ko)}</span>"
                + (f" <span style='color:{DIM}; font-size:9pt'>({tag})</span>" if tag else "")
                + (f" &nbsp;{html_badge(a)}" if a else "") + en)

    def _build_body(self, r: dict) -> None:
        self._clear_body()
        top = QHBoxLayout()
        if r.get("variants"):
            top.addWidget(QLabel("버전"))
            vc = QComboBox()
            for i, v in enumerate(r["variants"], start=1):
                vc.addItem(v, i)
            vc.setCurrentIndex(max(0, int(r.get("variant") or 1) - 1))
            vc.activated.connect(lambda i, vc=vc: self._edit({"variant": vc.itemData(i)}, rebuild=True))
            top.addWidget(vc)
        if r.get("quality") is not None:
            top.addWidget(QLabel("퀄리티"))
            q = QSpinBox()
            q.setRange(0, 30)
            q.setValue(int(r.get("quality") or 0))
            q.setSuffix(" %")
            q.editingFinished.connect(lambda q=q: self._edit({"quality": q.value()}, rebuild=False))
            top.addWidget(q)
        top.addStretch(1)
        has_range = any(ln.get("hasRange") and ln.get("active") and not (r.get("crafted") and ln["kind"] == "explicit")
                        for ln in r.get("lines") or [])
        if has_range:
            top.addWidget(QLabel("모든 유동 수치"))
            for txt, v in (("최소", 0.0), ("중간", 0.5), ("최대", 1.0)):
                b = QPushButton(txt)
                b.setStyleSheet("QPushButton { padding: 3px 10px; }")
                b.clicked.connect(lambda _=False, v=v: self._edit({"allRange": v}, rebuild=True))
                top.addWidget(b)
        self.body_l.addLayout(top)

        # 옵션 줄 (유니크·레어 텍스트: 유동 수치 슬라이더 / 제작 아이템: implicit 만, 나머지는 접두·접미 칸에서)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        row = 0
        for ln in self._sorted_lines(r.get("lines") or []):
            if not ln.get("active"):
                continue
            if r.get("crafted") and ln["kind"] == "explicit" and (ln.get("prefix") or ln.get("suffix")):
                continue
            lab = QLabel(self._line_text(ln))
            lab.setTextFormat(Qt.TextFormat.RichText)
            lab.setWordWrap(True)
            self.range_labels[(ln["kind"], ln["idx"])] = lab
            if self._mod_mode(r) and ln["kind"] == "explicit":
                # 일반 아이템: 옵션 목록(검색)에서 다른 옵션으로 바꾸기 + 티어 + 수치
                cell = QVBoxLayout()
                cell.setSpacing(3)
                cell.addWidget(lab)
                cell.addLayout(self._mod_row(r, ln))
                grid.addLayout(cell, row, 0, 1, 2)
            else:
                grid.addWidget(lab, row, 0)
            if self._mod_mode(r) and ln["kind"] == "explicit":
                pass
            elif ln.get("hasRange"):
                sl = QSlider(Qt.Orientation.Horizontal)
                sl.setRange(0, 100)
                sl.setValue(int(round((ln.get("range") if ln.get("range") is not None else 0.5) * 100)))
                sl.setFixedWidth(200)
                sl.setToolTip("유동 수치 (최소 ↔ 최대)")
                sl.valueChanged.connect(lambda v, k=(ln["kind"], ln["idx"]): self._queue_range(k, v / 100))
                grid.addWidget(sl, row, 1)
            else:
                nums = self._number_boxes(ln)
                if nums is not None:
                    grid.addLayout(nums, row, 1)
            x = QPushButton("✕")
            x.setFixedSize(30, 28)
            x.setStyleSheet("QPushButton { padding: 0; font-size: 10pt; color: #c9a08a; } QPushButton:hover { color: #ff9a80; }")
            x.setToolTip("이 옵션 줄 삭제")
            x.clicked.connect(lambda _=False, ln=ln: (self.row_state.clear(), self.row_lines.clear(), self._edit(
                {"line": {"kind": ln["kind"], "idx": ln["idx"], "text": ""}}, rebuild=True)))
            grid.addWidget(x, row, 2)
            row += 1
        grid.setColumnStretch(0, 1)
        self.body_l.addLayout(grid)

        if self._mod_mode(r):
            addm = QHBoxLayout()
            al = QLabel("옵션 추가")
            al.setStyleSheet("color: #c8a96a;")
            addm.addWidget(al)
            cb = self._search_combo(self._mod_entries(r), "옵션 검색 (예: 생명력, 저항, 공격 속도) — 비우면 전체 목록")
            cb.setCurrentIndex(-1)
            addm.addWidget(cb, 1)

            def pick_add(i, cb=cb):
                g = cb.itemData(i)
                if not g:
                    return
                top = g["tiers"][-1]
                self.row_state[("explicit", self._n_explicit(r) + 1)] = (g["key"], top["modId"], 0.5)
                self._edit({"setMod": {"kind": "explicit", "modId": top["modId"], "range": 0.5}}, rebuild=True)

            self._bind_search(cb, pick_add)
            self.body_l.addLayout(addm)

        # 옵션 줄 추가 (한글/영문)
        add = QHBoxLayout()
        self.add_kind = QComboBox()
        for k, v in (("explicit", "일반 옵션"), ("implicit", "implicit"), ("enchant", "인챈트"), ("crafted", "제작 옵션")):
            self.add_kind.addItem(v, k)
        add.addWidget(self.add_kind)
        self.add_text = QLineEdit()
        self.add_text.setPlaceholderText("목록에 없는 옵션은 직접 입력 (예: 최대 생명력 +80 · 영문도 가능) → Enter")
        self.add_text.returnPressed.connect(self._add_line)
        add.addWidget(self.add_text, 1)
        self.body_l.addLayout(add)

        if r.get("crafted"):
            self._build_affixes(r)

        # PoB 텍스트 직접 편집
        raw_box = QFrame()
        rv = QVBoxLayout(raw_box)
        rv.setContentsMargins(0, 6, 0, 0)
        rl = QHBoxLayout()
        t = QLabel("PoB 아이템 텍스트 (직접 고쳐서 적용 가능 — 옵션 줄 추가/삭제 등)")
        t.setStyleSheet(f"color: {DIM};")
        rl.addWidget(t, 1)
        ap = QPushButton("텍스트 적용")
        ap.clicked.connect(lambda: self._edit({"raw": self.raw_edit.toPlainText()}, rebuild=True))
        rl.addWidget(ap)
        rv.addLayout(rl)
        self.raw_edit = QPlainTextEdit(r.get("raw") or "")
        self.raw_edit.setFixedHeight(160)
        self.raw_edit.setStyleSheet("font-family: Consolas, 'Malgun Gothic'; font-size: 9.5pt;")
        rv.addWidget(self.raw_edit)
        self.body_l.addWidget(raw_box)
        self.body_l.addStretch(1)

    # ---------------- 일반 아이템: 줄마다 옵션 목록에서 고르기
    def _mod_mode(self, r: dict) -> bool:
        return (not r.get("crafted") and r.get("rarity") not in ("UNIQUE", "RELIC")
                and bool(r.get("prefixGroups") or r.get("suffixGroups")))

    @staticmethod
    def _n_explicit(r: dict) -> int:
        return sum(1 for ln in r.get("lines") or [] if ln["kind"] == "explicit")

    def _mod_entries(self, r: dict) -> list:
        out = []
        for key, name in (("prefixGroups", "접두"), ("suffixGroups", "접미")):
            for gi, g in enumerate(r.get(key) or []):
                g = dict(g, key=f"{key}:{gi}")
                out.append((f"[{name}] {ko2en.label_ko(g['label'])}", g))
        return out

    def _search_combo(self, entries: list, placeholder: str, current: str | None = None) -> QComboBox:
        from PySide6.QtWidgets import QCompleter

        cb = QComboBox()
        cb.setEditable(True)
        cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        cb.setMaxVisibleItems(18)
        if current is not None:
            cb.addItem(current, None)
        for label, data in entries:
            cb.addItem(label, data)
            cb.setItemData(cb.count() - 1, data["label"], Qt.ItemDataRole.ToolTipRole)
        cb.lineEdit().setPlaceholderText(placeholder)
        comp = QCompleter(cb.model(), cb)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)  # 검색어가 들어간 옵션만
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        comp.setMaxVisibleItems(18)
        cb.setCompleter(comp)
        cb.setMinimumWidth(300)
        return cb

    def _bind_search(self, cb: QComboBox, handler) -> None:
        def from_text(text):
            i = cb.findText(text)
            if i >= 0:
                cb.setCurrentIndex(i)
                handler(i)

        cb.activated.connect(handler)
        cb.completer().activated[str].connect(from_text)

    def _mod_row(self, r: dict, ln: dict) -> QHBoxLayout:
        key = (ln["kind"], ln["idx"])
        entries = self._mod_entries(r)
        h = QHBoxLayout()
        h.setSpacing(6)
        cb = self._search_combo(entries, "옵션 검색 — 비우면 전체", current="(지금 옵션 그대로)")
        h.addWidget(cb, 1)
        tc = QComboBox()
        tc.setMinimumWidth(220)
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(0, 100)
        sl.setFixedWidth(130)
        nums = self._number_boxes(ln)
        nums_w = QWidget()
        if nums is not None:
            nums_w.setLayout(nums)
        h.addWidget(tc)
        h.addWidget(sl)
        h.addWidget(nums_w)
        state = self.row_state.get(key)
        groups = {e[1]["key"]: e[1] for e in entries}

        def show_mode(chosen: bool):
            tc.setVisible(chosen)
            sl.setVisible(chosen)
            nums_w.setVisible(not chosen)

        def fill_tiers(g, keep=None):
            tc.blockSignals(True)
            tc.clear()
            n = len(g["tiers"])
            for ti in range(n - 1, -1, -1):
                t = g["tiers"][ti]
                tc.addItem(f"T{n - ti} · Lv{t['level']} · {ko2en.mod_ko(t['text'])}", t["modId"])
                tc.setItemData(tc.count() - 1, t["text"], Qt.ItemDataRole.ToolTipRole)
            tc.setCurrentIndex(next((k for k in range(tc.count()) if tc.itemData(k) == keep), 0))
            tc.blockSignals(False)

        def send(g):
            mod = tc.currentData()
            rng = sl.value() / 100
            old_n = (g.get("_lines") or 1)
            t = next(x for x in g["tiers"] if x["modId"] == mod)
            new_n = t["text"].count(" / ") + 1
            cur_n = self.row_lines.get(key, 1)
            self.row_state[key] = (g["key"], mod, rng)
            self.row_lines[key] = new_n
            # 줄 수가 바뀌는 옵션(하이브리드)이면 화면을 다시 구성, 아니면 그 자리에서 값만
            self._edit({"setMod": {"kind": ln["kind"], "idx": ln["idx"], "modId": mod, "range": rng}},
                       rebuild=(new_n != cur_n or new_n > 1))

        def on_pick(i):
            g = cb.itemData(i)
            if not g:
                return
            fill_tiers(g)
            if sl.value() == 0 and not self.row_state.get(key):
                sl.setValue(50)
            show_mode(True)
            send(g)

        self._bind_search(cb, on_pick)
        tc.activated.connect(lambda _i: send(groups[self.row_state[key][0]]) if self.row_state.get(key) else None)
        sl.valueChanged.connect(lambda _v: self._affix_timer(
            lambda: send(groups[self.row_state[key][0]]) if self.row_state.get(key) else None))
        if state and state[0] in groups:
            g = groups[state[0]]
            cb.setCurrentIndex(next((k for k in range(cb.count()) if (cb.itemData(k) or {}).get("key") == g["key"]), 0))
            fill_tiers(g, state[1])
            sl.blockSignals(True)
            sl.setValue(int(round(state[2] * 100)))
            sl.blockSignals(False)
            show_mode(True)
        else:
            cb.setCurrentIndex(0)
            show_mode(False)
        return h

    # ---------------- 범위 없는 옵션: 숫자 칸으로 직접 수정
    _NUM = re.compile(r"(\d+(?:\.\d+)?)")

    def _number_boxes(self, ln: dict):
        parts = self._NUM.split(ln["line"])
        if len(parts) < 3:
            return None
        h = QHBoxLayout()
        h.setSpacing(4)
        boxes = []
        for i in range(1, len(parts), 2):
            e = QLineEdit(parts[i])
            e.setFixedWidth(max(46, 12 * len(parts[i]) + 22))
            e.setAlignment(Qt.AlignmentFlag.AlignCenter)
            e.setToolTip("수치 직접 입력 → Enter")
            boxes.append((i, e))
            h.addWidget(e)

        def send():
            new = list(parts)
            for i, e in boxes:
                v = e.text().strip()
                if not re.fullmatch(r"\d+(?:\.\d+)?", v):
                    return
                new[i] = v
            text = "".join(new)
            if text != ln["line"]:
                ln["line"] = text
                parts[:] = self._NUM.split(text)
                self._edit({"line": {"kind": ln["kind"], "idx": ln["idx"], "text": text}}, rebuild=False)

        for _, e in boxes:
            e.editingFinished.connect(send)
        h.addStretch(1)
        return h

    def _add_line(self) -> None:
        text = self.add_text.text().strip()
        if not text:
            return
        if HANGUL.search(text):
            en = ko2en.translate_mod(re.sub(r"\s+", " ", text))
            if not en:
                self.status.setText("영문으로 바꾸지 못한 문장입니다 — 게임 표기 그대로 입력하거나 영문으로 입력해 주세요")
                return
            text = en
        kind = self.add_kind.currentData()
        spec = {"addLine": {"kind": "explicit" if kind == "crafted" else kind, "text": text, "crafted": kind == "crafted"}}
        self.add_text.clear()
        self._edit(spec, rebuild=True)

    # ---------------- 접두 / 접미
    def _build_affixes(self, r: dict) -> None:
        box = QFrame()
        bv = QVBoxLayout(box)
        bv.setContentsMargins(0, 4, 0, 0)
        bv.setSpacing(6)
        head = QLabel("옵션 (PoB 와 같은 접두 · 접미 목록 — 옵션 → 티어 → 수치)")
        head.setObjectName("ConfigSub")
        bv.addWidget(head)
        self.affix_rows = []
        for table, groups_key, limit_key, name in (("prefixes", "prefixGroups", "prefixLimit", "접두"),
                                                   ("suffixes", "suffixGroups", "suffixLimit", "접미")):
            groups = r.get(groups_key) or []
            for i in range(int(r.get(limit_key) or 0)):
                cur = ((r.get(table) or [])[i] if i < len(r.get(table) or []) else {}) or {}
                self.affix_rows.append(self._affix_row(bv, table, i + 1, name, groups, cur))
        self.crafted_lines = QLabel()
        self.crafted_lines.setTextFormat(Qt.TextFormat.RichText)
        self.crafted_lines.setWordWrap(True)
        bv.addWidget(self.crafted_lines)
        self.body_l.addWidget(box)
        self._fill_crafted_lines(r)
        self._update_used()

    def _affix_row(self, lay, table, index, name, groups, cur):
        h = QHBoxLayout()
        from PySide6.QtWidgets import QCheckBox

        chk = QCheckBox()
        chk.setToolTip("체크 해제 = 이 옵션 빼고 계산 (다시 체크하면 되돌림)")
        h.addWidget(chk)
        lab = QLabel(f"{name} {index}")
        lab.setFixedWidth(52)
        lab.setStyleSheet("color: #c8a96a;")
        h.addWidget(lab)
        gc = QComboBox()
        gc.addItem("(없음)", -1)
        sel_g, sel_t = -1, -1
        for gi, g in enumerate(groups):
            gc.addItem(ko2en.label_ko(g["label"]), gi)
            gc.setItemData(gc.count() - 1, g["label"], Qt.ItemDataRole.ToolTipRole)
            for ti, t in enumerate(g["tiers"]):
                if t["modId"] == cur.get("modId"):
                    sel_g, sel_t = gi, ti
        gc.setCurrentIndex(sel_g + 1)
        gc.setMinimumWidth(320)
        tc = QComboBox()
        tc.setMinimumWidth(230)
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(0, 100)
        sl.setFixedWidth(130)
        sl.setValue(int(round((cur.get("range") if cur.get("range") is not None else 0.5) * 100)))
        rowd = {"table": table, "index": index, "groups": groups, "gc": gc, "tc": tc, "sl": sl}

        def fill_tiers(g_idx, keep=None):
            tc.blockSignals(True)
            tc.clear()
            if g_idx >= 0:
                tiers = groups[g_idx]["tiers"]
                n = len(tiers)
                for ti in range(n - 1, -1, -1):  # T1(최상) 먼저
                    t = tiers[ti]
                    tc.addItem(f"T{n - ti} · Lv{t['level']} · {ko2en.mod_ko(t['text'])}", t["modId"])
                    tc.setItemData(tc.count() - 1, t["text"], Qt.ItemDataRole.ToolTipRole)
                idx = next((k for k in range(tc.count()) if tc.itemData(k) == keep), 0)
                tc.setCurrentIndex(idx)
            tc.blockSignals(False)
            tc.setEnabled(g_idx >= 0)
            sl.setEnabled(g_idx >= 0)

        fill_tiers(sel_g, cur.get("modId"))

        def send():
            g_idx = gc.currentData()
            mod = tc.currentData() if g_idx is not None and g_idx >= 0 else "None"
            self._edit({"affix": {"table": table, "index": index, "modId": mod or "None", "range": sl.value() / 100}},
                       rebuild=False)
            self._update_used()

        chk.setChecked(sel_g >= 0)
        chk.setEnabled(sel_g >= 0)
        saved = {}

        def on_check(on):
            if not on:
                saved["g"], saved["t"] = gc.currentIndex(), tc.currentData()
                gc.setCurrentIndex(0)
                fill_tiers(-1)
                send()
            elif saved.get("g"):
                gc.setCurrentIndex(saved["g"])
                fill_tiers(gc.currentData(), saved.get("t"))
                send()

        def on_group(_i):
            fill_tiers(gc.currentData())
            chk.blockSignals(True)
            chk.setChecked(gc.currentData() is not None and gc.currentData() >= 0)
            chk.setEnabled(gc.currentData() is not None and gc.currentData() >= 0)
            chk.blockSignals(False)
            send()

        chk.toggled.connect(on_check)
        gc.activated.connect(on_group)
        tc.activated.connect(lambda _i: send())
        sl.valueChanged.connect(lambda _v: self._affix_timer(send))
        h.addWidget(gc, 1)
        h.addWidget(tc)
        h.addWidget(sl)
        lay.addLayout(h)
        return rowd

    def _affix_timer(self, fn) -> None:
        """슬라이더를 끄는 동안 너무 자주 계산하지 않게: 마지막 값만 0.16초 뒤에."""
        if not hasattr(self, "_atimer"):
            self._atimer = QTimer(self, singleShot=True, interval=160)
            self._atimer.timeout.connect(lambda: self._afn and self._afn())
        self._afn = fn
        self._atimer.start()

    def _update_used(self) -> None:
        """다른 칸에서 이미 고른 옵션 묶음(같은 group)은 고를 수 없게 (PoB 와 동일)."""
        rows = getattr(self, "affix_rows", [])
        for rd in rows:
            used = set()
            for other in rows:
                if other is rd:
                    continue
                gi = other["gc"].currentData()
                if gi is not None and gi >= 0:
                    used.add(other["groups"][gi].get("group"))
            model = rd["gc"].model()
            for k in range(1, rd["gc"].count()):
                g = rd["groups"][rd["gc"].itemData(k)]
                item = model.item(k)
                if item is not None:
                    item.setEnabled(not (g.get("group") and g.get("group") in used))

    def _fill_crafted_lines(self, r: dict) -> None:
        if not hasattr(self, "crafted_lines"):
            return
        try:
            lines = self._sorted_lines([ln for ln in r.get("lines") or [] if ln["kind"] == "explicit" and ln.get("active")])
            self.crafted_lines.setText("<br>".join(self._line_text(ln) for ln in lines) or
                                       f"<span style='color:{DIM}'>고른 옵션이 없습니다</span>")
        except RuntimeError:
            pass

    # ================================================================ 결과 / 장착
    def _render_result(self, r: dict) -> None:
        if r.get("valid") is None:
            self.result.setText(f"<span style='color:#e0644c'>이 아이템은 {html.escape(self.slot_label)} 에 넣을 수 없습니다.</span>")
            self.equip_btn.setEnabled(False)
            return
        replacing = ""
        eq = (self.page.equip.data or {}).get("slots") or []
        for s in eq + [{"slot": f["slot"], "item": f.get("item")} for f in (self.page.equip.flasks or {}).get("flasks") or []]:
            if s["slot"] == self.slot and s.get("item"):
                replacing = s["item"]["name"]
        fake = {"base_stats": r.get("base_stats") or {},
                "slots": [{"slot": self.slot, "label": self.slot_label, "stats": r.get("stats") or {}, "replacing": replacing}]}
        self.result.setText(Overlay._pob_html(fake))
        self.equip_btn.setEnabled(True)

    def _equip(self) -> None:
        if not self.info:
            return
        c = self.page._cur()
        if c is None or c["id"] != self.cid:
            self.status.setText("캐릭터가 바뀌었습니다. 창을 다시 열어 주세요.")
            return
        self.equip_btn.setEnabled(False)
        self.status.setText("장착 중…")
        cid = self.cid

        def ok(res):
            self.page._apply_result(cid, res, f"{self.slot_label} 옵션 변경 적용" if self.edit_mode else f"{self.slot_label} 에 새 아이템 장착")
            self.page.equip.refresh(full=True)
            tw = self.page._tree_win
            if tw is not None and tw.isVisible() and tw.cid == cid and self.slot.startswith("Jewel"):
                tw.bind(c)
            self.status.setText("적용했습니다 (빌드에 저장됨)" if self.edit_mode else
                                "장착했습니다 (빌드에 저장됨 · 장비 칸 드롭다운에서 예전 아이템으로 되돌릴 수 있음)")
            self.equip_btn.setEnabled(True)

        self.client.call("draft_replace" if getattr(self, "edit_mode", False) else "draft_equip", {"slot": self.slot}, ok, self._err)
