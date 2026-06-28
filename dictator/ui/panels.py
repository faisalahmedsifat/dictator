"""UI panel widgets: MainPanel (overlay text) and LogPanel (scrollable log)."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font


def _get_mono_font() -> str:
    return "Consolas" if sys.platform == "win32" else "Monospace"


def _get_ui_font() -> str:
    return "Segoe UI" if sys.platform == "win32" else "Sans"


class GenericPanel:
    """Base class for overlay panels with visibility management."""

    def __init__(self, root: tk.Tk, title: str, bg_color: str, alpha: float = 0.60):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.title(title)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.bg_color = bg_color
        self.visible = True

        self.window.configure(bg=self.bg_color)
        try:
            self.window.wait_visibility(self.window)
            self.window.attributes("-alpha", alpha)
        except tk.TclError:
            pass

        if sys.platform == "win32":
            self._set_click_through()

    def _set_click_through(self) -> None:
        """Make window click-through on Windows using WS_EX_TRANSPARENT."""
        try:
            import ctypes
            hwnd = int(self.window.frame(), 16)
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_NOACTIVATE = 0x08000000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def toggle(self) -> None:
        if self.visible:
            self.window.withdraw()
        else:
            self.window.deiconify()
        self.visible = not self.visible

    def hide(self) -> None:
        self.window.withdraw()
        self.visible = False

    def show(self) -> None:
        self.window.deiconify()
        self.visible = True


class LogPanel(GenericPanel):
    """Scrollable log panel showing recent activity."""

    def __init__(self, root: tk.Tk, bg_color: str):
        super().__init__(root, "Dictator Log", bg_color)
        self.width = 600
        self.height = 400

        self.text = tk.Text(
            self.window,
            font=(_get_mono_font(), 10),
            fg="#00ff00",
            bg=self.bg_color,
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            state="disabled",
            wrap="word",
        )
        self.text.pack(fill="both", expand=True)

        screen_width = self.window.winfo_screenwidth()
        x = screen_width - self.width - 50
        self.window.geometry(f"{self.width}x{self.height}+{x}+50")
        self.hide()

    def write(self, text: str) -> None:
        try:
            self.text.config(state="normal")
            self.text.insert("end", text + "\n")
            self.text.see("end")
            self.text.config(state="disabled")
        except tk.TclError:
            pass


class MainPanel(GenericPanel):
    """Primary overlay panel showing dictation text and status."""

    def __init__(self, root: tk.Tk, bg_color: str, width: int = 900):
        super().__init__(root, "Dictator Overlay", bg_color, alpha=0.85)
        self.default_height = 80
        self.max_height = 400

        self.status_frame = tk.Frame(self.window, bg="gray", height=4)
        self.status_frame.pack(fill="x", side="top")

        custom_font = font.Font(family=_get_ui_font(), size=18, weight="bold")
        self.text_widget = tk.Text(
            self.window,
            font=custom_font,
            fg="white",
            bg=self.bg_color,
            bd=0,
            highlightthickness=0,
            wrap="word",
            padx=20,
            pady=15,
            state="disabled",
            cursor="arrow",
        )
        self.text_widget.pack(fill="both", expand=True)

        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        self._width = width
        self._x = (screen_width - width) // 2
        self._screen_height = screen_height
        self._update_geometry(self.default_height)

    def _update_geometry(self, height: int) -> None:
        y = self._screen_height - height - 100
        self.window.geometry(f"{self._width}x{height}+{self._x}+{y}")

    def resize_to_fit(self) -> None:
        try:
            lines = int(self.text_widget.index("end-1c").split(".")[0])
            calc_height = (lines * 34) + 30
            new_height = max(self.default_height, min(calc_height, self.max_height))
            self._update_geometry(new_height)
            if calc_height > self.max_height:
                self.text_widget.see("end")
        except tk.TclError:
            pass

    def set_text(self, text: str, color: str = "white") -> None:
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", text)
        self.text_widget.config(fg=color)
        self.resize_to_fit()
        self.text_widget.config(state="disabled")

    def set_status(self, color: str) -> None:
        self.status_frame.config(bg=color)
