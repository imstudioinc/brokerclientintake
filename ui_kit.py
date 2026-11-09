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


class Segmented(ctk.CTkFrame):
    """A row of choices in one rounded track (tabs / filters / small selectors). Replaces customtkinter's
    CTkSegmentedButton, whose bare-text segments, hairline borders and square corner pixels looked rough.

    Same calls the app already uses: values, variable, command, height, font, selected_color / selected_hover_color,
    set(), get(), configure(values=...), cget("values")."""

    def __init__(self, parent, values=(), variable=None, command=None, height=36, font=None, selected_color=None,
                 selected_hover_color=None, unselected_color=None, unselected_hover_color=None, text_color=None,
                 width=None, **_ignored):
        import sys
        app = parent.winfo_toplevel()
        self.ui = ui = sys.modules[type(app).__module__]
        super().__init__(parent, fg_color=ui.SURFACE_ALT, corner_radius=10, border_width=1, border_color=ui.BORDER)
        self.values, self.command, self.variable = list(values), command, variable
        self.seg_height = max(28, height - 8)
        self.font = font or ui.font(13, "bold")
        self.on_fill = selected_color or ui.ACCENT
        self.on_hover = selected_hover_color or ui.ACCENT_HOVER
        self.value = variable.get() if variable is not None else (self.values[0] if self.values else "")
        self.buttons = {}
        self.base_size = int(self.font.cget("size"))
        self.fitting = False
        if variable is not None:
            variable.trace_add("write", lambda *a: self.sync())
        self.build()
        self.bind("<Configure>", lambda e: self.after_idle(self.fit))

    def build(self):
        ui = self.ui
        for b in self.buttons.values():
            b.destroy()
        self.buttons = {}
        for i, name in enumerate(self.values):
            try:
                natural = int(self.font.measure(name)) + 6          # the text plus a little air; never clipped
            except Exception:
                natural = 9 * len(name) + 16
            b = ctk.CTkButton(self, text=name, height=self.seg_height, corner_radius=5, font=self.font,
                              fg_color="transparent", hover_color=ui.BORDER, text_color=ui.MUTED, border_width=0,
                              border_spacing=0, width=max(40, natural), command=lambda n=name: self.pick(n))
            b.grid(row=0, column=i, sticky="ew", padx=(3 if i == 0 else 1, 3 if i == len(self.values) - 1 else 1), pady=3)
            self.grid_columnconfigure(i, weight=1)                  # spare room is shared out; a tight row still fits
            self.buttons[name] = b
        self.paint()

    def fit(self):
        """When the row is wider than the room it was given (a narrow window), use a smaller font so every tab shows."""
        if self.fitting or not self.winfo_exists():
            return
        self.fitting = True
        try:
            room = self.winfo_width()
            if room <= 1:
                return
            size = self.base_size
            while True:
                if size != int(self.font.cget("size")):
                    self.font = ctk.CTkFont(family=self.font.cget("family"), size=size, weight=self.font.cget("weight"))
                    for b in self.buttons.values():
                        b.configure(font=self.font)
                    self.update_idletasks()
                if self.winfo_reqwidth() <= room + 1 or size <= 9:
                    break
                size -= 1
        finally:
            self.fitting = False

    def pick(self, name):
        self.set(name)
        if self.command:
            self.command(name)

    def sync(self):
        if self.variable is not None and self.variable.get() != self.value:
            self.value = self.variable.get()
            self.paint()

    def paint(self):
        ui = self.ui
        for name, b in self.buttons.items():
            if name == self.value:
                b.configure(fg_color=self.on_fill, hover_color=self.on_hover, text_color="#FFFFFF")
            else:
                b.configure(fg_color="transparent", hover_color=ui.BORDER, text_color=ui.MUTED)

    def set(self, value):
        self.value = value
        if self.variable is not None and self.variable.get() != value:
            self.variable.set(value)
        self.paint()

    def get(self):
        return self.value

    def cget(self, key):
        return list(self.values) if key == "values" else super().cget(key)

    def configure(self, require_redraw=False, **kw):
        if "values" in kw:
            self.values = list(kw.pop("values"))
            if self.value not in self.values and self.values:
                self.value = self.values[0]
            self.build()
        if kw:
            super().configure(require_redraw=require_redraw, **kw)


class Chips(ctk.CTkFrame):
    """Filter chips that wrap onto a second line instead of overflowing: separate rounded pills (the chosen one filled,
    the others outlined). Same calls as Segmented: values, variable, command, set(), get(), configure(values=...)."""

    def __init__(self, parent, values=(), variable=None, command=None, height=30, font=None, selected_color=None,
                 selected_hover_color=None, **_ignored):
        import sys
        app = parent.winfo_toplevel()
        self.ui = ui = sys.modules[type(app).__module__]
        super().__init__(parent, fg_color="transparent")
        self.values, self.command, self.variable = list(values), command, variable
        self.chip_height = height
        self.font = font or ui.font(13, "bold")
        self.on_fill = selected_color or ui.ACCENT
        self.on_hover = selected_hover_color or ui.ACCENT_HOVER
        self.value = variable.get() if variable is not None else (self.values[0] if self.values else "")
        self.buttons, self.laid_out = {}, None
        if variable is not None:
            variable.trace_add("write", lambda *a: self.sync())
        self.build()
        self.bind("<Configure>", lambda e: self.after_idle(self.flow))

    def build(self):
        for b in self.buttons.values():
            b.destroy()
        self.buttons, self.laid_out = {}, None
        for name in self.values:
            self.buttons[name] = ctk.CTkButton(self, text=name, height=self.chip_height, corner_radius=self.chip_height // 2,
                                               font=self.font, width=10, command=lambda n=name: self.pick(n))
        self.paint()
        self.flow()

    def flow(self):
        """Put the chips in rows that fit the width we were given."""
        if not self.winfo_exists():
            return
        room = self.winfo_width()
        if room <= 1:
            room = 10_000
        key = (room, tuple(self.values))
        if key == self.laid_out:
            return
        self.laid_out = key
        s = max(self._get_widget_scaling(), 1)
        gap = 6 * s                                        # all maths in real pixels; place() wants unscaled values
        x = y = 0
        height = self.chip_height * s
        for b in self.buttons.values():
            w = b.winfo_reqwidth()
            if x and x + w > room:
                x, y = 0, y + height + gap
            b.place(x=x / s, y=y / s)
            x += w + gap
        self.configure(height=(y + height) / s)

    def paint(self):
        ui = self.ui
        for name, b in self.buttons.items():
            if name == self.value:
                b.configure(fg_color=self.on_fill, hover_color=self.on_hover, text_color="#FFFFFF", border_width=0)
            else:
                b.configure(fg_color="transparent", hover_color=ui.SURFACE_ALT, text_color=ui.MUTED,
                            border_width=1, border_color=ui.BORDER)

    def pick(self, name):
        self.set(name)
        if self.command:
            self.command(name)

    def sync(self):
        if self.variable is not None and self.variable.get() != self.value:
            self.value = self.variable.get()
            self.paint()

    def set(self, value):
        self.value = value
        if self.variable is not None and self.variable.get() != value:
            self.variable.set(value)
        self.paint()

    def get(self):
        return self.value

    def cget(self, key):
        return list(self.values) if key == "values" else super().cget(key)

    def configure(self, require_redraw=False, **kw):
        if "values" in kw:
            self.values = list(kw.pop("values"))
            if self.value not in self.values and self.values:
                self.value = self.values[0]
            self.build()
        if kw:
            super().configure(require_redraw=require_redraw, **kw)


class NavTabs(ctk.CTkFrame):
    """Main navigation: plain text tabs, the current one dark / bold with a short red bar under it. No track, no fill.
    Same calls as Segmented: values, variable, command, set(), get()."""

    def __init__(self, parent, values=(), variable=None, command=None, font=None, **_ignored):
        import sys
        app = parent.winfo_toplevel()
        self.ui = ui = sys.modules[type(app).__module__]
        super().__init__(parent, fg_color="transparent")
        self.values, self.command, self.variable = list(values), command, variable
        self.font = font or ui.font(15, "bold")
        self.value = variable.get() if variable is not None else (self.values[0] if self.values else "")
        self.tabs = {}
        for i, name in enumerate(self.values):
            b = ctk.CTkButton(self, text=name, width=10, height=34, corner_radius=8, font=self.font, fg_color="transparent",
                              hover_color=ui.SURFACE_ALT, text_color=ui.MUTED, command=lambda n=name: self.pick(n))
            b.grid(row=0, column=i, padx=(0 if i == 0 else 2, 2))
            bar = ctk.CTkFrame(self, width=1, height=3, corner_radius=2, fg_color="transparent")
            bar.grid(row=1, column=i, sticky="ew", padx=14, pady=(1, 0))
            self.tabs[name] = (b, bar)
        if variable is not None:
            variable.trace_add("write", lambda *a: self.sync())
        self.paint()

    def paint(self):
        ui = self.ui
        for name, (b, bar) in self.tabs.items():
            on = name == self.value
            b.configure(text_color=ui.TEXT if on else ui.MUTED)
            bar.configure(fg_color=ui.PRIMARY if on else "transparent")

    def pick(self, name):
        self.set(name)
        if self.command:
            self.command(name)

    def sync(self):
        if self.variable is not None and self.variable.get() != self.value:
            self.value = self.variable.get()
            self.paint()

    def set(self, value):
        self.value = value
        if self.variable is not None and self.variable.get() != value:
            self.variable.set(value)
        self.paint()

    def get(self):
        return self.value
