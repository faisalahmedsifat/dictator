import tkinter as tk
from tkinter import font
import queue
import threading
import time

# Thread-safe communication
ui_queue = queue.Queue()

class LogPanel:
    def __init__(self, root, bg_color):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.title("Dictator Log")
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.bg_color = bg_color
        
        self.visible = True
        self.width = 600
        self.height = 400
        
        # Visuals
        self.window.configure(bg=self.bg_color)
        try:
            self.window.wait_visibility(self.window)
            self.window.attributes('-alpha', 0.60)
        except:
            pass
            
        # Layout
        self.text = tk.Text(
            self.window,
            font=("Monospace", 10),
            fg="#00ff00", # Terminal Green
            bg=self.bg_color,
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            state="disabled",
            wrap="word"
        )
        self.text.pack(fill="both", expand=True)
        
        # Positioning (Top Right)
        screen_width = self.window.winfo_screenwidth()
        x = screen_width - self.width - 50
        y = 50
        self.window.geometry(f"{self.width}x{self.height}+{x}+{y}")
        
    def write(self, text):
        self.text.config(state="normal")
        # Auto-scroll logic could be smarter, but always bottom for now
        self.text.insert("end", text + "\n")
        self.text.see("end")
        self.text.config(state="disabled")
        
    def toggle(self):
        if self.visible:
            self.window.withdraw()
            self.visible = False
        else:
            self.window.deiconify()
            self.visible = True

class OverlayUI:
    def __init__(self):
        self.root = None
        self.text_widget = None
        self.status_bar = None
        self.log_panel = None # Secondary Window
        
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        
        self.visible = True
        self.default_height = 80
        self.max_height = 400
        self.bg_color = "#202020"

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.root:
            self.root.quit()

    def update_text(self, text):
        ui_queue.put(("text", text))

    def update_status(self, color):
        ui_queue.put(("status", color))
        
    def show_agent_response(self, text):
        ui_queue.put(("agent", text))

    def toggle(self):
        ui_queue.put(("toggle", None))

    def toggle_log(self):
        ui_queue.put(("toggle_log", None))

    def update_log(self, text):
        ui_queue.put(("log", text))

    def _run(self):
        self.root = tk.Tk()
        self.root.title("Dictator Overlay")
        
        # 1. Main Window Setup
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=self.bg_color)
        try:
            self.root.wait_visibility(self.root)
            self.root.attributes('-alpha', 0.60)
        except:
            pass

        # 2. Main Window Layout
        self.status_frame = tk.Frame(self.root, bg="gray", height=4)
        self.status_frame.pack(fill="x", side="top")
        
        custom_font = font.Font(family="Sans", size=18, weight="bold")
        self.text_widget = tk.Text(
            self.root,
            font=custom_font,
            fg="white",
            bg=self.bg_color,
            bd=0,
            highlightthickness=0,
            wrap="word",
            padx=20,
            pady=15,
            state="disabled",
            cursor="watch"
        )
        self.text_widget.pack(fill="both", expand=True)

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = 900
        x = (screen_width - width) // 2
        self._update_geometry(width, self.default_height, x, screen_height)
        
        # 3. Initialize Log Panel
        self.log_panel = LogPanel(self.root, self.bg_color)
        # Hide log by default? Or Show? 
        # User requested "I dont see what the reactor is doing".
        # Let's keep it visible by default initially or toggleable.
        # I'll keep it visible.

        # 4. Polling Loop
        self._poll_queue()
        self.root.mainloop()

    def _update_geometry(self, width, height, x, screen_height):
        y = screen_height - height - 100
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.curr_x = x
        self.curr_width = width
        self.screen_height = screen_height

    def _resize_to_fit(self, content):
        if not self.text_widget: return
        lines = int(self.text_widget.index('end-1c').split('.')[0])
        line_height = 34
        calc_height = (lines * line_height) + 30
        new_height = max(self.default_height, min(calc_height, self.max_height))
        self._update_geometry(self.curr_width, new_height, self.curr_x, self.screen_height)
        if calc_height > self.max_height:
            self.text_widget.see("end")

    def _poll_queue(self):
        try:
            while True:
                msg_type, data = ui_queue.get_nowait()
                
                if msg_type == "text":
                    self._set_text(data, "white")
                elif msg_type == "agent":
                    self._set_text(data, "#00ccff")
                    # Also log to history
                    if self.log_panel: self.log_panel.write(f"Agent: {data}")
                elif msg_type == "status":
                    self._set_status(data)
                elif msg_type == "toggle":
                    self._toggle_visibility()
                elif msg_type == "toggle_log":
                    if self.log_panel: self.log_panel.toggle()
                elif msg_type == "log":
                    if self.log_panel: self.log_panel.write(data)
                    
        except queue.Empty:
            pass
        
        if not self.stop_event.is_set():
            self.root.after(50, self._poll_queue)

    def _set_text(self, text, color):
        if not self.text_widget: return
        
        # Log Logic: If it's user text (white), log it only if it's new/final?
        # dictate.py calls update_text constantly for partials.
        # optimizing logging: we can rely on dictate.py to call update_log explicitly for "User: ..." 
        # BUT dictate.py isn't updated for that yet.
        # For now, let's just create the capability.
        
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", text)
        self.text_widget.config(fg=color)
        self._resize_to_fit(text)
        self.text_widget.config(state="disabled")

    def _set_status(self, status):
        color_map = {
            "idle": "gray",
            "listening": "#00ff00",
            "processing": "yellow",
            "agent": "#00ccff",
            "sleep": "#202020" 
        }
        col = color_map.get(status, "gray")
        if self.status_frame:
            self.status_frame.config(bg=col)

    def _toggle_visibility(self):
        if self.visible:
            self.root.withdraw()
            self.visible = False
        else:
            self.root.deiconify()
            self.visible = True

# Global Instance
monitor = OverlayUI()
