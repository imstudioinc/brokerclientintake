"""Small shared widgets that give the forms one look (used by the property and commercial pages).

YesNo: a two-choice pill. Both choices are always visible; the chosen one is filled (Yes green with a tick, No slate
with a cross) and the other stays quiet, so a row of questions can be scanned at a glance. Click the chosen one again
to clear the answer. It behaves like the other form controls: get() / set(value).
"""
import customtkinter as ctk

YES_FILL = ("#15803D", "#1B8F46")        # green
NO_FILL = ("#64748B", "#475569")          # slate: clearly different from Yes without looking like an error
NO_HOVER = ("#556274", "#566579")
YES_HOVER = ("#116B33", "#22A455")
ON_FILL_TEXT = "#FFFFFF"


class YesNo(ctk.CTkFrame):
    def __init__(self, parent, ui, value="", command=None):
        super().__init__(parent, fg_color=ui.SURFACE_ALT, corner_radius=10, border_width=1, border_color=ui.BORDER)
        self.ui, self.command, self.value = ui, command, ""
        self.buttons = {}
        for i, (name, mark) in enumerate((("Yes", "✓  "), ("No", "✕  "))):
            b = ctk.CTkButton(self, text=name, width=74, height=30, corner_radius=8, font=ui.font(13, "bold"),
                              fg_color="transparent", hover_color=ui.BORDER, text_color=ui.MUTED, border_width=0,
                              command=lambda n=name: self.click(n))
            b.grid(row=0, column=i, padx=(3, 0) if i == 0 else (2, 3), pady=3)
            self.buttons[name] = (b, mark)
        self.set(value)

    def click(self, name):
        self.set("" if self.value == name else name)
        if self.command:
            self.command()

    def get(self):
        return self.value

    def set(self, value):
        self.value = value if value in self.buttons else ""
        ui = self.ui
        for name, (b, mark) in self.buttons.items():
            if name == self.value:
                fill, hover = (YES_FILL, YES_HOVER) if name == "Yes" else (NO_FILL, NO_HOVER)
                b.configure(text=mark + name, fg_color=fill, hover_color=hover, text_color=ON_FILL_TEXT)
            else:
                b.configure(text=name, fg_color="transparent", hover_color=ui.BORDER, text_color=ui.MUTED)


class Segmented(ctk.CTkSegmentedButton):
    """CTkSegmentedButton whose segments have room to breathe: each one is as wide as its text plus padding (plain
    customtkinter sizes them to the bare text, which looks cramped and leaves hairlines at the rounded corners)."""

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.pad_segments()

    def pad_segments(self):
        try:
            import tkinter.font as tkfont
            font = tkfont.Font(font=self.cget("font")) if self.cget("font") else None
        except Exception:
            font = None
        for text, button in self._buttons_dict.items():
            measure = font.measure(text) if font else len(text) * 8
            button.configure(width=max(52, int(measure / max(self._get_widget_scaling(), 1)) + 20))
