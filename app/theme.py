"""PoE1 톤의 다크 + 골드 테마."""
from __future__ import annotations

from pathlib import Path

from storage import APP_DIR

C = {
    "bg_title": "#0b0a08",
    "bg": "#15120e",
    "panel": "#1b1712",
    "row": "#1f1a14",
    "row_hover": "#2a231a",
    "input": "#100e0b",
    "border": "#2c251c",
    "border_hi": "#463a29",
    "gold": "#c8a96a",
    "gold_hi": "#ead197",
    "gold_dim": "#86704a",
    "text": "#ddd5c6",
    "text_dim": "#968b7a",
    "text_faint": "#62594d",
    "magic": "#8f8fff",
    "rare": "#ffff77",
    "unique": "#c8743a",
    "danger": "#d0503a",
}

QSS = r"""
* { font-family: "Malgun Gothic", "맑은 고딕", sans-serif; font-size: 10pt; color: @text; }
QWidget { background: transparent; }

/* ---------- 슬라이더: 동그란 손잡이를 끌어서 조정 ---------- */
QSlider { min-height: 22px; }
QSlider::groove:horizontal { height: 4px; background: #3a3226; border-radius: 2px; }
QSlider::sub-page:horizontal { background: @gold_dim; border-radius: 2px; }
QSlider::add-page:horizontal { background: #3a3226; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 14px; height: 14px; margin: -7px 0; border-radius: 9px;
    background: @gold_hi; border: 2px solid @gold_dim; }
QSlider::handle:horizontal:hover { background: #fff1c4; border-color: @gold; }
QSlider::handle:horizontal:pressed { background: @gold; }
QSlider::handle:horizontal:disabled { background: #4a4234; border-color: #3a3226; }

#WindowFrame { background: @bg; border: 1px solid @border_hi; }
#WindowFrame[maximized="true"] { border: none; }

/* ---------- 타이틀바 + 탭 ---------- */
#TitleBar { background: @bg_title; }
#AppTitle { color: @gold; font-family: "Georgia", "Times New Roman", serif; font-size: 10.5pt;
            font-weight: bold; letter-spacing: 3px; }
QTabBar#MainTabs { background: transparent; border: none; }
QTabBar#MainTabs::tab {
    background: transparent; color: @text_dim;
    height: 34px; min-width: 96px; max-width: 220px;
    padding: 0 8px 0 14px; margin-right: 2px;
    border: 1px solid transparent; border-bottom: none;
    border-top-left-radius: 9px; border-top-right-radius: 9px;
}
QTabBar#MainTabs::tab:hover:!selected { background: #17140f; color: @text; }
QTabBar#MainTabs::tab:selected {
    background: @bg; color: @gold_hi;
    border: 1px solid @border; border-top: 1px solid @gold_dim; border-bottom: none;
}
QTabBar#MainTabs QToolButton { background: @bg_title; border: none; color: @text_dim; width: 20px; }
QTabBar#MainTabs QToolButton:hover { color: @gold_hi; }
QTabBar#MainTabs QToolButton#TabClose {
    background: transparent; border: none; border-radius: 4px; color: @text_faint; width: 18px;
    font-family: "Segoe Fluent Icons", "Segoe MDL2 Assets"; font-size: 7pt; }
QTabBar#MainTabs QToolButton#TabClose:hover { background: #3a2a20; color: #ff9a80; }
#AddTabBtn { background: transparent; border: none; border-radius: 7px; color: @text_dim;
             font-family: "Segoe Fluent Icons", "Segoe MDL2 Assets"; font-size: 9pt; }
#AddTabBtn:hover { background: #1f1a14; color: @gold_hi; }
#WinBtn { background: transparent; border: none; color: @text_dim;
          font-family: "Segoe Fluent Icons", "Segoe MDL2 Assets"; font-size: 8pt; }
#WinBtn:hover { background: #1f1a14; color: @text; }
#WinBtn::menu-indicator { image: none; }
#WinClose { background: transparent; border: none; color: @text_dim;
            font-family: "Segoe Fluent Icons", "Segoe MDL2 Assets"; font-size: 8pt; }
#WinClose:hover { background: #c42b1c; color: #ffffff; }

/* ---------- 공용 위젯 ---------- */
QLineEdit, QDoubleSpinBox, QComboBox {
    background: @input; border: 1px solid @border_hi; border-radius: 6px;
    padding: 6px 10px; selection-background-color: @gold_dim; selection-color: #0b0a08;
}
QLineEdit:hover, QDoubleSpinBox:hover, QComboBox:hover { border-color: #5a4a33; }
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: @gold; }
QDoubleSpinBox { padding: 6px 8px; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0; height: 0; border: none; subcontrol-origin: border; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: url("@arrow"); width: 10px; height: 10px; }
QComboBox QAbstractItemView {
    background: @panel; border: 1px solid @border_hi; outline: none; padding: 4px;
    selection-background-color: @row_hover; selection-color: @gold_hi;
}
QComboBox QAbstractItemView::item { min-height: 26px; padding-left: 6px; }

QPushButton {
    background: @row; border: 1px solid @border_hi; border-radius: 6px;
    padding: 7px 16px; color: @text;
}
QPushButton:hover { background: @row_hover; border-color: @gold_dim; color: @gold_hi; }
QPushButton:pressed { background: @panel; }
QPushButton#Danger:hover { border-color: @danger; color: #ff9a80; background: #2a1712; }
QPushButton#Primary { background: #3a2f1e; border-color: @gold_dim; color: @gold_hi; font-weight: bold; }
QPushButton#Primary:hover { background: #4a3c25; border-color: @gold; }
QPushButton#DangerSolid { background: #4a1f16; border-color: #7a3424; color: #ffb3a0; font-weight: bold; }
QPushButton#DangerSolid:hover { background: #5c261b; border-color: @danger; }
QPushButton#AddOptionBtn {
    background: transparent; border: 1px dashed @border_hi; border-radius: 8px;
    color: @gold; padding: 11px; font-weight: bold;
}
QPushButton#AddOptionBtn:hover { border-color: @gold; background: #1d1810; color: @gold_hi; }

QScrollArea { border: none; background: transparent; }
#ListHost { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @border_hi; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @gold_dim; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @border_hi; border-radius: 3px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QMenu { background: @panel; border: 1px solid @border_hi; padding: 5px; }
QMenu::item { padding: 7px 26px 7px 12px; color: @text; border-radius: 4px; }
QMenu::item:selected { background: @row_hover; color: @gold_hi; }
QMenu::item:disabled { color: @text_faint; }
QMenu::separator { height: 1px; background: @border; margin: 4px 6px; }
QToolTip { background: @panel; color: @text; border: 1px solid @border_hi; padding: 6px; }

/* ---------- 편집기 ---------- */
#HeaderCard { background: @panel; border: 1px solid @border; border-radius: 10px; }
#FieldLabel { color: @text_dim; font-size: 9pt; }
#SectionLabel { color: @text_faint; font-size: 9pt; }
#CountLabel { color: @gold_dim; font-size: 9pt; }
#EmptyLabel { color: @text_faint; padding: 40px; }

#OptionRow { background: @row; border: 1px solid @border; border-radius: 8px; }
#OptionRow:hover { border-color: @border_hi; }
#OptText { color: @text; }
#BadgePrefix, #BadgeSuffix, #BadgeInf { border-radius: 4px; padding: 2px 0; font-size: 8.5pt; font-weight: bold; }
#BadgePrefix { color: @magic; background: #18183a; border: 1px solid #34346e; }
#BadgeSuffix { color: @gold; background: #261f12; border: 1px solid #5a4a2c; }
#BadgeInf { color: @unique; background: #26170d; border: 1px solid #5c3618; padding: 2px 6px; }
#ValueSpin { font-weight: bold; color: @gold_hi; }
#TierBtn {
    background: @input; border: 1px solid @border_hi; border-radius: 6px;
    padding: 6px 10px; color: @gold_hi; text-align: left;
}
#TierBtn:hover { border-color: @gold_dim; background: #17130e; }
#TierBtn[state="bad"] { color: #ff8f78; border-color: #6a2e22; }
#TierBtn::menu-indicator { image: none; width: 0; }
#RowDel { background: transparent; border: none; border-radius: 5px; color: @text_faint;
          font-family: "Segoe Fluent Icons", "Segoe MDL2 Assets"; font-size: 8pt; }
#RowDel:hover { background: #2e1812; color: #ff9a80; }

#StatusBar { background: @bg_title; border-top: 1px solid @border; }
#StatusText { color: @text_faint; font-size: 8.5pt; }

/* ---------- 섹션 전환 ---------- */
#NavSeg { background: #15120e; border: 1px solid @border; border-radius: 9px; }
#NavBtn { background: transparent; border: none; border-radius: 6px; color: @text_dim;
          padding: 4px 14px; font-weight: bold; }
#NavBtn:hover { color: @text; background: #1d1913; }
#NavBtn:checked { background: #2c2418; color: @gold_hi; }

/* ---------- 캐릭터 ---------- */
#Banner { background: #1d1810; border: 1px solid @gold_dim; border-radius: 10px; }
#BannerText { color: @text; }
QProgressBar { background: @input; border: none; border-radius: 3px; }
QProgressBar::chunk { background: @gold; border-radius: 3px; }
#CharName { color: @gold_hi; font-size: 15pt; font-weight: bold; font-family: "Georgia", "Malgun Gothic", serif; }
#CharSub { color: @text; }
#CardTitle { color: @gold; font-weight: bold; font-size: 9.5pt; }
#StatTile { background: @input; border: 1px solid @border; border-radius: 8px; }
#TileTitle { color: @text_dim; font-size: 8.5pt; }
#TileValue { color: @text; font-size: 15pt; font-weight: bold; }
#TileSub { color: @text_faint; font-size: 8.5pt; }
#ResLine { font-size: 10.5pt; padding-top: 4px; }
#DefLine { color: @text; line-height: 150%; }
#SkillRow { background: @input; border: 1px solid @border; border-radius: 6px; }
#SkillRow:hover { border-color: @border_hi; }
#Overlay { background: rgba(14, 12, 9, 238); border: 1px solid @gold_dim; border-radius: 10px; }
#Overlay QLabel { color: @text; background: transparent; }
#OverlayClose { color: @text_faint; font-size: 10pt; padding: 0 2px; }
#OverlayEdit { color: @gold_hi; background: rgba(200, 169, 106, 30); border: 1px solid @gold_dim;
    border-radius: 6px; padding: 3px 10px; font-size: 9pt; }
#OverlayEdit:hover { background: rgba(200, 169, 106, 60); }
#EditorRow { background: rgba(255, 255, 255, 6); border: 1px solid @border; border-radius: 6px; }
#EditorRow[off="true"] { background: transparent; border-style: dashed; }
#EditorNum { background: @input; border: 1px solid @border_hi; border-radius: 4px; padding: 1px 4px;
    color: @gold_hi; font-weight: bold; }
#EditorClose { background: rgba(255, 255, 255, 12); border: 1px solid @border_hi; border-radius: 6px;
    color: @text; font-size: 11pt; padding: 0; min-width: 0; min-height: 0; }
#EditorClose:hover { background: #c0392b; border-color: #e0644c; color: white; }
#SmallClose { background: transparent; border: 1px solid @border_hi; border-radius: 5px; color: @text_dim;
    font-size: 8.5pt; padding: 2px 12px; }
#SmallClose:hover { color: white; border-color: #e0644c; background: rgba(224, 100, 76, 60); }
#RowDelete { background: transparent; border: none; color: @text_faint; font-size: 10pt; }
#RowDelete:hover { color: #e0644c; }
#Overlay QLabel#AddedBadge { color: #0e0c09; background: #7fc46a; font-size: 8pt; font-weight: bold; border-radius: 4px; padding: 1px 5px; }
#Overlay QLabel#EditedBadge { color: #0e0c09; background: #e8c15a; font-size: 8pt; font-weight: bold; border-radius: 4px; padding: 1px 5px; }
#KindBadge { color: @text_faint; font-size: 8pt; border: 1px solid @border; border-radius: 4px; padding: 0 4px; }
#OverlayTab { padding-top: 4px; }
#OverlayRow { font-size: 9.5pt; }
#OverlaySep { background: @border; }
#OverlayPob { background: rgba(255, 255, 255, 10); border: 1px solid @border; border-radius: 8px; }
#ConfigSection { background: @input; border: 1px solid @border; border-radius: 8px; }
#ConfigSub { color: @gold_dim; font-weight: bold; font-size: 9pt; padding-top: 4px; }
QCheckBox, QRadioButton { color: @text_dim; spacing: 6px; }
QCheckBox:checked, QRadioButton:checked { color: @gold_hi; }
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid @border_hi; border-radius: 3px; background: @input; }
QCheckBox::indicator:hover { border-color: @gold_dim; }
QCheckBox::indicator:checked { background: @gold; border-color: @gold_hi; }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { background: #1a1612; border-color: @border; }
QRadioButton::indicator { width: 13px; height: 13px; border: 1px solid @border_hi; border-radius: 7px; background: @input; }
QRadioButton::indicator:hover { border-color: @gold_dim; }
QRadioButton::indicator:checked { background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
    stop:0 @gold_hi, stop:0.5 @gold, stop:0.6 @input, stop:1 @input); border-color: @gold; }
QPlainTextEdit { background: @input; border: 1px solid @border_hi; border-radius: 6px; padding: 6px;
    selection-background-color: @gold_dim; selection-color: #0b0a08; font-family: "Consolas", "Malgun Gothic"; }
QPlainTextEdit:focus { border-color: @gold; }

/* ---------- 다이얼로그 ---------- */
QDialog#Dialog { background: @bg; }
#DialogFrame { background: @bg; border: 1px solid @border_hi; }
#DialogHeader { background: @bg_title; border-bottom: 1px solid @border; }
#DialogTitle { color: @gold_hi; font-size: 11pt; font-weight: bold; }
#DialogSub { color: @text_dim; }
#DialogText { color: @text; }
#FilterChip {
    background: transparent; border: 1px solid @border_hi; border-radius: 13px;
    padding: 4px 14px; color: @text_dim;
}
#FilterChip:hover { color: @text; border-color: #5a4a33; }
#FilterChip:checked { border-color: @gold; color: @gold_hi; background: #261f12; }
QListWidget#ResultList { background: transparent; border: none; outline: none; }
QListWidget#ResultList::item { border: 1px solid transparent; border-radius: 6px; margin: 0 4px 3px 0; }
QListWidget#ResultList::item:hover { background: @row; }
QListWidget#ResultList::item:selected { background: @row_hover; border: 1px solid @gold_dim; }
#ResText { color: @text; }
#ResRange { color: @text_dim; font-size: 9pt; }
#AddedTag { color: #7fb069; font-size: 8.5pt; }
#DetailCard { background: @panel; border: 1px solid @border; border-radius: 10px; }
#DetailTitle { color: @gold_hi; font-size: 11pt; font-weight: bold; }
#DetailEn { color: @text_faint; font-size: 9pt; }
QTableWidget#TierTable {
    background: transparent; border: none; gridline-color: transparent;
    selection-background-color: @row_hover; selection-color: @gold_hi;
}
QTableWidget#TierTable::item { padding: 3px 6px; border-bottom: 1px solid @border; }
QTableWidget#TierTable::item:hover { background: #211b14; }
QTableWidget#TierTable::item:selected { background: #33291a; color: @gold_hi;
    border-top: 1px solid @gold_dim; border-bottom: 1px solid @gold_dim; }
QHeaderView::section {
    background: transparent; color: @text_faint; border: none;
    border-bottom: 1px solid @border_hi; padding: 5px 6px; font-size: 9pt;
}
QTableCornerButton::section { background: transparent; border: none; }
"""

ARROW_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">'
    '<path d="M1.5 3.5 L5 7 L8.5 3.5" fill="none" stroke="#c8a96a" stroke-width="1.4" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def build_qss() -> str:
    asset_dir = APP_DIR / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    arrow = asset_dir / "chevron.svg"
    if not arrow.exists() or arrow.read_text(encoding="utf-8") != ARROW_SVG:
        arrow.write_text(ARROW_SVG, encoding="utf-8")
    qss = QSS.replace("@arrow", arrow.as_posix())
    for k in sorted(C, key=len, reverse=True):
        qss = qss.replace("@" + k, C[k])
    return qss
