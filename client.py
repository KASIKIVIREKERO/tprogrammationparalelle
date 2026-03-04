import base64
import json
import os
import queue
import socket
import struct
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, ttk


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


class ChatClientApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Client Chat")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)

        self.sock = None
        self.connected = False
        self.username = ""

        self.host_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.IntVar(value=5000)
        self.username_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="broadcast")

        self.incoming_queue: "queue.Queue[dict]" = queue.Queue()

        self._apply_theme()
        self._build_ui()
        self.root.after(100, self._drain_incoming)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _apply_theme(self):
        # Palette moderne avec bleu comme couleur principale
        self.colors = {
            "bg": "#f0f4f8",           # Fond gris très clair
            "surface": "#ffffff",       # Blanc pur
            "surface_light": "#e6edf5", # Bleu très clair
            "text": "#1e293b",          # Bleu nuit
            "text_secondary": "#475569", # Gris bleuté
            "accent": "#2563eb",        # Bleu vif
            "accent_hover": "#1d4ed8",  # Bleu plus foncé
            "accent_light": "#dbeafe",  # Bleu très clair pour les survols
            "success": "#059669",       # Vert
            "warning": "#d97706",       # Orange
            "danger": "#dc2626",        # Rouge
            "danger_hover": "#b91c1c",  # Rouge foncé
            "border": "#cbd5e1",        # Gris bordure
            "chat_bg": "#f8fafc",       # Fond conversation très clair
            "chat_text": "#0f172a",     # Texte conversation
            "my_message_bg": "#2563eb", # Fond message envoyé (bleu)
            "my_message_text": "#ffffff", # Texte message envoyé (blanc)
            "other_message_bg": "#f1f5f9", # Fond message reçu (gris clair)
            "other_message_text": "#1e293b", # Texte message reçu
            "private_message_bg": "#dbeafe", # Fond message privé reçu (bleu clair)
            "private_message_text": "#1e40af", # Texte message privé reçu (bleu foncé)
            "group_message_bg": "#ede9fe", # Fond message groupe (violet clair)
            "group_message_text": "#5b21b6", # Texte message groupe (violet foncé)
            "timestamp": "#64748b",      # Couleur timestamp
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
                       font=("Segoe UI", 20, "bold"))
        
        style.configure("Subtitle.TLabel",
                       background=self.colors["surface"],
                       foreground=self.colors["text_secondary"],
                       font=("Segoe UI", 11))
        
        # Buttons
        style.configure("Accent.TButton",
                       background=self.colors["accent"],
                       foreground="#ffffff",
                       borderwidth=0,
                       focuscolor="none",
                       font=("Segoe UI", 10, "bold"),
                       padding=(20, 12))
        style.map("Accent.TButton",
                 background=[("active", self.colors["accent_hover"]),
                           ("disabled", self.colors["border"])])
        
        style.configure("Danger.TButton",
                       background=self.colors["danger"],
                       foreground="#ffffff",
                       borderwidth=0,
                       focuscolor="none",
                       font=("Segoe UI", 10, "bold"),
                       padding=(20, 12))
        style.map("Danger.TButton",
                 background=[("active", self.colors["danger_hover"])])
        
        # Entry
        style.configure("TEntry",
                       fieldbackground=self.colors["surface"],
                       foreground=self.colors["text"],
                       insertcolor=self.colors["text"],
                       borderwidth=1,
                       focuscolor=self.colors["accent"],
                       padding=(12, 10),
                       relief="solid")
        style.map("TEntry",
                 fieldbackground=[("focus", self.colors["surface"])],
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
        
        # Radiobutton
        style.configure("TRadiobutton",
                       background=self.colors["surface"],
                       foreground=self.colors["text"],
                       focuscolor="none",
                       font=("Segoe UI", 10))
        style.map("TRadiobutton",
                 background=[("active", self.colors["surface"])])

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        # Header avec une touche de bleu
        header = ttk.Frame(self.root, style="Surface.TFrame", padding="20 20")
        header.grid(row=0, column=0, sticky="ew")

        # Titre avec icône bleue
        title_frame = ttk.Frame(header, style="Surface.TFrame")
        title_frame.pack(side=tk.LEFT)
        
        # Label coloré pour l'icône
        title_icon = tk.Label(
            title_frame, 
            text="💬", 
            bg=self.colors["surface"],
            fg=self.colors["accent"],
            font=("Segoe UI", 24)
        )
        title_icon.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(title_frame, text="Chat", style="Title.TLabel").pack(side=tk.LEFT)
        
        self.status_badge = tk.Label(
            header,
            text="● Hors ligne",
            bg=self.colors["surface"],
            fg=self.colors["text_secondary"],
            font=("Segoe UI", 11, "bold"),
        )
        self.status_badge.pack(side=tk.RIGHT)

        # Barre de connexion avec meilleure disposition des boutons
        toolbar = ttk.Frame(self.root, style="Surface.TFrame", padding="20 0 20 20")
        toolbar.grid(row=1, column=0, sticky="ew")
        
        # Configuration des colonnes pour un meilleur alignement
        for i in range(8):
            toolbar.columnconfigure(i, weight=1 if i in [1,3,5] else 0)

        # Serveur
        ttk.Label(toolbar, text="Serveur:", style="Subtitle.TLabel").grid(row=0, column=0, padx=(0, 8))
        host_entry = ttk.Entry(toolbar, textvariable=self.host_var, width=15)
        host_entry.grid(row=0, column=1, padx=(0, 16), sticky="ew")

        # Port
        ttk.Label(toolbar, text="Port:", style="Subtitle.TLabel").grid(row=0, column=2, padx=(0, 8))
        port_entry = ttk.Entry(toolbar, textvariable=self.port_var, width=8)
        port_entry.grid(row=0, column=3, padx=(0, 16), sticky="ew")

        # Utilisateur
        ttk.Label(toolbar, text="Utilisateur:", style="Subtitle.TLabel").grid(row=0, column=4, padx=(0, 8))
        username_entry = ttk.Entry(toolbar, textvariable=self.username_var, width=20)
        username_entry.grid(row=0, column=5, padx=(0, 20), sticky="ew")

        # Frame pour les boutons avec meilleur espacement
        button_frame = ttk.Frame(toolbar, style="Surface.TFrame")
        button_frame.grid(row=0, column=6, columnspan=2, sticky="e")

        self.connect_btn = ttk.Button(
            button_frame,
            text="🔌 Connexion",
            command=self.connect,
            style="Accent.TButton",
        )
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.disconnect_btn = ttk.Button(
            button_frame,
            text="🔌 Déconnexion",
            command=self.disconnect,
            style="Danger.TButton",
        )
        self.disconnect_btn.pack(side=tk.LEFT)

        # Panneau principal
        main_pane = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main_pane.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))

        # Panneau de gauche - Messages
        left_frame = ttk.Frame(main_pane, style="Surface.TFrame")
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        # Zone de messages avec scrolledtext
        self.messages_text = scrolledtext.ScrolledText(
            left_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            bg=self.colors["chat_bg"],
            fg=self.colors["chat_text"],
            insertbackground=self.colors["text"],
            borderwidth=1,
            relief="solid",
            padx=15,
            pady=15,
            spacing1=8,
            spacing2=4,
            spacing3=8,
            height=20
        )
        self.messages_text.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.messages_text.config(state=tk.DISABLED)
        
        # Tags pour les différents types de messages
        self.messages_text.tag_config("system", foreground=self.colors["text_secondary"], font=("Segoe UI", 10, "italic"))
        self.messages_text.tag_config("error", foreground=self.colors["danger"], font=("Segoe UI", 10, "bold"))
        self.messages_text.tag_config("timestamp", foreground=self.colors["timestamp"], font=("Segoe UI", 9))
        self.messages_text.tag_config("sender", foreground=self.colors["accent"], font=("Segoe UI", 10, "bold"))
        self.messages_text.tag_config("my_message", 
                                     foreground=self.colors["my_message_text"], 
                                     background=self.colors["my_message_bg"], 
                                     spacing2=2, 
                                     lmargin2=20,
                                     font=("Segoe UI", 11, "bold"))
        self.messages_text.tag_config("other_message", 
                                     foreground=self.colors["other_message_text"], 
                                     background=self.colors["other_message_bg"], 
                                     spacing2=2, 
                                     lmargin2=20,
                                     font=("Segoe UI", 11))
        self.messages_text.tag_config("private_message", 
                                     foreground=self.colors["private_message_text"], 
                                     background=self.colors["private_message_bg"], 
                                     spacing2=2, 
                                     lmargin2=20,
                                     font=("Segoe UI", 11))
        self.messages_text.tag_config("group_message", 
                                     foreground=self.colors["group_message_text"], 
                                     background=self.colors["group_message_bg"], 
                                     spacing2=2, 
                                     lmargin2=20,
                                     font=("Segoe UI", 11, "italic"))

        # Zone de saisie avec bouton d'envoi - BIEN VISIBLE
        input_frame = ttk.Frame(left_frame, style="Surface.TFrame")
        input_frame.grid(row=1, column=0, sticky="ew", pady=(0, 0))
        input_frame.columnconfigure(0, weight=1)

        # Champ de texte pour la saisie des messages
        self.message_entry = ttk.Entry(
            input_frame,
            font=("Segoe UI", 11)
        )
        self.message_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10), ipady=10)
        self.message_entry.bind("<Return>", lambda _: self.send_message())

        # Bouton d'envoi bien visible en bleu
        self.send_btn = ttk.Button(
            input_frame,
            text="📤 Envoyer",
            command=self.send_message,
            style="Accent.TButton",
            width=15
        )
        self.send_btn.grid(row=0, column=1, sticky="e")

        # Panneau de droite - Contrôles
        right_frame = ttk.Frame(main_pane, style="Surface.TFrame")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(2, weight=1)
        
        # Mode de chat
        mode_frame = ttk.LabelFrame(right_frame, text="Mode de chat", padding="15")
        mode_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        # Broadcast
        broadcast_frame = ttk.Frame(mode_frame, style="Surface.TFrame")
        broadcast_frame.pack(fill=tk.X, pady=3)
        ttk.Radiobutton(
            broadcast_frame,
            text="📢 Broadcast (Tous)",
            variable=self.mode_var,
            value="broadcast",
            style="TRadiobutton",
        ).pack(side=tk.LEFT)
        
        # Privé
        private_frame = ttk.Frame(mode_frame, style="Surface.TFrame")
        private_frame.pack(fill=tk.X, pady=3)
        ttk.Radiobutton(
            private_frame,
            text="🔒 Privé (1 destinataire)",
            variable=self.mode_var,
            value="private",
            style="TRadiobutton",
        ).pack(side=tk.LEFT)
        
        # Groupe
        group_frame = ttk.Frame(mode_frame, style="Surface.TFrame")
        group_frame.pack(fill=tk.X, pady=3)
        ttk.Radiobutton(
            group_frame,
            text="👥 Groupe (2+ destinataires)",
            variable=self.mode_var,
            value="group",
            style="TRadiobutton",
        ).pack(side=tk.LEFT)

        # Liste des clients
        clients_frame = ttk.LabelFrame(right_frame, text="Clients connectés", padding="15")
        clients_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        clients_frame.columnconfigure(0, weight=1)
        clients_frame.rowconfigure(1, weight=1)

        header_frame = ttk.Frame(clients_frame, style="Surface.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(
            header_frame,
            text="👤 Disponibles",
            style="Subtitle.TLabel",
            font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.LEFT)

        self.client_count = ttk.Label(header_frame, text="(0)", style="Subtitle.TLabel")
        self.client_count.pack(side=tk.LEFT, padx=(5, 0))

        listbox_frame = ttk.Frame(clients_frame, style="Surface.TFrame")
        listbox_frame.grid(row=1, column=0, sticky="nsew")
        listbox_frame.columnconfigure(0, weight=1)
        listbox_frame.rowconfigure(0, weight=1)

        self.targets_listbox = tk.Listbox(
            listbox_frame,
            selectmode=tk.MULTIPLE,
            bg=self.colors["surface_light"],
            fg=self.colors["text"],
            selectbackground=self.colors["accent"],
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            borderwidth=0,
            font=("Segoe UI", 11),
            activestyle="none",
            relief="flat",
            height=12
        )
        self.targets_listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(listbox_frame, command=self.targets_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.targets_listbox.config(yscrollcommand=scrollbar.set)

        # Instructions avec fond bleu clair
        instructions_frame = tk.Frame(
            clients_frame, 
            bg=self.colors["accent_light"],
            padx=10,
            pady=8
        )
        instructions_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        ttk.Label(
            instructions_frame,
            text="💡 Sélectionnez des destinataires :",
            style="Subtitle.TLabel",
            background=self.colors["accent_light"],
            foreground=self.colors["accent"],
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        
        ttk.Label(
            instructions_frame,
            text="• Mode privé : 1 sélection\n• Mode groupe : 2+ sélections\n• Mode broadcast : aucune sélection",
            style="Subtitle.TLabel",
            background=self.colors["accent_light"],
            foreground=self.colors["text"],
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(5, 0))

        main_pane.add(left_frame, weight=3)
        main_pane.add(right_frame, weight=1)

    def _update_client_count(self):
        count = self.targets_listbox.size()
        self.client_count.config(text=f"({count})")

    def _send_payload(self, payload: dict):
        if not self.connected or not self.sock:
            raise ConnectionError("Client non connecté.")
        raw = json.dumps(payload).encode("utf-8")
        send_packet(self.sock, raw)

    def _add_message(self, data: dict):
        """Ajoute un message formaté au widget de texte"""
        self.messages_text.config(state=tk.NORMAL)
        
        sender = data.get("sender", "?")
        text = data.get("message", "")
        timestamp = data.get("timestamp", datetime.now().strftime("%H:%M"))
        mode = data.get("mode", "broadcast")
        
        # Déterminer si c'est notre message
        is_me = (sender == self.username)
        
        # Déterminer le tag à utiliser
        if mode in ["system", "error"]:
            tag = mode
            if mode == "error":
                # Filtrer les erreurs SQL
                if "1327" in text or "Undeclared variable" in text:
                    # Logger silencieusement mais ne pas afficher
                    print(f"⚠️ Erreur SQL ignorée: {text}")
                    self.messages_text.config(state=tk.DISABLED)
                    return
            display_text = f"[{timestamp}] {text}\n"
        else:
            mode_emoji = {
                "broadcast": "📢",
                "private": "🔒",
                "group": "👥"
            }.get(mode, "💬")
            
            if is_me:
                tag = "my_message"
                display_text = f"  {mode_emoji} Moi: {text}\n"
            else:
                if mode == "private":
                    tag = "private_message"
                elif mode == "group":
                    tag = "group_message"
                else:
                    tag = "other_message"
                display_text = f"  {mode_emoji} {sender}: {text}\n"
        
        # Insérer le message
        self.messages_text.insert(tk.END, display_text, tag)
        
        self.messages_text.see(tk.END)
        self.messages_text.config(state=tk.DISABLED)

    def connect(self):
        if self.connected:
            return

        host = self.host_var.get().strip()
        port = self.port_var.get()
        username = self.username_var.get().strip()
        
        if not username:
            messagebox.showerror("Erreur", "Veuillez entrer un nom d'utilisateur.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, int(port)))

            send_packet(self.sock, json.dumps({"type": "auth", "username": username}).encode("utf-8"))
            auth_reply = json.loads(recv_packet(self.sock).decode("utf-8"))

            if auth_reply.get("type") == "auth_ok":
                self.connected = True
                self.username = username
                
                # Mise à jour UI
                self.status_badge.config(text="● Connecté", fg=self.colors["success"])
                
                self._add_message({
                    "type": "system",
                    "message": f"✅ Connecté en tant que {username}",
                    "timestamp": datetime.now().strftime("%H:%M")
                })
                
                threading.Thread(target=self._recv_loop, daemon=True).start()
            else:
                msg = auth_reply.get("message", "Authentification refusée.")
                self.sock.close()
                self.sock = None
                messagebox.showerror("Erreur", msg)
        except Exception as exc:
            messagebox.showerror("Erreur de connexion", str(exc))
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

    def disconnect(self):
        if not self.connected:
            return
        self.connected = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None
        self.status_badge.config(text="● Hors ligne", fg=self.colors["text_secondary"])
        self.targets_listbox.delete(0, tk.END)
        self._update_client_count()
        self._add_message({
            "type": "system",
            "message": "❌ Déconnecté",
            "timestamp": datetime.now().strftime("%H:%M")
        })

    def _recv_loop(self):
        try:
            while self.connected and self.sock:
                packet = recv_packet(self.sock)
                data = json.loads(packet.decode("utf-8"))
                self.incoming_queue.put(data)
        except Exception as exc:
            self.incoming_queue.put({
                "type": "error",
                "message": f"Connexion perdue: {exc}",
                "timestamp": datetime.now().strftime("%H:%M")
            })
        finally:
            self.connected = False
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

    def _drain_incoming(self):
        while not self.incoming_queue.empty():
            data = self.incoming_queue.get_nowait()
            ptype = data.get("type")

            if ptype == "chat":
                self._add_message(data)
                
            elif ptype == "clients":
                clients = data.get("clients", [])
                self.targets_listbox.delete(0, tk.END)
                for user in clients:
                    self.targets_listbox.insert(tk.END, user)
                self._update_client_count()
                
            elif ptype == "history":
                messages = data.get("messages", [])
                if messages:
                    self._add_message({
                        "type": "system",
                        "message": "📜 Historique des messages",
                        "timestamp": datetime.now().strftime("%H:%M")
                    })
                    for item in messages:
                        self._add_message(item)
                    
            elif ptype == "error":
                # Gestion spéciale des erreurs SQL
                error_msg = data.get("message", "")
                if "1327" in error_msg or "Undeclared variable" in error_msg:
                    # Logger silencieusement sans afficher
                    print(f"🔇 Erreur SQL ignorée: {error_msg}")
                else:
                    self._add_message(data)
                
            elif ptype == "system":
                self._add_message(data)
                
            elif ptype == "pong":
                pass

        self.root.after(100, self._drain_incoming)

    def send_message(self):
        if not self.connected:
            messagebox.showwarning("Info", "Connectez-vous d'abord.")
            return

        text = self.message_entry.get().strip()
        if not text:
            return

        mode = self.mode_var.get()
        selected_indexes = self.targets_listbox.curselection()
        selected_users = [self.targets_listbox.get(i) for i in selected_indexes]

        if mode == "private" and len(selected_users) != 1:
            messagebox.showwarning("Routage", "En mode privé, sélectionnez exactement un destinataire.")
            return
            
        if mode == "group" and len(selected_users) < 2:
            messagebox.showwarning("Routage", "En mode groupé, sélectionnez au moins deux destinataires.")
            return

        payload = {
            "type": "chat",
            "mode": mode,
            "targets": selected_users,
            "message": text,
        }

        try:
            self._send_payload(payload)
            
            # Afficher le message immédiatement
            self._add_message({
                "type": "chat",
                "sender": self.username,
                "mode": mode,
                "message": text,
                "timestamp": datetime.now().strftime("%H:%M")
            })
            
            self.message_entry.delete(0, tk.END)
            
        except Exception as exc:
            messagebox.showerror("Erreur d'envoi", str(exc))

    def on_close(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClientApp(root)
    root.mainloop()