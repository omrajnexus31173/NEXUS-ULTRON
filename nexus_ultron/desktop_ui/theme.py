"""Obsidian Black, Midnight Navy, Electric Cyan & Titanium Silver Theme for PySide6."""

from __future__ import annotations

OBSIDIAN_BLACK = "#05070B"
MIDNIGHT_NAVY = "#0B1220"
PANEL_SURFACE = "#101A2E"
ELECTRIC_CYAN = "#00D9FF"
TITANIUM_SILVER = "#B9C5D0"
TEXT_PRIMARY = "#E8EEF5"
DANGER_RED = "#FF3B5C"
SUCCESS_GREEN = "#00E599"
WARNING_AMBER = "#FFB020"

NEXUS_ULTRON_QSS = f"""
QMainWindow, QWidget {{
    background-color: {OBSIDIAN_BLACK};
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Inter', 'DejaVu Sans', sans-serif;
    font-size: 13px;
}}

QLabel, QCheckBox {{
    background-color: transparent;
}}

QFrame#SidebarFrame {{
    background-color: {MIDNIGHT_NAVY};
    border-right: 1px solid #1A2942;
}}

QFrame#TopBarFrame {{
    background-color: {MIDNIGHT_NAVY};
    border-bottom: 1px solid #1A2942;
}}

QFrame#CardFrame {{
    background-color: {MIDNIGHT_NAVY};
    border: 1px solid #1B2B48;
    border-radius: 10px;
}}

QLabel#BrandTitle {{
    color: {TEXT_PRIMARY};
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 3px;
}}

QLabel#BrandTagline {{
    color: {ELECTRIC_CYAN};
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 1px;
}}

QLabel#ScreenHeading {{
    color: {TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 1px;
}}

QLabel#MetricValue {{
    color: {ELECTRIC_CYAN};
    font-size: 22px;
    font-weight: 700;
}}

QLabel#MutedLabel {{
    color: {TITANIUM_SILVER};
    font-size: 12px;
}}

QPushButton {{
    background-color: {PANEL_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid #243B61;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
}}

QPushButton:hover {{
    border-color: {ELECTRIC_CYAN};
    color: #FFFFFF;
    background-color: #152542;
}}

QPushButton#PrimaryButton {{
    background-color: #004E66;
    border: 1px solid {ELECTRIC_CYAN};
    color: #FFFFFF;
    font-weight: 700;
}}

QPushButton#PrimaryButton:hover {{
    background-color: #006B8C;
}}

QPushButton#EmergencyButton {{
    background-color: #4D0F1D;
    border: 1px solid {DANGER_RED};
    color: #FFD6DE;
    font-weight: 800;
    padding: 7px 16px;
}}

QPushButton#EmergencyButton:hover {{
    background-color: {DANGER_RED};
    color: #FFFFFF;
}}

QPushButton#NavButton {{
    text-align: left;
    padding: 9px 14px;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 4px;
    background-color: transparent;
    color: {TITANIUM_SILVER};
    font-weight: 600;
}}

QPushButton#NavButton:checked {{
    background-color: #122038;
    border-left: 3px solid {ELECTRIC_CYAN};
    color: {ELECTRIC_CYAN};
}}

QPushButton#NavButton:hover {{
    background-color: #0F1B30;
    color: #FFFFFF;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background-color: #080E1A;
    color: {TEXT_PRIMARY};
    border: 1px solid #1F3354;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {ELECTRIC_CYAN};
    selection-color: #05070B;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {ELECTRIC_CYAN};
}}

QTableWidget, QListWidget {{
    background-color: #080E1A;
    border: 1px solid #1B2B48;
    border-radius: 8px;
    gridline-color: #16243B;
    color: {TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {PANEL_SURFACE};
    color: {ELECTRIC_CYAN};
    border: none;
    border-bottom: 1px solid #233859;
    padding: 6px 8px;
    font-weight: 700;
}}

QProgressBar {{
    background-color: #080E1A;
    border: 1px solid #1E3150;
    border-radius: 5px;
    text-align: center;
    color: #FFFFFF;
    height: 16px;
}}

QProgressBar::chunk {{
    background-color: {ELECTRIC_CYAN};
    border-radius: 4px;
}}
"""
