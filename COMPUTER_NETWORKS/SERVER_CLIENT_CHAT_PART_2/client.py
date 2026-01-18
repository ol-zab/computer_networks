import socket
import threading
import json

HOST = "127.0.0.1"
PORT = 5000


def send_json(s: socket.socket, obj: dict):
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    s.sendall(data)


def recv_loop(s: socket.socket):
    buf = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                print("\n[server disconnected]")
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("utf-8", errors="replace")

                try:
                    msg = json.loads(text)
                except json.JSONDecodeError:
                    print("\n[bad message]")
                    continue

                t = msg.get("type")
                if t == "chat":
                    print(f"\n{msg.get('from','?')}: {msg.get('message','')}")
                elif t == "chat_started":
                    print(f"\n[chat started with {msg.get('with')}]")
                elif t == "system":
                    print(f"\n* {msg.get('message','')}")
                elif t == "error":
                    print(f"\n[ERROR] {msg.get('message','')}")
                else:
                    print(f"\n{msg}")

                print("> ", end="", flush=True)
        except OSError:
            break


def main():
    username = input("Choose username: ").strip() or "guest"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        send_json(s, {"type": "join", "username": username})

        threading.Thread(target=recv_loop, args=(s,), daemon=True).start()

        while True:
            try:
                line = input("> ").strip()
                if not line:
                    continue

                if line.startswith("/chat "):
                    to = line.split(" ", 1)[1].strip()
                    send_json(s, {"type": "chat_request", "to": to})
                    continue

                if line == "/leave":
                    send_json(s, {"type": "leave_chat"})
                    continue

                if line == "/quit":
                    send_json(s, {"type": "quit"})
                    break

                # default: send chat message
                send_json(s, {"type": "chat", "message": line})

            except (BrokenPipeError, OSError):
                break


if __name__ == "__main__":
    main()
