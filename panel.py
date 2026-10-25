"""Panel: a page shown inside the main window instead of a separate (Toplevel) window.

The owner wants everything in one window. Every dialog subclasses Panel instead of CTkToplevel:
it opens over the current view with a "← Back" bar and a title, and closing it (Back, Escape,
or the dialog calling destroy()) brings back what was there before. Panels stack, so a page
opened from another page returns to it.

Short pages set FORM = True: they sit in a scrolling holder, so a form taller than the window
can still be scrolled to its buttons. Big pages manage their own scrolling.
Window-only calls the dialogs make (title, geometry, transient, grab_set, ...) are accepted
here: title() sets the bar's title; a geometry width under 900 px keeps the page that wide
and centred (forms), anything wider fills the window.
"""
import re
import sys

import customtkinter as ctk


class Panel(ctk.CTkFrame):
    def __init__(self, master, **kw):
        app = master.winfo_toplevel()
        self._app = app
        ui = self._ui = sys.modules[type(app).__module__]
        self._close_handler = None
        self._escape = None
        stack = app.__dict__.setdefault("_panels", [])

        # hide whatever is showing: the page below, or the current view
        if stack:
            stack[-1]._wrapper.pack_forget()
        else:
            for view in (getattr(app, "clients_view", None), getattr(app, "tracker_win", None),
                         getattr(app, "rules_view", None)):
                if view is not None and view.winfo_exists():
                    view.pack_forget()

        self._wrapper = ctk.CTkFrame(app, fg_color="transparent")
        self._wrapper.pack(fill="both", expand=True, padx=3 * ui.SP, pady=(0, 3 * ui.SP))
        bar = ctk.CTkFrame(self._wrapper, fg_color="transparent")
        bar.pack(fill="x", pady=(0, ui.SP))
        ctk.CTkButton(bar, text="←  Back", width=96, height=34, font=ui.font(13), fg_color="transparent",
                      border_width=1, border_color=ui.BORDER, text_color=ui.TEXT, hover_color=ui.SURFACE_ALT,
                      command=self._back).pack(side="left")
        self._title = ctk.CTkLabel(bar, text="", font=ui.font(17, "bold"), text_color=ui.TEXT)
        self._title.pack(side="left", padx=2 * ui.SP)
        self._area = ctk.CTkFrame(self._wrapper, fg_color="transparent")
        self._area.pack(fill="both", expand=True)
        self._area.grid_rowconfigure(0, weight=1)
        kw.setdefault("fg_color", ui.BG)
        # a form page (FORM = True) scrolls when the window is shorter than the form
        self._holder = None
        if getattr(type(self), "FORM", False):
            self._holder = ctk.CTkScrollableFrame(self._area, fg_color="transparent",
                                                  scrollbar_button_color=ui.BG, scrollbar_button_hover_color=ui.BORDER)
            self._holder.grid_columnconfigure(0, weight=1)
            super().__init__(self._holder, **kw)
            super().grid(row=0, column=0, sticky="nsew")
        else:
            super().__init__(self._area, **kw)
        self._fill(None)
        stack.append(self)
        app.bind("<Escape>", lambda e: stack and stack[-1]._back())

    # ---- size: forms stay their designed width, big pages fill the window ----
    def _fill(self, width):
        area = self._area
        for col in range(3):
            area.grid_columnconfigure(col, weight=0, minsize=0)
        target = self._holder if self._holder is not None else self
        grid = target.grid if self._holder is not None else super().grid
        if width and width < 900:
            area.grid_columnconfigure(0, weight=1)
            area.grid_columnconfigure(1, minsize=width + (20 if self._holder is not None else 0))
            area.grid_columnconfigure(2, weight=1)
        else:
            area.grid_columnconfigure(1, weight=1)
        grid(row=0, column=1, sticky="nsew")

    def geometry(self, spec=None):
        m = re.match(r"(\d+)x(\d+)", spec or "")
        if m:
            self._fill(int(m.group(1)))

    def title(self, text=None):
        if text is not None:
            self._title.configure(text=text)
        return self._title.cget("text")

    def protocol(self, name, func=None):
        if name == "WM_DELETE_WINDOW":
            self._close_handler = func

    # window-only calls: nothing to do inside one window
    def transient(self, *a):
        pass

    def grab_set(self, *a):
        pass

    def grab_release(self, *a):
        pass

    def resizable(self, *a):
        pass

    def minsize(self, *a):
        pass

    def attributes(self, *a, **k):
        pass

    def iconbitmap(self, *a, **k):
        pass

    def lift(self, *a):
        pass

    def focus_force(self):
        self.focus_set()

    def bind(self, sequence=None, func=None, add=None):
        if sequence == "<Escape>":
            self._escape = func          # Escape always goes to the page on top (see __init__)
            return None
        return super().bind(sequence, func, add=True if add in (None, "") else add)   # CTk keeps its own handlers

    # ---- closing ----
    def _back(self):
        if self._escape is not None:
            self._escape(None)
        elif self._close_handler is not None:
            self._close_handler()
        else:
            self.destroy()

    def destroy(self):
        app = self._app
        stack = app.__dict__.get("_panels", [])
        if self in stack:
            stack.remove(self)
        wrapper = self._wrapper
        super().destroy()
        if wrapper.winfo_exists():
            wrapper.destroy()
        try:
            if stack:                                   # back to the page below
                top = stack[-1]
                top._wrapper.pack(fill="both", expand=True, padx=3 * self._ui.SP, pady=(0, 3 * self._ui.SP))
            else:                                       # back to the view
                app.unbind("<Escape>")
                if hasattr(app, "show_view") and hasattr(app, "view_var"):
                    app.show_view(app.view_var.get(), _from_panel=True)
        except Exception:
            pass    # the whole window is closing


def close_all(app):
    """Close every open page (e.g. when switching to Tracker / Rules)."""
    for page in list(app.__dict__.get("_panels", []))[::-1]:
        page.destroy()
