from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import font

ui_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()

STATUS_COLORS = {
    "idle": "gray",
    "listening": "#00ff00",
    "processing": "yellow",
    "agent": "#00ccff",
    "sleep": "#202020",
}


class GenericPanel:
    """Base class for overlay panels."""

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
    def __init__(self, root: tk.Tk, bg_color: str):
        super().__init__(root, "Dictator Log", bg_color, alpha=0.92)
        self.width = 700
        self.height = 500

        self.text = tk.Text(
            self.window,
            font=("Monospace", 14),
            fg="#e0e0e0",
            bg="#1a1a2e",
            bd=0,
            highlightthickness=0,
            padx=20,
            pady=20,
            state="disabled",
            wrap="word",
        )
        self.text.pack(fill="both", expand=True)

        self._setup_tags()
        self._position_top_right()

    def _setup_tags(self) -> None:
        self.text.tag_configure("user", foreground="#ffd700")
        self.text.tag_configure("user_label", foreground="#ffd700", font=("Monospace", 14, "bold"))
        self.text.tag_configure("claude", foreground="#7fdbff")
        self.text.tag_configure("claude_label", foreground="#7fdbff", font=("Monospace", 14, "bold"))
        self.text.tag_configure("separator", foreground="#444466")
        self.text.tag_configure("heading", foreground="#ffffff", font=("Monospace", 15, "bold"))
        self.text.tag_configure("bold", foreground="#ffffff", font=("Monospace", 14, "bold"))
        self.text.tag_configure("code", foreground="#ffab70", font=("Monospace", 13), background="#2a2a4a")
        self.text.tag_configure("bullet", foreground="#98ee99")
        self.text.tag_configure("dim", foreground="#8888aa")

    def _position_top_right(self) -> None:
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        x = screen_width - self.width - 40
        y = 40
        self.window.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def show(self) -> None:
        self._position_top_right()
        super().show()

    def write(self, text: str, tag: str = "") -> None:
        try:
            self.text.config(state="normal")
            if tag:
                self.text.insert("end", text + "\n", tag)
            else:
                self.text.insert("end", text + "\n")
            self.text.see("end")
            self.text.config(state="disabled")
        except tk.TclError:
            pass

    def write_user(self, text: str) -> None:
        self.write("", "separator")
        self.write(f"  You: {text}", "user_label")
        self.write("", "separator")

    def write_agent(self, text: str) -> None:
        self.write("─" * 44, "separator")
        self.write("  Claude:", "claude_label")
        self._render_markdown(text)
        self.write("", "separator")

    def _render_markdown(self, text: str) -> None:
        """Render basic markdown formatting with tags."""
        import re
        try:
            self.text.config(state="normal")
            in_code_block = False

            for line in text.split("\n"):
                stripped = line.strip()

                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                    continue

                if in_code_block:
                    self.text.insert("end", f"    {line}\n", "code")
                elif stripped.startswith("# "):
                    self.text.insert("end", f"  {stripped[2:]}\n", "heading")
                elif stripped.startswith("## "):
                    self.text.insert("end", f"  {stripped[3:]}\n", "heading")
                elif stripped.startswith("### "):
                    self.text.insert("end", f"  {stripped[4:]}\n", "bold")
                elif stripped.startswith(("- ", "* ", "• ")):
                    self.text.insert("end", f"  • {stripped[2:]}\n", "bullet")
                elif stripped.startswith("`") and stripped.endswith("`") and len(stripped) > 2:
                    self.text.insert("end", f"  {stripped[1:-1]}\n", "code")
                elif stripped:
                    # Handle inline bold **text** and inline code `text`
                    parts = re.split(r"(\*\*.*?\*\*|`.*?`)", stripped)
                    self.text.insert("end", "  ")
                    for part in parts:
                        if part.startswith("**") and part.endswith("**"):
                            self.text.insert("end", part[2:-2], "bold")
                        elif part.startswith("`") and part.endswith("`"):
                            self.text.insert("end", part[1:-1], "code")
                        else:
                            self.text.insert("end", part, "claude")
                    self.text.insert("end", "\n")
                else:
                    self.text.insert("end", "\n")

            self.text.see("end")
            self.text.config(state="disabled")
        except tk.TclError:
            pass


class MainPanel(GenericPanel):
    def __init__(self, root: tk.Tk, bg_color: str):
        super().__init__(root, "Dictator Overlay", bg_color)
        self.default_height = 80
        self.max_height = 400

        self.status_frame = tk.Frame(self.window, bg="gray", height=4)
        self.status_frame.pack(fill="x", side="top")

        custom_font = font.Font(family="Sans", size=18, weight="bold")
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
            cursor="watch",
        )
        self.text_widget.pack(fill="both", expand=True)

        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        width = 900
        x = (screen_width - width) // 2

        self._screen_height = screen_height
        self._width = width
        self._x = x
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

    def set_text(self, text: str, color: str) -> None:
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", text)
        self.text_widget.config(fg=color)
        self.resize_to_fit()
        self.text_widget.config(state="disabled")

    def set_status(self, color: str) -> None:
        self.status_frame.config(bg=color)


class OverlayUI:
    """Thread-safe overlay UI manager."""

    def __init__(self):
        self.root: tk.Tk | None = None
        self.main_panel: MainPanel | None = None
        self.log_panel: LogPanel | None = None
        self.stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._bg_color = "#202020"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.root:
            self.root.quit()

    def update_text(self, text: str) -> None:
        ui_queue.put(("text", text))

    def update_status(self, status: str) -> None:
        ui_queue.put(("status", status))

    def show_agent_response(self, text: str) -> None:
        ui_queue.put(("agent", text))

    def toggle(self) -> None:
        ui_queue.put(("toggle_main", None))

    def toggle_log(self) -> None:
        ui_queue.put(("toggle_log", None))

    def hide_all(self) -> None:
        ui_queue.put(("hide_all", None))

    def update_log(self, text: str) -> None:
        ui_queue.put(("log", text))

    def update_log_user(self, text: str) -> None:
        ui_queue.put(("log_user", text))

    def _run(self) -> None:
        self.root = tk.Tk()
        self.root.withdraw()

        self.main_panel = MainPanel(self.root, self._bg_color)
        self.log_panel = LogPanel(self.root, self._bg_color)
        self.log_panel.hide()

        self._poll_queue()
        self.root.mainloop()

    def _poll_queue(self) -> None:
        try:
            while True:
                msg_type, data = ui_queue.get_nowait()

                if msg_type == "text":
                    if self.main_panel:
                        self.main_panel.set_text(data, "white")
                elif msg_type == "agent":
                    if self.main_panel:
                        self.main_panel.set_text(data, "#00ccff")
                    if self.log_panel:
                        self.log_panel.write_agent(data)
                elif msg_type == "status":
                    color = STATUS_COLORS.get(data, "gray")
                    if self.main_panel:
                        self.main_panel.set_status(color)
                    if self.log_panel:
                        if data == "agent":
                            self.log_panel.show()
                        elif data == "idle":
                            self.log_panel.hide()
                elif msg_type == "toggle_main":
                    if self.main_panel:
                        self.main_panel.toggle()
                elif msg_type == "toggle_log":
                    if self.log_panel:
                        self.log_panel.toggle()
                elif msg_type == "hide_all":
                    if self.main_panel:
                        self.main_panel.hide()
                    if self.log_panel:
                        self.log_panel.hide()
                elif msg_type == "log_user":
                    if self.log_panel:
                        self.log_panel.write_user(data)
                elif msg_type == "log":
                    if self.log_panel:
                        self.log_panel.write(f"  {data}", "dim")
        except queue.Empty:
            pass

        if not self.stop_event.is_set():
            self.root.after(50, self._poll_queue)


monitor = OverlayUI()
