import socket
import threading
import json

HOST = "127.0.0.1"
PORT = 5000

lock = threading.Lock()

# username -> conn
users: dict[str, socket.socket] = {}

# conn -> username
user_of: dict[socket.socket, str] = {}

# conn -> partner_conn (if in private chat)
partner: dict[socket.socket, socket.socket] = {}


def send_json(conn: socket.socket, obj: dict):
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    conn.sendall(data)


def recv_lines(conn: socket.socket):
    buf = b""
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            return
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            yield line.decode("utf-8", errors="replace")


def safe_close_chat(conn: socket.socket, reason: str = "chat ended"):
    """Break pairing for conn (and notify the other side)."""
    with lock:
        other = partner.pop(conn, None)
        if other is not None:
            partner.pop(other, None)

    if other is not None:
        try:
            send_json(other, {"type": "system", "message": reason})
        except OSError:
            pass


def handle_client(conn: socket.socket, addr):
    graceful = False
    username = None
    try:
        it = recv_lines(conn)

        first = next(it, None)
        if first is None:
            return

        try:
            msg = json.loads(first)
        except json.JSONDecodeError:
            send_json(conn, {"type": "error", "message": "Invalid JSON"})
            return

        if msg.get("type") != "join" or not msg.get("username"):
            send_json(conn, {"type": "error", "message": "First message must be join with username"})
            return

        username = str(msg["username"]).strip()
        if not username:
            send_json(conn, {"type": "error", "message": "Empty username"})
            return

        # register username
        with lock:
            if username in users:
                send_json(conn, {"type": "error", "message": "Username already taken"})
                return
            users[username] = conn
            user_of[conn] = username

        print(f"[+] {username} connected from {addr}")
        send_json(conn, {"type": "system", "message": f"Welcome {username}! Use /chat <name> to start."})

        for line in it:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                send_json(conn, {"type": "error", "message": "Invalid JSON"})
                continue

            t = msg.get("type")

            if t == "chat_request":
                target = str(msg.get("to", "")).strip()
                if not target:
                    send_json(conn, {"type": "error", "message": "Missing 'to' username"})
                    continue

                with lock:
                    me = conn
                    me_name = user_of.get(me, "unknown")
                    target_conn = users.get(target)

                    if target_conn is None:
                        send_json(conn, {"type": "error", "message": f"{target} is not online"})
                        continue

                    if target_conn is me:
                        send_json(conn, {"type": "error", "message": "You cannot chat with yourself"})
                        continue

                    if me in partner:
                        send_json(conn, {"type": "error", "message": "You are already in a chat. Use /leave first."})
                        continue

                    if target_conn in partner:
                        send_json(conn, {"type": "error", "message": f"{target} is busy"})
                        continue

                    # pair them
                    partner[me] = target_conn
                    partner[target_conn] = me

                send_json(conn, {"type": "chat_started", "with": target})
                try:
                    send_json(target_conn, {"type": "chat_started", "with": me_name})
                except OSError:
                    # if sending failed, undo pairing
                    safe_close_chat(conn, reason="chat ended (peer disconnected)")
                continue

            if t == "leave_chat":
                safe_close_chat(conn, reason="peer left the chat")
                send_json(conn, {"type": "system", "message": "You left the chat"})
                continue

            if t == "chat":
                text = str(msg.get("message", ""))
                if not text.strip():
                    continue

                with lock:
                    other = partner.get(conn)
                    me_name = user_of.get(conn, "unknown")

                if other is None:
                    send_json(conn, {"type": "error", "message": "You are not in a private chat. Use /chat <name>."})
                    continue

                # deliver only to partner
                try:
                    send_json(other, {"type": "chat", "from": me_name, "message": text})
                except OSError:
                    safe_close_chat(conn, reason="chat ended (peer disconnected)")
                    send_json(conn, {"type": "error", "message": "Peer disconnected"})
                continue

            if t == "quit":
                graceful = True
                break

            send_json(conn, {"type": "error", "message": "Unknown message type"})

    except (ConnectionResetError, OSError):
        pass
    finally:

    # cleanup
     safe_close_chat(conn, reason="peer disconnected")

    with lock:
        if username and users.get(username) is conn:
            users.pop(username, None)
        user_of.pop(conn, None)

      # logging: graceful vs unexpected
    if username:
        if graceful:
            print(f"[-] {username} disconnected (graceful)")
        else:
            print(f"[!] {username} disconnected (unexpected)")
    else:
        # if we didn't finish join(), still log something useful
        if not graceful:
            print(f"[!] disconnect from {addr} (before join)")

    # close socket
    try:
        conn.close()
    except OSError:
        pass


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
