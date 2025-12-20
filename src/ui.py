import tkinter as tk
from tkinter import font
import queue
import threading
import time

# Thread-safe communication
ui_queue = queue.Queue()

class GenericPanel:
    """Base class for panels to ensure consistent behavior"""
    def __init__(self, root, title, bg_color, alpha=0.60):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.title(title)
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.bg_color = bg_color
        self.visible = True
        
        self.window.configure(bg=self.bg_color)
        try:
            self.window.wait_visibility(self.window)
            self.window.attributes('-alpha', alpha)
        except:
            pass

    def toggle(self):
        if self.visible:
            self.window.withdraw()
            self.visible = False
        else:
            self.window.deiconify()
            self.visible = True

    def hide(self):
        self.window.withdraw()
        self.visible = False
        
    def show(self):
        self.window.deiconify()
        self.visible = True

class LogPanel(GenericPanel):
    def __init__(self, root, bg_color):
        super().__init__(root, "Dictator Log", bg_color)
        self.width = 600
        self.height = 400
        
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
        try:
            self.text.config(state="normal")
            self.text.insert("end", text + "\n")
            self.text.see("end")
            self.text.config(state="disabled")
        except Exception:
            pass # Handle window destroyed cases

class MainPanel(GenericPanel):
    def __init__(self, root, bg_color):
        super().__init__(root, "Dictator Overlay", bg_color)
        self.default_height = 80
        self.max_height = 400
        
        # Layout
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
            cursor="watch"
        )
        self.text_widget.pack(fill="both", expand=True)

        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        width = 900
        x = (screen_width - width) // 2
        
        self._update_geometry(width, self.default_height, x, screen_height)
        
    def _update_geometry(self, width, height, x, screen_height):
        y = screen_height - height - 100
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.curr_x = x
        self.curr_width = width
        self.screen_height = screen_height

    def resize_to_fit(self, content):
        try:
            lines = int(self.text_widget.index('end-1c').split('.')[0])
            line_height = 34
            calc_height = (lines * line_height) + 30
            new_height = max(self.default_height, min(calc_height, self.max_height))
            
            self._update_geometry(self.curr_width, new_height, self.curr_x, self.screen_height)
            
            if calc_height > self.max_height:
                self.text_widget.see("end")
        except:
            pass
            
    def set_text(self, text, color):
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", text)
        self.text_widget.config(fg=color)
        self.resize_to_fit(text)
        self.text_widget.config(state="disabled")
        
    def set_status(self, color):
        self.status_frame.config(bg=color)


class OverlayUI:
    def __init__(self):
        self.root = None
        self.main_panel = None
        self.log_panel = None
        
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.bg_color = "#202020"

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.root:
            self.root.quit()

    # --- API ---
    def update_text(self, text):
        ui_queue.put(("text", text))

    def update_status(self, color):
        ui_queue.put(("status", color))
        
    def show_agent_response(self, text):
        ui_queue.put(("agent", text))

    def toggle(self): # Toggle Main
        ui_queue.put(("toggle_main", None))

    def toggle_log(self): # Toggle Log
        ui_queue.put(("toggle_log", None))
        
    def hide_all(self): # Hide Both
        ui_queue.put(("hide_all", None))

    def update_log(self, text):
        ui_queue.put(("log", text))

    def _run(self):
        self.root = tk.Tk()
        self.root.withdraw() # Hide the root window!
        
        # Initialize Panels
        self.main_panel = MainPanel(self.root, self.bg_color)
        self.log_panel = LogPanel(self.root, self.bg_color)
        
        # Polling Loop
        self._poll_queue()
        self.root.mainloop()

    def _poll_queue(self):
        try:
            while True:
                msg_type, data = ui_queue.get_nowait()
                
                if msg_type == "text":
                    if self.main_panel: self.main_panel.set_text(data, "white")
                elif msg_type == "agent":
                    if self.main_panel: self.main_panel.set_text(data, "#00ccff")
                    if self.log_panel: self.log_panel.write(f"Agent: {data}")
                elif msg_type == "status":
                    self._set_status(data)
                elif msg_type == "toggle_main":
                    if self.main_panel: self.main_panel.toggle()
                elif msg_type == "toggle_log":
                    if self.log_panel: self.log_panel.toggle()
                elif msg_type == "hide_all":
                    if self.main_panel: self.main_panel.hide()
                    if self.log_panel: self.log_panel.hide()
                elif msg_type == "log":
                    if self.log_panel: self.log_panel.write(data)
                    
        except queue.Empty:
            pass
        
        if not self.stop_event.is_set():
            self.root.after(50, self._poll_queue)

    def _set_status(self, status):
        color_map = {
            "idle": "gray",
            "listening": "#00ff00",
            "processing": "yellow",
            "agent": "#00ccff",
            "sleep": "#202020" 
        }
        col = color_map.get(status, "gray")
        if self.main_panel:
            self.main_panel.set_status(col)

# Global Instance
monitor = OverlayUI()
