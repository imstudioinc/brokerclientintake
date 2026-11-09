"""Build templates/theme.json: customtkinter's defaults (radius, borders, colours) matched to the app's design tokens.

    python tools/make_theme.py

Every widget the app does not style itself (and every one a future screen forgets to style) then still looks like the
rest: 8 px corners, 1 px quiet borders, neutral dropdowns, a blue ACCENT for ticks / switches / selected tabs, and red
kept for the one main action. Keep the colours in step with the tokens at the top of client_intake.pyw.
"""
import json
from pathlib import Path

import customtkinter

BG = ["#F3F5F8", "#0F1419"]
SURFACE = ["#FFFFFF", "#1A2027"]
SURFACE_ALT = ["#F8FAFC", "#202832"]
FIELD = ["#FFFFFF", "#2B333D"]
BORDER = ["#D5DBE3", "#2C3540"]
TEXT = ["#111827", "#E6EAF0"]
MUTED = ["#5B6472", "#9AA4B2"]
PRIMARY = ["#C8102E", "#D42A44"]
PRIMARY_HOVER = ["#A50D26", "#B5213A"]
ACCENT = ["#2563EB", "#3B82F6"]
ACCENT_HOVER = ["#1D4ED8", "#2F6FDB"]
HOVER = ["#EEF1F5", "#27303B"]

SRC = Path(customtkinter.__file__).parent / "assets" / "themes" / "blue.json"
OUT = Path(__file__).resolve().parent.parent / "templates" / "theme.json"


def main():
    t = json.loads(SRC.read_text(encoding="utf-8"))
    t["CTkFrame"].update(corner_radius=10, border_width=0, fg_color=SURFACE, top_fg_color=SURFACE_ALT,
                         border_color=BORDER)
    t["CTkButton"].update(corner_radius=8, border_width=0, fg_color=PRIMARY, hover_color=PRIMARY_HOVER,
                          border_color=BORDER, text_color=["#FFFFFF", "#FFFFFF"], text_color_disabled=MUTED)
    t["CTkEntry"].update(corner_radius=8, border_width=1, fg_color=FIELD, border_color=BORDER, text_color=TEXT,
                         placeholder_text_color=MUTED)
    t["CTkComboBox"].update(corner_radius=8, border_width=1, fg_color=FIELD, border_color=BORDER, button_color=BORDER,
                            button_hover_color=MUTED, text_color=TEXT)
    t["CTkOptionMenu"].update(corner_radius=8, fg_color=FIELD, button_color=BORDER, button_hover_color=MUTED,
                              text_color=TEXT)
    t["CTkSegmentedButton"].update(corner_radius=8, border_width=2, fg_color=SURFACE_ALT, selected_color=ACCENT,
                                   selected_hover_color=ACCENT_HOVER, unselected_color=SURFACE_ALT,
                                   unselected_hover_color=HOVER, text_color=TEXT)
    t["CTkCheckBox"].update(corner_radius=5, border_width=2, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                            border_color=MUTED, checkmark_color=["#FFFFFF", "#FFFFFF"], text_color=TEXT)
    t["CTkRadioButton"].update(fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=MUTED, text_color=TEXT)
    t["CTkSwitch"].update(progress_color=ACCENT, fg_color=["#B8C0CB", "#3A4450"], button_color=["#FFFFFF", "#E6EAF0"],
                          button_hover_color=["#F3F5F8", "#FFFFFF"], text_color=TEXT)
    t["CTkTextbox"].update(corner_radius=8, border_width=1, fg_color=FIELD, border_color=BORDER, text_color=TEXT)
    t["CTkScrollbar"].update(button_color=["#C3CAD4", "#3A4450"], button_hover_color=["#9AA4B2", "#566579"])
    t["CTkProgressBar"].update(progress_color=ACCENT)
    t["CTkFont"] = {"family": "Segoe UI", "size": 14, "weight": "normal"}
    OUT.write_text(json.dumps(t, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
