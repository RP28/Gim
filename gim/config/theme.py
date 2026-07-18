from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Palette:
    background: str = "#0B0D10"
    surface: str = "#15191F"
    surface_alt: str = "#20262E"
    accent: str = "#E05252"
    text: str = "#F2F4F7"
    muted: str = "#9AA4B2"
    success: str = "#67C587"
    warning: str = "#E0A752"


PALETTE = Palette()
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
NODE_WIDTH = 188
NODE_HEIGHT = 64
NODE_X_GAP = 210
NODE_Y_GAP = 116


def build_stylesheet() -> str:
    p = PALETTE
    return f"""
    QWidget {{
        background: {p.background};
        color: {p.text};
        font-family: Arial, Helvetica, sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QDialog {{ background: {p.background}; }}
    QFrame#Card, QWidget#Card {{
        background: {p.surface};
        border: 1px solid {p.surface_alt};
        border-radius: 12px;
    }}
    QPushButton, QToolButton {{
        background: {p.surface_alt};
        color: {p.text};
        border: 1px solid #2D3540;
        border-radius: 8px;
        padding: 7px 11px;
    }}
    QPushButton:hover, QToolButton:hover {{ border-color: {p.accent}; }}
    QPushButton:checked {{
        background: {p.accent};
        border-color: {p.accent};
        color: white;
        font-weight: 600;
    }}
    QPushButton:pressed, QToolButton:pressed {{ background: #2A313B; }}
    QPushButton#accentButton {{
        background: {p.accent};
        border-color: {p.accent};
        color: white;
        font-weight: 600;
    }}
    QPushButton#accentButton:hover {{ background: #EE6262; }}
    QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: #101419;
        color: {p.text};
        border: 1px solid #2D3540;
        border-radius: 7px;
        padding: 6px;
        selection-background-color: {p.accent};
    }}
    QComboBox {{ padding-right: 30px; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background: {p.surface};
        color: {p.text};
        selection-background-color: {p.accent};
        border: 1px solid #2D3540;
    }}
    QLabel#Title {{ font-size: 24px; font-weight: 700; }}
    QLabel#SectionTitle {{ font-size: 15px; font-weight: 650; }}
    QLabel#Muted {{ color: {p.muted}; }}
    QSplitter::handle {{ background: #242A32; width: 2px; height: 2px; }}
    QTabWidget::pane {{ border: 1px solid #2D3540; border-radius: 8px; }}
    QTabBar::tab {{
        background: {p.surface}; color: {p.muted}; padding: 8px 14px;
        border: 1px solid #2D3540;
    }}
    QTabBar::tab:selected {{ color: {p.text}; border-bottom: 2px solid {p.accent}; }}
    QScrollBar:vertical {{ background: {p.background}; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #333C48; min-height: 30px; border-radius: 5px; }}
    QScrollBar:horizontal {{ background: {p.background}; height: 10px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: #333C48; min-width: 30px; border-radius: 5px; }}
    QGroupBox {{
        border: 1px solid #2D3540; border-radius: 9px; margin-top: 10px; padding-top: 10px;
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {p.muted}; }}
    QToolTip {{ background: {p.surface_alt}; color: {p.text}; border: 1px solid #3A4451; }}
    QListWidget, QTreeWidget, QTableWidget {{
        background: #101419; border: 1px solid #2D3540; border-radius: 8px;
        alternate-background-color: {p.surface};
    }}
    QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
        background: {p.accent}; color: white;
    }}
    QSlider::groove:horizontal {{ height: 5px; background: #303946; border-radius: 2px; }}
    QSlider::handle:horizontal {{ width: 15px; margin: -5px 0; background: {p.accent}; border-radius: 7px; }}
    QProgressBar {{ border: 1px solid #2D3540; border-radius: 6px; text-align: center; }}
    QProgressBar::chunk {{ background: {p.accent}; border-radius: 5px; }}
    """
