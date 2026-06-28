"""First-run onboarding wizard: welcome, mic test, keybinding overview, model download."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

logger = logging.getLogger(__name__)


class FirstRunWizard:
    """Guides new users through initial setup with a simple Tkinter wizard.

    Steps:
    1. Welcome message
    2. Keybinding overview
    3. Model download with progress bar
    4. Completion
    """

    def __init__(self, on_complete: Callable[[], None]):
        self._on_complete = on_complete
        self._root: tk.Tk | None = None
        self._current_step = 0

    def show(self) -> None:
        """Display the first-run wizard (blocking on main thread)."""
        self._root = tk.Tk()
        self._root.title("Welcome to Dictator")
        self._root.geometry("600x400")
        self._root.resizable(False, False)

        self._container = tk.Frame(self._root, padx=30, pady=20)
        self._container.pack(fill="both", expand=True)

        self._show_welcome()
        self._root.mainloop()

    def _clear(self) -> None:
        for widget in self._container.winfo_children():
            widget.destroy()

    def _show_welcome(self) -> None:
        self._clear()
        tk.Label(
            self._container,
            text="Welcome to Dictator",
            font=("Segoe UI", 20, "bold"),
        ).pack(pady=(20, 10))

        tk.Label(
            self._container,
            text=(
                "Dictator is a privacy-first voice assistant that runs entirely on your machine.\n"
                "Dictate text into any window, or use voice commands to control your computer."
            ),
            font=("Segoe UI", 11),
            wraplength=500,
            justify="center",
        ).pack(pady=20)

        tk.Button(
            self._container,
            text="Next",
            command=self._show_keybindings,
            font=("Segoe UI", 11),
            width=15,
        ).pack(pady=20)

    def _show_keybindings(self) -> None:
        self._clear()
        tk.Label(
            self._container,
            text="Keybindings",
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=(10, 15))

        bindings = [
            ("F9", "Toggle dictation mode"),
            ("F10", "Toggle agent mode"),
            ("Escape", "Cancel current action"),
            ("Ctrl+Shift+Space", "Toggle overlay"),
        ]

        for key, desc in bindings:
            row = tk.Frame(self._container)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=key, font=("Consolas", 11, "bold"), width=20, anchor="e").pack(side="left")
            tk.Label(row, text=f"  {desc}", font=("Segoe UI", 11), anchor="w").pack(side="left")

        tk.Label(
            self._container,
            text="\nYou can customize these later in Settings.",
            font=("Segoe UI", 10),
            fg="gray",
        ).pack(pady=10)

        tk.Button(
            self._container,
            text="Next",
            command=self._show_model_download,
            font=("Segoe UI", 11),
            width=15,
        ).pack(pady=15)

    def _show_model_download(self) -> None:
        self._clear()
        tk.Label(
            self._container,
            text="Download AI Models",
            font=("Segoe UI", 16, "bold"),
        ).pack(pady=(10, 15))

        tk.Label(
            self._container,
            text=(
                "Dictator needs to download AI models for speech recognition and the voice agent.\n"
                "This requires ~1.5 GB of disk space and may take a few minutes."
            ),
            font=("Segoe UI", 11),
            wraplength=500,
            justify="center",
        ).pack(pady=10)

        self._progress_label = tk.Label(
            self._container, text="Ready to download", font=("Segoe UI", 10)
        )
        self._progress_label.pack(pady=5)

        self._progress_bar = ttk.Progressbar(
            self._container, length=400, mode="determinate"
        )
        self._progress_bar.pack(pady=10)

        self._download_btn = tk.Button(
            self._container,
            text="Download Now",
            command=self._start_download,
            font=("Segoe UI", 11),
            width=15,
        )
        self._download_btn.pack(pady=10)

        self._skip_btn = tk.Button(
            self._container,
            text="Skip (download later)",
            command=self._finish,
            font=("Segoe UI", 10),
            fg="gray",
        )
        self._skip_btn.pack()

    def _start_download(self) -> None:
        self._download_btn.config(state="disabled")
        self._skip_btn.config(state="disabled")

        from dictator.core.models import ModelManager

        manager = ModelManager()
        manager.set_progress_callback(self._update_progress)

        thread = threading.Thread(target=self._do_download, args=(manager,), daemon=True)
        thread.start()

    def _do_download(self, manager) -> None:
        success = manager.download_if_missing()
        if self._root:
            self._root.after(0, lambda: self._download_complete(success))

    def _update_progress(self, description: str, fraction: float) -> None:
        if self._root:
            self._root.after(0, lambda: self._set_progress(description, fraction))

    def _set_progress(self, description: str, fraction: float) -> None:
        try:
            self._progress_label.config(text=description)
            self._progress_bar["value"] = fraction * 100
        except tk.TclError:
            pass

    def _download_complete(self, success: bool) -> None:
        if success:
            self._progress_label.config(text="Download complete!")
            self._progress_bar["value"] = 100
        else:
            self._progress_label.config(text="Download failed. You can retry from Settings.")

        tk.Button(
            self._container,
            text="Finish",
            command=self._finish,
            font=("Segoe UI", 11),
            width=15,
        ).pack(pady=15)

    def _finish(self) -> None:
        if self._root:
            self._root.destroy()
            self._root = None
        self._on_complete()
