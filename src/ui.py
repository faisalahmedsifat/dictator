import tkinter as tk
from tkinter import font
import queue
import threading
import time

# Thread-safe communication
ui_queue = queue.Queue()

class OverlayUI:
    def __init__(self):
        self.root = None
        self.label = None
        self.status_bar = None
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True

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

    def _run(self):
        self.root = tk.Tk()
        self.root.title("Dictator Overlay")
        
        # 1. Window Setup (Frameless, Topmost)
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.geometry("+50+50") # Default position
        
        # 2. Transparency / Visuals
        # Dark Gray background with some transparency
        bg_color = "#202020"
        self.root.configure(bg=bg_color)
        # Try alpha (works on most Linux compositors)
        try:
            self.root.wait_visibility(self.root)
            self.root.attributes('-alpha', 0.85)
        except:
            pass

        # 3. Layout
        # Status Bar (Top Line)
        self.status_frame = tk.Frame(self.root, bg="gray", height=4)
        self.status_frame.pack(fill="x", side="top")
        
        # Text Area
        custom_font = font.Font(family="Sans", size=18, weight="bold")
        self.label = tk.Label(
            self.root, 
            text="Dictator Ready...", 
            font=custom_font, 
            fg="white", 
            bg=bg_color,
            wraplength=800,
            justify="left",
            padx=20,
            pady=15
        )
        self.label.pack(fill="both", expand=True)

        # 4. Positioning logic (Bottom Center by default)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = 900
        height = 120
        x = (screen_width - width) // 2
        y = screen_height - height - 100
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # 5. Polling Loop
        self._poll_queue()
        self.root.mainloop()

    def _poll_queue(self):
        try:
            while True:
                msg_type, data = ui_queue.get_nowait()
                if msg_type == "text":
                    self.label.config(text=data, fg="white")
                elif msg_type == "agent":
                    self.label.config(text=data, fg="#00ccff") # Blue for agent
                elif msg_type == "status":
                    color_map = {
                        "idle": "gray",
                        "listening": "#00ff00", # Green
                        "processing": "yellow",
                        "agent": "#00ccff", # Blue
                        "sleep": "#202020" 
                    }
                    col = color_map.get(data, "gray")
                    self.status_frame.config(bg=col)
        except queue.Empty:
            pass
        
        if not self.stop_event.is_set():
            self.root.after(50, self._poll_queue)

# Global Instance
monitor = OverlayUI()
