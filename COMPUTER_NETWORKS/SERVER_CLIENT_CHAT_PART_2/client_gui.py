import socket
import threading
import json
import tkinter as tk
from tkinter import scrolledtext, messagebox

HOST = "127.0.0.1"
PORT = 5000


class ChatGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Chat Client")

        # --- Top: connect controls ---
        top = tk.Frame(root)
        top.pack(fill="x", padx=8, pady=6)

        tk.Label(top, text="Username:").pack(side="left")
        self.username_entry = tk.Entry(top, width=18)
        self.username_entry.pack(side="left", padx=6)
        self.username_entry.insert(0, "alice")

        self.connect_btn = tk.Button(top, text="Connect", command=self.connect)
        self.connect_btn.pack(side="left", padx=6)

        self.status_var = tk.StringVar(value="Disconnected")
        tk.Label(top, textvariable=self.status_var).pack(side="left", padx=10)

        # --- Chat display ---
        self.chat_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=18, state="disabled")
        self.chat_box.pack(fill="both", expand=True, padx=8, pady=6)

        # --- Chat target controls ---
        mid = tk.Frame(root)
        mid.pack(fill="x", padx=8, pady=4)

        tk.Label(mid, text="Chat with:").pack(side="left")
        self.to_entry = tk.Entry(mid, width=18)
        self.to_entry.pack(side="left", padx=6)

        self.chat_btn = tk.Button(mid, text="Start Chat", command=self.start_chat, state="disabled")
        self.chat_btn.pack(side="left", padx=6)

        self.leave_btn = tk.Button(mid, text="Leave Chat", command=self.leave_chat, state="disabled")
        self.leave_btn.pack(side="left", padx=6)

        # --- Bottom: message input ---
        bottom = tk.Frame(root)
        bottom.pack(fill="x", padx=8, pady=8)

        self.msg_entry = tk.Entry(bottom)
        self.msg_entry.pack(side="left", fill="x", expand=True)
        self.msg_entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = tk.Button(bottom, text="Send", command=self.send_message, state="disabled")
        self.send_btn.pack(side="left", padx=6)

        self.quit_btn = tk.Button(bottom, text="Quit", command=self.quit_app)
        self.quit_btn.pack(side="left")

        # --- Networking state ---
        self.sock: socket.socket | None = None
        self.recv_thread: threading.Thread | None = None
        self.connected = False

        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)

    # ---------- UI helpers ----------
    def log(self, text: str):
        self.chat_box.configure(state="normal")
        self.chat_box.insert(tk.END, text + "\n")
        self.chat_box.see(tk.END)
        self.chat_box.configure(state="disabled")

    def set_connected_ui(self, is_connected: bool):
        self.connected = is_connected
        self.connect_btn.configure(state=("disabled" if is_connected else "normal"))
        self.chat_btn.configure(state=("normal" if is_connected else "disabled"))
        self.leave_btn.configure(state=("normal" if is_connected else "disabled"))
        self.send_btn.configure(state=("normal" if is_connected else "disabled"))
        self.status_var.set("Connected" if is_connected else "Disconnected")

    # ---------- JSON lines ----------
    def send_json(self, obj: dict):
        if not self.sock:
            return
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        self.sock.sendall(data)

    def recv_loop(self):
        buf = b""
        try:
            while self.sock:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self.root.after(0, lambda: self.on_disconnected("Server disconnected"))
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace")
                    try:
                        msg = json.loads(text)
                    except json.JSONDecodeError:
                        self.root.after(0, lambda: self.log("[bad message from server]"))
                        continue
                    self.root.after(0, lambda m=msg: self.handle_server_msg(m))
        except OSError:
            self.root.after(0, lambda: self.on_disconnected("Connection closed"))

    def handle_server_msg(self, msg: dict):
        t = msg.get("type")
        if t == "chat":
            self.log(f'{msg.get("from","?")}: {msg.get("message","")}')
        elif t == "chat_started":
            self.log(f'[chat started with {msg.get("with")}]')
        elif t == "system":
            self.log(f'* {msg.get("message","")}')
        elif t == "error":
            self.log(f'[ERROR] {msg.get("message","")}')
        else:
            self.log(str(msg))

    # ---------- Actions ----------
    def connect(self):
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showerror("Error", "Username is required")
            return

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((HOST, PORT))
            self.sock = s
            self.send_json({"type": "join", "username": username})
        except OSError as e:
            messagebox.showerror("Connection error", str(e))
            try:
                if self.sock:
                    self.sock.close()
            except OSError:
                pass
            self.sock = None
            return

        self.set_connected_ui(True)
        self.log(f"[connected as {username}]")

        self.recv_thread = threading.Thread(target=self.recv_loop, daemon=True)
        self.recv_thread.start()

    def start_chat(self):
        to = self.to_entry.get().strip()
        if not to:
            messagebox.showerror("Error", "Enter a username to chat with")
            return
        try:
            self.send_json({"type": "chat_request", "to": to})
        except OSError as e:
            self.on_disconnected(str(e))

    def leave_chat(self):
        try:
            self.send_json({"type": "leave_chat"})
        except OSError as e:
            self.on_disconnected(str(e))

    def send_message(self):
        text = self.msg_entry.get().strip()
        if not text:
            return
        self.msg_entry.delete(0, tk.END)
        try:
            self.send_json({"type": "chat", "message": text})
            # Optional: show your own messages in the UI
            self.log(f"me: {text}")
        except OSError as e:
            self.on_disconnected(str(e))

    def on_disconnected(self, reason: str):
        if self.connected:
            self.log(f"[disconnected] {reason}")
        self.set_connected_ui(False)
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.sock = None

    def quit_app(self):
        try:
            if self.sock:
                try:
                    self.send_json({"type": "quit"})
                except OSError:
                    pass
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    self.sock.close()
                except OSError:
                    pass
        finally:
            self.sock = None
            self.root.destroy()


def main():
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
