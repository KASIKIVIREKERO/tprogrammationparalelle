import base64
import json
import os
import queue
import socket
import struct
import threading
import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk

import mysql.connector


def send_packet(sock: socket.socket, data: bytes) -> None:
    sock.sendall(struct.pack("!I", len(data)) + data)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    buf = b""
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise ConnectionError("Connexion fermée.")
        buf += chunk
    return buf


def recv_packet(sock: socket.socket) -> bytes:
    header = recv_exact(sock, 4)
    (size,) = struct.unpack("!I", header)
    return recv_exact(sock, size)


class ChatServerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Serveur de Chat - Administration")
        self.root.geometry("1300x800")
        self.root.minsize(1000, 700)

        self.host_var = tk.StringVar(value="0.0.0.0")
        self.port_var = tk.IntVar(value=5000)
        self.status_var = tk.StringVar(value="Serveur arrêté")

        self.server_socket = None
        self.running = False
        self.clients = {}  # username -> socket
        self.client_locks = {}  # username -> lock for socket write
        self.clients_lock = threading.Lock()

        self.db_conn = None
        self.db_lock = threading.Lock()
        self.history_limit = int(os.getenv("CHAT_HISTORY_LIMIT", "100"))

        self.log_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self._apply_theme()
        self._build_ui()
        self._connect_db()
        self.root.after(100, self._drain_logs)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _apply_theme(self):
        # Palette moderne et élégante - Thème "Nord" style
        self.colors = {
            "bg": "#2E3440",           # Nord 0 (gris foncé)
            "surface": "#3B4252",       # Nord 1 (gris plus clair)
            "surface_light": "#434C5E", # Nord 2 (gris encore plus clair)
            "text": "#ECEFF4",          # Nord 6 (blanc cassé)
            "text_secondary": "#D8DEE9", # Nord 4 (gris très clair)
            "accent": "#88C0D0",        # Nord 8 (bleu glacier)
            "accent_hover": "#81A1C1",  # Nord 9 (bleu plus foncé)
            "success": "#A3BE8C",       # Nord 14 (vert)
            "warning": "#EBCB8B",       # Nord 13 (jaune)
            "danger": "#BF616A",        # Nord 11 (rouge)
            "danger_hover": "#D08770",  # Nord 12 (orange)
            "border": "#4C566A",        # Nord 3 (gris bordure)
            "log_bg": "#2E3440",        # Fond journal
            "log_text": "#ECEFF4",      # Texte journal
            "highlight": "#5E81AC",     # Nord 10 (bleu)
        }
        
        self.root.configure(bg=self.colors["bg"])
        
        style = ttk.Style()
        style.theme_use("clam")
        
        # Configuration globale
        style.configure(".", 
                       background=self.colors["surface"],
                       foreground=self.colors["text"],
                       font=("Segoe UI", 10),
                       relief="flat",
                       borderwidth=0)
        
        # Frames
        style.configure("Surface.TFrame", 
                       background=self.colors["surface"])
        style.configure("Header.TFrame", 
                       background=self.colors["surface"])
        
        # Labels
        style.configure("Title.TLabel",
                       background=self.colors["surface"],
                       foreground=self.colors["text"],
                       font=("Segoe UI", 18, "bold"))
        
        style.configure("Subtitle.TLabel",
                       background=self.colors["surface"],
                       foreground=self.colors["text_secondary"],
                       font=("Segoe UI", 11))
        
        style.configure("Status.TLabel",
                       background=self.colors["surface"],
                       foreground=self.colors["text_secondary"],
                       font=("Segoe UI", 11))
        
        # Buttons
        style.configure("Success.TButton",
                       background=self.colors["success"],
                       foreground=self.colors["bg"],
                       borderwidth=0,
                       focuscolor="none",
                       font=("Segoe UI", 10, "bold"),
                       padding=(20, 10))
        style.map("Success.TButton",
                 background=[("active", "#8FBCBB"),
                           ("disabled", self.colors["border"])])
        
        style.configure("Danger.TButton",
                       background=self.colors["danger"],
                       foreground=self.colors["text"],
                       borderwidth=0,
                       focuscolor="none",
                       font=("Segoe UI", 10, "bold"),
                       padding=(20, 10))
        style.map("Danger.TButton",
                 background=[("active", self.colors["danger_hover"])])
        
        style.configure("Accent.TButton",
                       background=self.colors["accent"],
                       foreground=self.colors["bg"],
                       borderwidth=0,
                       focuscolor="none",
                       font=("Segoe UI", 10, "bold"),
                       padding=(16, 8))
        style.map("Accent.TButton",
                 background=[("active", self.colors["accent_hover"])])
        
        # Entry
        style.configure("TEntry",
                       fieldbackground=self.colors["surface_light"],
                       foreground=self.colors["text"],
                       insertcolor=self.colors["text"],
                       borderwidth=1,
                       focuscolor=self.colors["accent"],
                       padding=(12, 8),
                       relief="solid")
        style.map("TEntry",
                 fieldbackground=[("focus", self.colors["surface_light"])],
                 bordercolor=[("focus", self.colors["accent"])])
        
        # Labelframe
        style.configure("TLabelframe",
                       background=self.colors["surface"],
                       foreground=self.colors["text"],
                       bordercolor=self.colors["border"],
                       borderwidth=1,
                       relief="solid")
        style.configure("TLabelframe.Label",
                       background=self.colors["surface"],
                       foreground=self.colors["accent"],
                       font=("Segoe UI", 12, "bold"))

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        # Header avec style épuré
        header = ttk.Frame(self.root, style="Surface.TFrame", padding="20 20")
        header.grid(row=0, column=0, sticky="ew")

        # Logo et titre avec séparateur
        title_frame = ttk.Frame(header, style="Surface.TFrame")
        title_frame.pack(side=tk.LEFT)

        ttk.Label(title_frame, text="⚡", style="Title.TLabel", font=("Segoe UI", 24)).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(title_frame, text="ADMIN", style="Title.TLabel").pack(side=tk.LEFT)
        
        # Séparateur vertical
        separator = tk.Frame(header, width=1, bg=self.colors["border"])
        separator.pack(side=tk.LEFT, padx=20, fill=tk.Y)

        # Stats rapides
        stats_frame = ttk.Frame(header, style="Surface.TFrame")
        stats_frame.pack(side=tk.LEFT)
        
        self.uptime_label = ttk.Label(stats_frame, text="🕐 Arrêté", style="Status.TLabel")
        self.uptime_label.pack(side=tk.LEFT, padx=(0, 15))

        # Status badge
        self.status_badge = tk.Label(
            header,
            text="⛔ OFFLINE",
            bg=self.colors["surface"],
            fg=self.colors["text_secondary"],
            font=("Segoe UI", 11, "bold"),
        )
        self.status_badge.pack(side=tk.RIGHT)

        # Panneau de contrôle compact
        control_frame = ttk.Frame(self.root, style="Surface.TFrame", padding="20 0 20 20")
        control_frame.grid(row=1, column=0, sticky="ew")
        
        # Grille de contrôle
        control_grid = ttk.Frame(control_frame, style="Surface.TFrame")
        control_grid.pack(fill=tk.X)
        
        # Configuration réseau
        network_frame = ttk.Frame(control_grid, style="Surface.TFrame")
        network_frame.pack(side=tk.LEFT)

        ttk.Label(network_frame, text="Interface", style="Subtitle.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        host_entry = ttk.Entry(network_frame, textvariable=self.host_var, width=15)
        host_entry.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(network_frame, text="Port", style="Subtitle.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        port_entry = ttk.Entry(network_frame, textvariable=self.port_var, width=8)
        port_entry.pack(side=tk.LEFT, padx=(0, 20))

        # Boutons
        self.start_btn = ttk.Button(
            control_grid,
            text="DÉMARRER",
            command=self.start_server,
            style="Success.TButton",
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = ttk.Button(
            control_grid,
            text="ARRÊTER",
            command=self.stop_server,
            style="Danger.TButton",
        )
        self.stop_btn.pack(side=tk.LEFT)

        # Zone principale avec design en cartes
        main_container = ttk.Frame(self.root, style="Surface.TFrame", padding="20 0 20 20")
        main_container.grid(row=2, column=0, sticky="nsew")
        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=2)
        main_container.rowconfigure(0, weight=1)

        # Carte Clients (gauche)
        clients_card = ttk.Frame(main_container, style="Surface.TFrame")
        clients_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # En-tête de carte
        clients_header = ttk.Frame(clients_card, style="Surface.TFrame")
        clients_header.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(clients_header, text="👥 CONNECTÉS", style="Subtitle.TLabel", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        
        self.client_count = tk.Label(
            clients_header,
            text="0",
            bg=self.colors["accent"],
            fg=self.colors["bg"],
            font=("Segoe UI", 12, "bold"),
            padx=12,
            pady=2,
        )
        self.client_count.pack(side=tk.RIGHT)

        # Liste des clients avec style
        clients_list_frame = ttk.Frame(clients_card, style="Surface.TFrame")
        clients_list_frame.pack(fill=tk.BOTH, expand=True)

        self.clients_listbox = tk.Listbox(
            clients_list_frame,
            bg=self.colors["surface_light"],
            fg=self.colors["text"],
            selectbackground=self.colors["highlight"],
            selectforeground=self.colors["text"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            borderwidth=0,
            font=("Segoe UI", 11),
            activestyle="none",
            relief="flat",
        )
        self.clients_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        clients_scroll = ttk.Scrollbar(clients_list_frame, command=self.clients_listbox.yview)
        clients_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.clients_listbox.config(yscrollcommand=clients_scroll.set)

        # Carte Journal (droite)
        log_card = ttk.Frame(main_container, style="Surface.TFrame")
        log_card.grid(row=0, column=1, sticky="nsew")
        
        # En-tête de carte avec contrôles
        log_header = ttk.Frame(log_card, style="Surface.TFrame")
        log_header.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(log_header, text="📋 JOURNAL", style="Subtitle.TLabel", font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        
        # Bouton pour effacer le journal
        clear_btn = ttk.Button(
            log_header,
            text="Effacer",
            command=self._clear_logs,
            style="Accent.TButton",
        )
        clear_btn.pack(side=tk.RIGHT)

        # Zone de journal
        log_frame = ttk.Frame(log_card, style="Surface.TFrame")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            log_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg=self.colors["surface_light"],
            fg=self.colors["log_text"],
            insertbackground=self.colors["text"],
            borderwidth=0,
            font=("Consolas", 11),
            padx=15,
            pady=15,
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scroll.set)

        # Configuration des tags pour le journal
        self.log_text.tag_config("info", foreground=self.colors["text"])
        self.log_text.tag_config("success", foreground=self.colors["success"])
        self.log_text.tag_config("warning", foreground=self.colors["warning"])
        self.log_text.tag_config("error", foreground=self.colors["danger"])
        self.log_text.tag_config("connect", foreground=self.colors["accent"])
        self.log_text.tag_config("disconnect", foreground=self.colors["warning"])

        # Barre d'état avec infos DB
        status_bar = ttk.Frame(self.root, style="Surface.TFrame", padding="20 10")
        status_bar.grid(row=3, column=0, sticky="ew")

        self.db_status = tk.Label(
            status_bar,
            text="● Base de données: Connexion...",
            bg=self.colors["surface"],
            fg=self.colors["text_secondary"],
            font=("Segoe UI", 10),
        )
        self.db_status.pack(side=tk.LEFT)

    def _connect_db(self):
        try:
            self.db_conn = mysql.connector.connect(
                host=os.getenv("MYSQL_HOST", "127.0.0.1"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "chat_db"),
                autocommit=True,
            )
            with self.db_lock:
                cursor = self.db_conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        sent_at DATETIME NOT NULL,
                        sender VARCHAR(64) NOT NULL,
                        mode VARCHAR(16) NOT NULL,
                        recipients TEXT NOT NULL,
                        message_text TEXT NOT NULL
                    )
                    """
                )
                cursor.close()
            self.db_status.config(text="● Base de données: Connectée", fg=self.colors["success"])
            self._log("✅ Base MySQL connectée avec succès.", "success")
        except Exception as exc:
            self.db_status.config(text=f"● Base de données: Erreur", fg=self.colors["danger"])
            self._log(f"❌ Erreur MySQL: {exc}", "error")

    def _save_message(self, sender: str, mode: str, recipients: list, content: str):
        if not self.db_conn:
            self._log("⚠️ MySQL non disponible: message non persisté.", "warning")
            return
        try:
            with self.db_lock:
                cursor = self.db_conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO chat_messages (sent_at, sender, mode, recipients, message_text)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (datetime.now(), sender, mode, ",".join(recipients), content),
                )
                cursor.close()
        except Exception as exc:
            self._log(f"❌ Erreur insertion MySQL: {exc}", "error")

    def _get_history_for_user(self, username: str) -> list[dict]:
        """Récupère l'historique des messages pour un utilisateur"""
        if not self.db_conn:
            return []
        items = []
        try:
            with self.db_lock:
                cursor = self.db_conn.cursor()
                # Requête corrigée - plus de variable non déclarée
                cursor.execute(
                    """
                    SELECT sent_at, sender, mode, recipients, message_text
                    FROM chat_messages
                    WHERE sender = %s OR mode = 'broadcast' OR FIND_IN_SET(%s, recipients)
                    ORDER BY sent_at DESC
                    LIMIT %s
                    """,
                    (username, username, self.history_limit),
                )
                rows = list(reversed(cursor.fetchall()))
                cursor.close()
                
            for sent_at, sender, mode, recipients_raw, message_text in rows:
                recipients = [u.strip() for u in (recipients_raw or "").split(",") if u.strip()]
                items.append(
                    {
                        "sender": sender,
                        "mode": mode,
                        "targets": recipients,
                        "message": message_text,
                        "timestamp": sent_at.strftime("%H:%M:%S") if hasattr(sent_at, "strftime") else str(sent_at),
                    }
                )
        except mysql.connector.Error as exc:
            self._log(f"❌ Erreur MySQL lecture historique pour {username}: {exc}", "error")
        except Exception as exc:
            self._log(f"❌ Erreur lecture historique pour {username}: {exc}", "error")
        return items

    def _log(self, message: str, tag: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put((f"[{timestamp}] {message}", tag))

    def _drain_logs(self):
        while not self.log_queue.empty():
            line, tag = self.log_queue.get_nowait()
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, line + "\n", tag)
            self.log_text.config(state=tk.DISABLED)
            self.log_text.see(tk.END)
        self.root.after(100, self._drain_logs)

    def _clear_logs(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self._log("📋 Journal effacé", "info")

    def _refresh_clients_ui(self):
        self.clients_listbox.delete(0, tk.END)
        with self.clients_lock:
            for user in sorted(self.clients.keys()):
                self.clients_listbox.insert(tk.END, f"  {user}")
        
        count = len(self.clients)
        self.client_count.config(text=str(count))

    def start_server(self):
        if self.running:
            return
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host_var.get(), self.port_var.get()))
            self.server_socket.listen(50)
            self.running = True
            
            host = self.host_var.get()
            port = self.port_var.get()
            display_host = "0.0.0.0" if host == "0.0.0.0" else host
            
            self.status_var.set(f"Serveur actif sur {display_host}:{port}")
            self.status_badge.config(text="🟢 ONLINE", fg=self.colors["success"])
            self.uptime_label.config(text=f"🕐 {datetime.now().strftime('%H:%M:%S')}")
            
            threading.Thread(target=self._accept_loop, daemon=True).start()
            self._log(f"🚀 Serveur démarré sur {display_host}:{port}", "success")
        except Exception as exc:
            self._log(f"❌ Impossible de démarrer le serveur: {exc}", "error")

    def stop_server(self):
        if not self.running:
            return
        self.running = False
        
        host = self.host_var.get()
        port = self.port_var.get()
        display_host = "0.0.0.0" if host == "0.0.0.0" else host
        
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception:
            pass

        with self.clients_lock:
            for username, sock in list(self.clients.items()):
                try:
                    self._send_plain(sock, {"type": "system", "message": "Serveur arrêté."}, username)
                    sock.close()
                except Exception:
                    pass
            self.clients.clear()
            self.client_locks.clear()

        self._refresh_clients_ui()
        self.status_var.set("Serveur arrêté")
        self.status_badge.config(text="⛔ OFFLINE", fg=self.colors["text_secondary"])
        self.uptime_label.config(text="🕐 Arrêté")
        self._log(f"🛑 Serveur arrêté sur {display_host}:{port}", "warning")

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True).start()
            except OSError:
                break
            except Exception as exc:
                self._log(f"❌ Erreur accept(): {exc}", "error")

    def _send_plain(self, sock: socket.socket, payload: dict, username: str | None = None):
        encoded = json.dumps(payload).encode("utf-8")
        if username and username in self.client_locks:
            with self.client_locks[username]:
                send_packet(sock, encoded)
        else:
            send_packet(sock, encoded)

    def _broadcast_clients_list(self):
        with self.clients_lock:
            usernames = sorted(self.clients.keys())
            snapshot = list(self.clients.items())
        for user, sock in snapshot:
            try:
                self._send_plain(sock, {"type": "clients", "clients": [u for u in usernames if u != user]}, user)
            except Exception as exc:
                self._log(f"❌ Erreur envoi liste clients à {user}: {exc}", "error")

    def _disconnect(self, username: str):
        with self.clients_lock:
            sock = self.clients.pop(username, None)
            self.client_locks.pop(username, None)
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        self._refresh_clients_ui()
        self._broadcast_clients_list()
        self._log(f"👋 {username} déconnecté.", "disconnect")

    def _route_message(self, sender: str, mode: str, targets: list, text: str):
        delivered_to = []
        with self.clients_lock:
            clients_snapshot = dict(self.clients)

        if mode == "broadcast":
            recipients = [u for u in clients_snapshot if u != sender]
        elif mode == "private":
            recipients = targets[:1]
        elif mode == "group":
            recipients = [u for u in targets if u != sender]
        else:
            recipients = []

        message = {
            "type": "chat",
            "sender": sender,
            "mode": mode,
            "targets": recipients,
            "message": text,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }

        for user in recipients:
            sock = clients_snapshot.get(user)
            if not sock:
                continue
            try:
                self._send_plain(sock, message, user)
                delivered_to.append(user)
            except Exception as exc:
                self._log(f"❌ Erreur envoi vers {user}: {exc}", "error")

        self._save_message(sender, mode, delivered_to, text)

    def _handle_client(self, client_sock: socket.socket, addr):
        username = None
        try:
            raw = recv_packet(client_sock)
            auth = json.loads(raw.decode("utf-8"))
            if auth.get("type") != "auth":
                raise ValueError("Paquet d'authentification invalide.")

            username = auth.get("username", "").strip()
            if not username:
                raise ValueError("Nom d'utilisateur vide.")

            with self.clients_lock:
                if username in self.clients:
                    self._send_plain(client_sock, {"type": "error", "message": "Nom déjà utilisé."})
                    client_sock.close()
                    return
                self.clients[username] = client_sock
                self.client_locks[username] = threading.Lock()

            self._send_plain(client_sock, {"type": "auth_ok", "message": f"Bienvenue {username}"}, username)
            history = self._get_history_for_user(username)
            self._send_plain(client_sock, {"type": "history", "messages": history}, username)
            self._log(f"🔌 {username} connecté depuis {addr[0]}:{addr[1]}", "connect")
            self._refresh_clients_ui()
            self._broadcast_clients_list()

            while self.running:
                raw = recv_packet(client_sock)
                payload = json.loads(raw.decode("utf-8"))
                ptype = payload.get("type")

                if ptype == "chat":
                    mode = payload.get("mode", "broadcast")
                    targets = payload.get("targets", [])
                    text = payload.get("message", "").strip()
                    if text:
                        self._route_message(username, mode, targets, text)
                elif ptype == "ping":
                    self._send_plain(client_sock, {"type": "pong"}, username)
                else:
                    self._log(f"⚠️ Type inconnu depuis {username}: {ptype}", "warning")

        except ConnectionError:
            pass
        except Exception as exc:
            self._log(f"❌ Erreur client {username or addr}: {exc}", "error")
            try:
                self._send_plain(client_sock, {"type": "error", "message": str(exc)}, username)
            except Exception:
                pass
        finally:
            if username:
                self._disconnect(username)
            else:
                try:
                    client_sock.close()
                except Exception:
                    pass

    def on_close(self):
        self.stop_server()
        try:
            if self.db_conn:
                self.db_conn.close()
                self._log("📊 Déconnexion de la base de données", "info")
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ChatServerApp(root)
    root.mainloop()