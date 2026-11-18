"""캐릭터 화면의 '장착 장비 · 주얼' 카드.

PoB Items 탭의 슬롯 드롭다운과 같은 동작: 빼기/다시 끼기/빌드 안의 다른 아이템으로 바꾸기.
각 슬롯 오른쪽에는 '빼면 얼마나 줄어드는지'(= 그 아이템의 기여도)를 PoB 로 계산해 보여준다.
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

import ko2en
from overlay import SLOT_KO

RARITY_COL = {"UNIQUE": "#d08a4a", "RARE": "#e8d77a", "MAGIC": "#8f9fff", "NORMAL": "#ddd5c6", "RELIC": "#82d68f"}
RARITY_KO = {"UNIQUE": "고유", "RARE": "희귀", "MAGIC": "마법", "NORMAL": "일반", "RELIC": "유물"}
KIND_KO = {"enchant": "인챈트", "scourge": "스커지", "implicit": "implicit", "explicit": "", "crucible": "도가니"}
POS, NEG, DIM = "#7fc46a", "#e0644c", "#968b7a"


def _fmt(v: float) -> str:
    a = abs(v)
    if a >= 1e6:
        return f"{v / 1e6:.2f}M"
    if a >= 1e4:
        return f"{v / 1e3:.1f}K"
    return f"{v:,.0f}"


def slot_name(s: dict) -> str:
    if s["kind"] == "jewel":
        return f"주얼 슬롯 {s['label'].split()[-1]}"
    if s["kind"] == "abyss":
        owner = s["slot"].split(" Abyssal Socket ")[0].replace(" Swap", "")
        return f"└ {SLOT_KO.get(owner, owner)} 심연 {s['slot'].split()[-1]}"
    return SLOT_KO.get(s["label"], s["label"])


def item_tooltip(it: dict | None, slot: str | None = None, affixes: bool = True) -> str:
    """slot = PoB 슬롯 이름 (접두/접미 판별용). affixes=False 면 접두/접미를 따지지 않음 (주얼 · 플라스크)."""
    if not it:
        return "비어 있음"
    import affix

    col = RARITY_COL.get(it.get("rarity"), "#ddd5c6")
    out = [f"<b style='color:{col}'>{html.escape(it.get('name') or '')}</b>"
           f"<br><span style='color:{DIM}'>{RARITY_KO.get(it.get('rarity'), '')} · {html.escape(it.get('base') or '')}"
           + (" · 타락" if it.get("corrupted") else "") + "</span>"]
    lines = it.get("lines") or []
    if affixes:
        rows = affix.ordered(lines, slot)
    else:
        rows = [(ln, 0, "") for ln in lines]
    last = None
    n_in = {}
    for _ln, gid, _a in rows:
        if gid:
            n_in[gid] = n_in.get(gid, 0) + 1
    seen = set()
    for ln, gid, a in rows:
        k = ln.get("kind")
        g = affix.group(k or "explicit", a)
        if last is not None and g != last:
            out.append("<span style='color:#4a4032'>────────</span>")
        last = g
        # 하이브리드 옵션: 접두/접미 표시는 묶음 마지막 줄에 한 번, 줄 앞에 묶음 표시
        if gid and n_in.get(gid, 0) > 1:
            first = gid not in seen
            seen.add(gid)
            n_in[gid] -= 1
            mark = "┌" if first else "└" if n_in[gid] == 0 else "│"
            lead = f"<span style='color:#6b5d48'>{mark} </span>"
            a = a if n_in[gid] == 0 else ""
        else:
            lead = ""
        tag = KIND_KO.get(k, "")
        if ln.get("crafted"):
            tag = "제작"
        if ln.get("fractured"):
            tag = "분열"
        txt = ko2en.passive_ko(ln["line"])
        color = "#b8a8ff" if k != "explicit" else "#9fb5ff" if not ln.get("crafted") else "#b9e0ff"
        out.append(f"{lead}<span style='color:{color}'>{html.escape(txt)}</span>"
                   + (f" <span style='color:{DIM}'>({tag})</span>" if tag else "")
                   + (f" &nbsp;{affix.html_badge(a)}" if a else ""))
    return "<br>".join(out)


class EquipmentCard:
    """character_page 의 카드 안 레이아웃을 채운다."""

    def __init__(self, page, host: QVBoxLayout):
        self.page = page
        self.client = page.client
        self.host = host
        self.data: dict | None = None
        self.flasks: dict | None = None
        self.creator = None
        self.impact: dict | None = None
        self.impact_stale = False
        self.last_item: dict[str, int] = {}
        self.busy = False
        self.cid: str | None = None
        self.data_cid: str | None = None

        top = QHBoxLayout()
        self.info = QLabel()
        self.info.setObjectName("SectionLabel")
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.TextFormat.RichText)
        top.addWidget(self.info, 1)
        clip = QPushButton("클립보드 아이템 비교")
        clip.setToolTip("게임/거래소에서 복사(Ctrl+C)해 둔 아이템을 지금 장비와 비교합니다 (한글·영문 모두).\n"
                        "게임에서 Ctrl+C 하면 자동으로도 뜹니다 (메뉴 '게임 Ctrl+C 감지').")
        clip.clicked.connect(self._compare_clipboard)
        top.addWidget(clip, 0, Qt.AlignmentFlag.AlignTop)
        self.recalc_btn = QPushButton("기여도 다시 계산")
        self.recalc_btn.setToolTip("트리·설정을 바꾼 뒤에는 각 장비를 뺐을 때의 변화를 다시 계산합니다")
        self.recalc_btn.clicked.connect(lambda: self.refresh(full=True))
        top.addWidget(self.recalc_btn, 0, Qt.AlignmentFlag.AlignTop)
        host.addLayout(top)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(4)
        host.addWidget(self.grid_host)
        self._timer = QTimer(singleShot=True, interval=350, timeout=lambda: self.refresh(full=False))
        self._auto = QTimer(singleShot=True, interval=1500, timeout=self._auto_impact)

    def _compare_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        win = self.page.window()
        fn = getattr(win, "open_item_text", None)
        if fn is None or not fn(QApplication.clipboard().text()):
            self.page.flash("클립보드에 아이템 텍스트가 없습니다 — 게임에서 아이템에 마우스를 올리고 Ctrl+C")

    # ------------------------------------------------------------ 데이터
    def on_result(self, cid: str) -> None:
        """캐릭터 계산 결과가 바뀔 때마다 (장비 목록만 가볍게 다시, 기여도는 '오래됨' 표시)."""
        if self.busy:
            return
        if cid != self.cid:
            self.cid = cid
            self.refresh(full=True)
            return
        self.impact_stale = self.impact is not None
        self._gen = getattr(self, "_gen", 0) + 1  # 나눠 계산 도중 빌드가 바뀌면 그 결과는 버림
        self._timer.start()
        self._auto.start()  # 잠시 조작이 없으면 기여도 자동 재계산 (장비 탭이 보일 때)

    def _auto_impact(self) -> None:
        if not self.impact_stale or self.busy or self.client.state != "ready":
            return
        if getattr(self.page, "_sub_i", 0) != 0 or not self.page.isVisible():
            return
        if self.client.fg_pending() or getattr(self, "_impact_running", False):
            self._auto.start()  # 다른 계산 중이면 조금 뒤에
            return
        cid = self.cid
        gen = getattr(self, "_gen", 0)
        self._impact_running = True

        def got(r):
            self._impact_running = False
            if cid != self.cid:
                return
            self.impact = r
            self.impact_stale = False
            self.render()

        def failed(m):
            self._impact_running = False
            if m is None and self.impact_stale:
                self._auto.start()  # 도중에 빌드가 바뀜 → 잠시 뒤 처음부터

        self.client.call_chunks("equipment_impact", {}, 6, got, failed,
                                alive=lambda: getattr(self, "_gen", 0) == gen and self.cid == cid)

    def refresh(self, full: bool = True) -> None:
        c = self.page._cur()
        if c is None or self.client.state != "ready":
            return
        cid = c["id"]
        self.cid = cid
        self.page._ensure_loaded()

        def got_list(r):
            if cid != self.cid:
                return
            self.data = r
            self.data_cid = cid
            if full:
                self.impact = None
                self.impact_stale = False
            self.render()
            self.client.call("flasks", {}, got_flasks, lambda m: None)
            if full:
                self.client.call_chunks("equipment_impact", {}, 6, got_impact, lambda m: None,
                                        alive=lambda: self.cid == cid)

        def got_flasks(r):
            if cid != self.cid:
                return
            self.flasks = r
            self.render()

        def got_impact(r):
            if cid != self.cid:
                return
            self.impact = r
            self.impact_stale = False
            self.render()

        self.client.call("equipment", {}, got_list, lambda m: self.info.setText(f"장비 목록을 읽지 못했습니다: {m}"))

    def set_slot(self, slot: str, item_id: int, msg: str) -> None:
        c = self.page._cur()
        if c is None or self.busy:
            return
        self.busy = True
        cid = c["id"]

        def ok(r):
            self.page._apply_result(cid, r, msg)  # busy 동안이라 on_result 는 건너뜀
            self.busy = False
            self.refresh(full=True)
            tw = self.page._tree_win
            if tw is not None and tw.isVisible() and tw.cid == cid:
                tw.bind(c)  # 클러스터 주얼이면 트리 모양이 바뀜

        def err(m):
            self.busy = False
            self.page.flash(f"장비 변경 실패: {m}")
            self.render()

        self.page._ensure_loaded()
        self.client.call("set_slot", {"slot": slot, "item": item_id}, ok, err)

    # ------------------------------------------------------------ 표시
    def _impact_html(self, s: dict) -> str:
        if not s.get("item"):
            return ""
        imp = self.impact or {}
        st = (imp.get("slots") or {}).get(s["slot"])
        if st is None:
            return f"<span style='color:{DIM}'>{'계산 중…' if self.impact is None else ''}</span>"
        base = imp.get("base") or {}
        dk = "FullDPS" if base.get("FullDPS") else "CombinedDPS"
        cells = []
        for key, nm in ((dk, "DPS"), ("TotalEHP", "EHP")):
            a, b = base.get(key) or 0.0, st.get(key) or 0.0
            if not a or a >= 1e299 or b >= 1e299:
                continue
            p = (b - a) / a * 100
            if abs(p) < 0.05:
                continue  # 변화 없는 값(+0.0%)은 생략
            col = NEG if p < 0 else POS
            cells.append(f"<span style='color:{DIM}'>{nm}</span> <b style='color:{col}'>{p:+.1f}%</b>")
        from statfmt import maxhit_html

        life = (st.get("Life") or 0) - (base.get("Life") or 0)
        if abs(life) >= 1:
            cells.append(f"<span style='color:{DIM}'>생명력</span> <span style='color:{NEG if life < 0 else POS}'>{_fmt(life)}</span>")
        mh = maxhit_html(base, st, "최대피격")
        style = "opacity:0.5;" if self.impact_stale else ""
        if not cells and not mh:
            return f"<span style='color:{DIM}'>빼도 변화 없음</span>"
        # 최대 피격(5속성)은 둘째 줄로
        return (f"<span style='{style}'>빼면 &nbsp;" + " · ".join(cells)
                + (("<br>" if cells else "") + f"<span style='font-size:9.5pt'>{mh}</span>" if mh else "") + "</span>")

    def render(self) -> None:
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        slots = (self.data or {}).get("slots") or []
        ready = self.client.state == "ready"
        n_jewel = sum(1 for s in slots if s["kind"] == "jewel" and s.get("item"))
        stale = " &nbsp;<span style='color:#e8b65a'>· 빌드가 바뀌어 기여도 다시 계산 중…</span>" if self.impact_stale else ""
        self.info.setText(
            f"체크 해제 = 빼고 계산 · 드롭다운 = 빌드 안의 다른 아이템 · 오른쪽 = <b>빼면</b> 바뀌는 양 · 변경 = 옵션 고치기"
            f"<br><span style='color:{DIM}'>주얼 {n_jewel}개 · 이름에 마우스를 올리면 옵션 · "
            f"Ctrl+C 비교도 여기 상태 기준</span>{stale}")
        row = self._render_flasks(ready)
        section = None
        for s in slots:
            sec = "주얼" if s["kind"] == "jewel" else "장비"
            if sec != section:
                section = sec
                h = QLabel(f"{sec}")
                h.setObjectName("ConfigSub")
                self.grid.addWidget(h, row, 0, 1, 5)
                row += 1
            it = s.get("item")
            tip = item_tooltip(it, s["slot"], affixes=s["kind"] not in ("jewel", "abyss"))
            chk = QCheckBox()
            chk.setChecked(bool(it))
            opts = s.get("options") or []
            if it:
                self.last_item[self._key(s)] = it["id"]
            can_on = bool(self.last_item.get(self._key(s)) or opts)
            chk.setEnabled(ready and not self.busy and (bool(it) or can_on))
            chk.setToolTip("체크 해제하면 이 장비를 빼고 계산합니다")
            chk.toggled.connect(lambda on, s=s: self._toggle(s, on))
            self.grid.addWidget(chk, row, 0)
            lab = QLabel(slot_name(s))
            lab.setStyleSheet(f"color: {'#c8a96a' if it else DIM};")
            self.grid.addWidget(lab, row, 1)
            if len(opts) > 1 or (not it and opts):
                cb = QComboBox()
                cb.addItem("(비어 있음)", 0)
                for o in opts:
                    cb.addItem(o["name"], o["id"])
                cb.setCurrentIndex(next((i + 1 for i, o in enumerate(opts) if it and o["id"] == it["id"]), 0))
                cb.setToolTip(tip)
                cb.setEnabled(ready and not self.busy)
                cb.activated.connect(lambda i, s=s, cb=cb: self._choose(s, cb.itemData(i)))
                cb.setMinimumWidth(180)
                cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                cb.setMinimumContentsLength(16)
                w = cb
            else:
                w = QLabel(html.escape(it["name"]) if it else "(비어 있음)")
                w.setTextFormat(Qt.TextFormat.RichText)
                w.setToolTip(tip)
            if it:
                w.setStyleSheet(f"color: {RARITY_COL.get(it.get('rarity'), '#ddd5c6')};")
            else:
                w.setStyleSheet(f"color: {DIM};")
            self.grid.addWidget(w, row, 2)
            imp = QLabel(self._impact_html(s))
            imp.setTextFormat(Qt.TextFormat.RichText)
            imp.setWordWrap(True)
            imp.setToolTip(tip)
            self.grid.addWidget(imp, row, 3)
            self.grid.addWidget(self._make_btn(s["slot"], slot_name(s).lstrip("└ "), ready, bool(it)), row, 4)
            row += 1
        self.grid.setColumnStretch(2, 1)
        self.grid.setColumnStretch(3, 1)
        if not slots:
            self.grid.addWidget(QLabel("PoB 엔진에서 장비를 읽는 중…"), 0, 0, 1, 4)

    def _key(self, s: dict) -> str:
        return f"{self.data_cid}|{s['slot']}"

    def _toggle(self, s: dict, on: bool) -> None:
        it = s.get("item")
        name = slot_name(s).lstrip("└ ")
        if not on and it:
            self.last_item[self._key(s)] = it["id"]
            self.set_slot(s["slot"], 0, f"{name} 뺌 — {it['name']}")
        elif on and not it:
            iid = self.last_item.get(self._key(s)) or ((s.get("options") or [{}])[0].get("id"))
            if iid:
                self.set_slot(s["slot"], iid, f"{name} 다시 장착")

    def _choose(self, s: dict, item_id) -> None:
        cur = (s.get("item") or {}).get("id") or 0
        if (item_id or 0) == cur:
            return
        name = slot_name(s).lstrip("└ ")
        self.set_slot(s["slot"], item_id or 0, f"{name} 변경됨")

    # ------------------------------------------------------------ 플라스크 (맨 위)
    def _render_flasks(self, ready: bool) -> int:
        fl = (self.flasks or {}).get("flasks") or []
        if not fl:
            return 0
        h = QLabel("플라스크  ·  체크 = 사용 중으로 계산 (PoB Items 탭의 활성 체크)")
        h.setObjectName("ConfigSub")
        self.grid.addWidget(h, 0, 0, 1, 5)
        row = 1
        base = (self.flasks or {}).get("base") or {}
        dk = "FullDPS" if base.get("FullDPS") else "CombinedDPS"
        for f in fl:
            it = f.get("item")
            tip = item_tooltip(it, affixes=False)
            chk = QCheckBox()
            chk.setChecked(bool(f.get("active")))
            chk.setEnabled(ready and bool(it))
            chk.setToolTip("체크하면 이 플라스크를 마신 상태로 계산합니다")
            chk.toggled.connect(lambda on, f=f: self.page._call(
                "set_flask", {"slot": f["slot"], "active": on}, f"{f['slot'][-1]}번 플라스크 {'사용' if on else '사용 안 함'}"))
            self.grid.addWidget(chk, row, 0)
            lab = QLabel(f"플라스크 {f['slot'][-1]}")
            lab.setStyleSheet(f"color: {'#c8a96a' if it else DIM};")
            self.grid.addWidget(lab, row, 1)
            opts = f.get("options") or []
            s = {"slot": f["slot"], "kind": "gear", "label": f["slot"], "item": it, "options": opts}
            if len(opts) > 1 or (not it and opts):
                cb = QComboBox()
                cb.addItem("(비어 있음)", 0)
                for o in opts:
                    cb.addItem(o["name"], o["id"])
                cb.setCurrentIndex(next((i + 1 for i, o in enumerate(opts) if it and o["id"] == it["id"]), 0))
                cb.setToolTip(tip)
                cb.setEnabled(ready and not self.busy)
                cb.activated.connect(lambda i, s=s, cb=cb: self._choose(s, cb.itemData(i)))
                cb.setMinimumWidth(180)
                cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                cb.setMinimumContentsLength(16)
                w = cb
            else:
                w = QLabel(html.escape(it["name"]) if it else "(비어 있음)")
                w.setToolTip(tip)
            w.setStyleSheet(f"color: {RARITY_COL.get((it or {}).get('rarity'), DIM)};")
            self.grid.addWidget(w, row, 2)
            txt = ""
            tg = f.get("toggled")
            if it and tg:
                cells = []
                for key, nm in ((dk, "DPS"), ("TotalEHP", "EHP")):
                    a, b = base.get(key) or 0.0, tg.get(key) or 0.0
                    if a and a < 1e299 and b < 1e299:
                        p = (b - a) / a * 100
                        if abs(p) >= 0.05:
                            col = POS if p > 0 else NEG
                            cells.append(f"<span style='color:{DIM}'>{nm}</span> <b style='color:{col}'>{p:+.1f}%</b>")
                from statfmt import maxhit_html

                mh = maxhit_html(base, tg, "최대피격")
                head = "끄면" if f.get("active") else "켜면"
                if not cells and not mh:
                    txt = f"<span style='color:{DIM}'>{head} 변화 없음</span>"
                else:
                    txt = (f"{head} &nbsp;" + " · ".join(cells)
                           + (("<br>" if cells else "") + f"<span style='font-size:9.5pt'>{mh}</span>" if mh else ""))
            imp = QLabel(txt)
            imp.setTextFormat(Qt.TextFormat.RichText)
            imp.setWordWrap(True)
            self.grid.addWidget(imp, row, 3)
            self.grid.addWidget(self._make_btn(f["slot"], f"플라스크 {f['slot'][-1]}", ready, bool(it)), row, 4)
            row += 1
        return row

    def _make_btn(self, slot: str, label: str, ready: bool, has_item: bool) -> QPushButton:
        b = QPushButton("변경" if has_item else "넣기")
        b.setToolTip(f"{label}: 지금 아이템의 옵션·수치를 바꿔 보고 적용합니다" if has_item else
                     f"{label}: 비어 있는 자리에 유니크 / 베이스로 만든 아이템을 넣습니다")
        b.setStyleSheet("QPushButton { padding: 3px 12px; font-size: 9.5pt; }")
        b.setEnabled(ready)
        b.clicked.connect(lambda: self.open_creator(slot, label, has_item))
        return b

    def open_creator(self, slot: str, label: str, edit: bool = True) -> None:
        from item_creator import ItemCreator

        if self.creator is None:
            self.creator = ItemCreator(self.page, self.page.window())
        self.creator.open_for(slot, label, edit=edit)

    def open_draft(self, slot: str, label: str, draft: dict) -> None:
        """(베타 최적화 결과 등) 만들어 둔 아이템을 옵션 조정 창으로."""
        from item_creator import ItemCreator

        if self.creator is None:
            self.creator = ItemCreator(self.page, self.page.window())
        self.creator.open_draft(slot, label, draft)