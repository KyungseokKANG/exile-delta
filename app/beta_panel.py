"""(베타) 캐릭터 화면의 'Beta' 탭: 슬롯별 DPS 최적 옵션 찾기.

1차: DPS 만 보고 접두·접미 최적 조합 (headless.lua es_optimize)
2차: 결과를 아이템 창에서 옵션 체크 해제 / 다른 옵션으로 교체하며 저항·EHP 맞추기 (item_creator)
"""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

import ko2en
from overlay import SLOT_KO, Overlay

DIM, POS, NEG = "#968b7a", "#7fc46a", "#e0644c"
INFL_KO = {"Shaper": "쉐이퍼", "Elder": "엘더", "Warlord": "전쟁군주", "Hunter": "사냥꾼", "Crusader": "십자군", "Redeemer": "구원자"}
CAT_KO = {"Abrasive": "공격", "Accelerating": "속도", "Dextral": "접미 옵션", "Fertile": "생명력·마나", "Imbued": "주문",
          "Intrinsic": "능력치", "Noxious": "물리·카오스", "Prismatic": "저항", "Sinistral": "접두 옵션", "Tempering": "방어",
          "Turbulent": "원소", "Unstable": "치명타"}
GEAR = ["Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves", "Boots", "Amulet", "Ring 1", "Ring 2", "Belt"]


class BetaCard:
    def __init__(self, page, host: QVBoxLayout):
        self.page = page
        self.client = page.client
        self.result: dict | None = None
        self.busy = False

        intro = QLabel(
            "<b style='color:#ead197'>장비별 DPS 최적화 (베타)</b><br>"
            f"<span style='color:{DIM}'>부위를 고르고 실행하면, 그 부위 베이스에 붙을 수 있는 접두·접미 옵션을 하나씩 붙여 DPS 순으로 줄 세운 뒤 "
            "상위 3+3 에서 시작해 서로 바꿔 보며 가장 DPS 가 높은 6옵션을 찾습니다 (시너지·캡 반영). "
            "영향력은 없음 / 하나씩 / 효과 있던 것끼리 2개 조합을 모두 계산하고, 악세는 촉매 특수 퀄리티 20% 중 최고를 고릅니다. "
            "지금 템보다 낮게 나오면 가장 덜 떨어지는 조합입니다. "
            "결과는 '옵션 조정' 창에서 체크 해제 / 다른 옵션으로 바꿔 저항·EHP 를 맞춘 뒤 장착할 수 있습니다.</span>")
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        host.addWidget(intro)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("부위"))
        self.slot = QComboBox()
        for s in GEAR:
            self.slot.addItem(SLOT_KO.get(s, s), s)
        self.slot.setCurrentIndex(GEAR.index("Ring 1"))
        self.slot.currentIndexChanged.connect(self._load_bases)
        row.addWidget(self.slot)
        row.addWidget(QLabel("베이스"))
        self.base = QComboBox()
        self.base.setMinimumWidth(240)
        row.addWidget(self.base)
        row.addWidget(QLabel("티어"))
        self.tier = QComboBox()
        for t in (1, 2, 3):
            self.tier.addItem(f"T{t} {'(최고)' if t == 1 else '까지'}", t)
        row.addWidget(self.tier)
        row.addWidget(QLabel("수치"))
        self.range = QComboBox()
        self.range.addItem("최대", 1.0)
        self.range.addItem("중간", 0.5)
        row.addWidget(self.range)
        row.addStretch(1)
        host.addLayout(row)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.use_infl = QCheckBox("영향력 옵션 포함 (최대 2개)")
        self.use_infl.setChecked(True)
        self.use_infl.setToolTip("쉐이퍼·엘더·전쟁군주·사냥꾼·십자군·구원자 옵션까지 후보로 (각성자의 오브처럼 한 아이템 최대 2개)")
        row.addWidget(self.use_infl)
        self.use_cat = QCheckBox("악세 특수 퀄리티 20%")
        self.use_cat.setChecked(True)
        self.use_cat.setToolTip("반지·목걸이·허리띠: 촉매 12종 중 가장 좋은 것을 20% 로 (무기·방어구는 일반 퀄리티 20%)")
        row.addWidget(self.use_cat)
        self.no_sock = QCheckBox("'장착된 젬 보조' 옵션 제외")
        self.no_sock.setToolTip("'장착된 젬에 ○○ 보조 효과 적용' 옵션은 그 장비에 꽂은 젬에만 적용됩니다.\n"
                                "주 스킬을 다른 장비에 꽂았다면 체크해서 후보에서 빼세요 (같이 붙은 공속 등은 계산에 반영됨).")
        row.addWidget(self.no_sock)
        row.addStretch(1)
        self.run_btn = QPushButton("DPS 최적 옵션 찾기")
        self.run_btn.setObjectName("Primary")
        self.run_btn.clicked.connect(self.run)
        row.addWidget(self.run_btn)
        host.addLayout(row)

        self.status = QLabel()
        self.status.setStyleSheet(f"color: {DIM};")
        host.addWidget(self.status)
        self.out = QLabel()
        self.out.setTextFormat(Qt.TextFormat.RichText)
        self.out.setWordWrap(True)
        host.addWidget(self.out)
        btns = QHBoxLayout()
        self.edit_btn = QPushButton("옵션 조정 · 장착 (체크 해제 / 다른 옵션으로 바꾸기)")
        self.edit_btn.setObjectName("Primary")
        self.edit_btn.clicked.connect(self.open_editor)
        self.edit_btn.hide()
        btns.addWidget(self.edit_btn)
        btns.addStretch(1)
        host.addLayout(btns)
        self.rank = QLabel()
        self.rank.setTextFormat(Qt.TextFormat.RichText)
        self.rank.setWordWrap(True)
        host.addWidget(self.rank)
        self._bases_for = None

    # ------------------------------------------------------------ 베이스 목록
    def on_shown(self) -> None:
        if self._bases_for != self.slot.currentData():
            self._load_bases()

    def _load_bases(self) -> None:
        slot = self.slot.currentData()
        self._bases_for = slot
        self.base.clear()
        cur = ""
        for s in ((self.page.equip.data or {}).get("slots") or []):
            if s["slot"] == slot and s.get("item"):
                cur = s["item"].get("base") or ""
        self.base.addItem(f"지금 베이스 · {ko2en.name_ko(cur) or cur}" if cur else "(베이스를 고르세요)", cur)
        if self.client.state != "ready":
            return

        def ok(r):
            if self.slot.currentData() != slot:
                return
            for bt in r.get("baseTypes") or []:
                for b in bt["bases"]:
                    if b["name"] != cur:
                        ko = ko2en.name_ko(b["name"])
                        self.base.addItem(f"{ko + '  ' if ko else ''}{b['name']} · Lv{b.get('level') or 0}", b["name"])

        self.client.call("item_catalog", {"slot": slot}, ok, lambda m: None)

    # ------------------------------------------------------------ 실행
    def run(self) -> None:
        c = self.page._cur()
        if c is None or self.client.state != "ready" or self.busy:
            return
        base = self.base.currentData() or ""
        if not base:
            self.status.setText("이 부위가 비어 있습니다 — 베이스를 골라 주세요")
            return
        self.busy = True
        self.run_btn.setEnabled(False)
        self.status.setText("계산 중… (옵션·영향력 조합마다 PoB 로 계산 — 10초 안팎)")
        self.page._ensure_loaded()
        slot = self.slot.currentData()
        spec = {"slot": slot, "base": base, "tier": self.tier.currentData(), "range": self.range.currentData(),
                "influence": self.use_infl.isChecked(), "catalyst": self.use_cat.isChecked(),
                "noSocketed": self.no_sock.isChecked()}

        def ok(r):
            self.busy = False
            self.run_btn.setEnabled(True)
            self.result = dict(r, slot=slot)
            self.render()

        def err(m):
            self.busy = False
            self.run_btn.setEnabled(True)
            self.status.setText(f"실패: {m}")

        self.client.call("optimize", {"spec": spec}, ok, err)

    def render(self) -> None:
        r = self.result or {}
        if not r:
            return
        slot = r["slot"]
        base_stats, final = r.get("base") or {}, r.get("final") or {}
        k = r.get("key", "CombinedDPS")
        a, b = base_stats.get(k) or 0, final.get(k) or 0
        self.status.setText(f"PoB 계산 {r.get('calcs')}번 · 영향력 조합 {r.get('tried')}가지 시도 · "
                            f"기준: {'Full DPS' if k == 'FullDPS' else '주 스킬 DPS'}")
        lines = [f"<b>{html.escape(SLOT_KO.get(slot, slot))}</b> · {html.escape(ko2en.name_ko(r.get('baseName', '')) or r.get('baseName', ''))}"
                 f" <span style='color:{DIM}'>(지금: {html.escape(r.get('current') or '비어 있음')})</span>"]
        extras = []
        infl = r.get("influences") or []
        if infl:
            extras.append("영향력 " + " + ".join(f"<b style='color:#b7a3ff'>{INFL_KO.get(x, x)}</b> ({x})" for x in infl))
        elif r.get("canInfluence"):
            extras.append(f"<span style='color:{DIM}'>영향력 없음이 가장 좋음</span>")
        if r.get("catalyst"):
            extras.append(f"특수 퀄리티 <b style='color:#6fd0c4'>{CAT_KO.get(r['catalyst'], '')} +20%</b> ({r['catalyst']} Catalyst)")
        elif r.get("quality"):
            extras.append(f"퀄리티 +{r['quality']}%")
        if extras:
            lines.append(" &nbsp;·&nbsp; ".join(extras))
        if a:
            p = (b - a) / a * 100
            col = POS if p > 0 else NEG
            note = "" if p > 0 else f" <span style='color:{DIM}'>— 지금 템이 더 셉니다. 일반 옵션으로 만들 수 있는 것 중 가장 덜 떨어지는 조합</span>"
            lines.append(f"DPS <b style='color:{col}; font-size:13pt'>{p:+.1f}%</b>{note}")
        rows = []
        for c in r.get("chosen") or []:
            kind = "접두" if c["kind"] == "prefix" else "접미"
            contrib = c["contrib"] / a * 100 if a else 0
            note = ""
            if c["text"].startswith("Socketed Gems") and (r.get("mainSlot") or "") != slot:
                where = SLOT_KO.get(r.get("mainSlot") or "", r.get("mainSlot") or "다른 장비")
                note = (f"<br><span style='color:#e8b65a; font-size:9.5pt'>※ 보조 효과는 이 장비에 꽂은 젬에만 — 주 스킬은 "
                        f"{html.escape(where)}에 있어서 적용 안 됨. 기여도는 같이 붙은 다른 효과(공격 속도 등) 몫</span>")
            rows.append(f"<tr><td style='color:#c8a96a; padding-right:8px'>{kind}</td>"
                        f"<td style='padding-right:8px'>T{c['tier']}</td>"
                        f"<td style='padding-right:14px'>{html.escape(ko2en.mod_ko(c['text']))}{note}</td>"
                        f"<td style='color:{DIM}'>기여 <b style='color:{POS if contrib > 0 else DIM}'>{contrib:+.1f}%</b></td></tr>")
        lines.append("<table cellspacing='0' cellpadding='2'>" + "".join(rows) + "</table>")
        fake = {"base_stats": base_stats, "slots": [{"slot": slot, "stats": final, "replacing": r.get("current") or ""}]}
        lines.append(Overlay._pob_html(fake))
        self.out.setText("<br>".join(lines))
        self.edit_btn.show()

        def rank_html(title, lst):
            items = []
            for i, x in enumerate(lst[:12], start=1):
                p = x["solo"] / r["empty"] * 100 if r.get("empty") else 0
                items.append(f"{i}. {html.escape(ko2en.mod_ko(x['text']))} <span style='color:{POS if p > 0.005 else DIM}'>{p:+.2f}%</span>")
            return f"<b style='color:#c8a96a'>{title}</b><br>" + "<br>".join(items)

        self.rank.setText(
            f"<span style='color:{DIM}'>옵션 하나만 붙였을 때 DPS (빈 베이스 대비) 순위</span>"
            "<table><tr><td style='padding-right:30px; vertical-align:top'>" + rank_html("접두", r.get("prefixRank") or [])
            + "</td><td style='vertical-align:top'>" + rank_html("접미", r.get("suffixRank") or []) + "</td></tr></table>")

    def open_editor(self) -> None:
        r = self.result or {}
        if not r.get("draft"):
            return
        slot = r["slot"]
        self.page.equip.open_draft(slot, SLOT_KO.get(slot, slot), r["draft"])
