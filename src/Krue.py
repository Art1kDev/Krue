import socket
import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime
import os
from PIL import Image, ImageTk, ImageOps
import io
import struct

class DeveloperInfoWindow(ctk.CTkToplevel):
    def __init__(self, parent, theme):
        super().__init__(parent)
        self.theme = theme
        self.title("Developers Info")
        self.geometry("300x200")
        self.resizable(False, False)
        self.grab_set()

        t = parent.themes[theme]
        self.configure(fg_color=t["card"], border_color=t["border"], border_width=1)

        ctk.CTkLabel(self, text="Krue Messenger", font=("Consolas", 18, "bold"), text_color=t["accent"]).pack(pady=(15, 5))
        
        ctk.CTkLabel(self, text="Version: 0.2 Build 0104", font=("Consolas", 10, "italic"), text_color=t["subtext"]).pack(pady=(0, 10))

        dev_frame = ctk.CTkFrame(self, fg_color="transparent")
        dev_frame.pack(pady=10)
        
        ctk.CTkLabel(dev_frame, text="Developers:", font=("Consolas", 12, "bold"), text_color=t["text"]).pack()
        
        ctk.CTkLabel(dev_frame, text="Mezoik", font=("Consolas", 11), text_color=t["text"]).pack()
        ctk.CTkLabel(dev_frame, text="Art1kDev", font=("Consolas", 11), text_color=t["text"]).pack()

        ctk.CTkButton(self, text="Close", command=self.destroy, fg_color=t["accent"], hover_color=parent.darken(t["accent"])).pack(pady=(10, 15))


class AvatarCropper(ctk.CTkToplevel):
    def __init__(self, parent, image_path):
        super().__init__(parent)
        self.parent = parent
        self.original_image = Image.open(image_path).convert("RGBA")
        self.title("Crop Avatar")
        self.geometry("400x500")
        self.resizable(False, False)
        self.grab_set()

        self.canvas_size = 350
        self.crop_display_size = 300
        
        self.canvas = ctk.CTkCanvas(self, width=self.canvas_size, height=self.canvas_size, highlightthickness=0)
        self.canvas.pack(pady=20)

        self.rect_id = None
        self.image_tk = None
        self.displayed_image = None
        self.rect_x1 = 0
        self.rect_y1 = 0
        self.offset_x = 0
        self.offset_y = 0
        
        self.display_image()

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=10)

        ctk.CTkButton(btn_frame, text="Done", command=self.crop_and_save).pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=10)

    def display_image(self):
        display_img = self.original_image.copy()
        display_img.thumbnail((self.canvas_size, self.canvas_size), Image.Resampling.LANCZOS)
        self.displayed_image = display_img
        self.image_tk = ImageTk.PhotoImage(display_img)
        self.canvas.create_image(self.canvas_size // 2, self.canvas_size // 2, image=self.image_tk)

        self.rect_x1 = (self.canvas_size - self.crop_display_size) // 2
        self.rect_y1 = (self.canvas_size - self.crop_display_size) // 2
        x2 = self.rect_x1 + self.crop_display_size
        y2 = self.rect_y1 + self.crop_display_size
        
        self.rect_id = self.canvas.create_rectangle(self.rect_x1, self.rect_y1, x2, y2, outline="#4a90e2", width=3, dash=(5, 5))

    def on_press(self, event):
        coords = self.canvas.coords(self.rect_id)
        if not coords: return
        self.offset_x = event.x - coords[0]
        self.offset_y = event.y - coords[1]

    def on_drag(self, event):
        new_x1 = event.x - self.offset_x
        new_y1 = event.y - self.offset_y

        max_coord = self.canvas_size - self.crop_display_size
        
        x1 = max(0, min(new_x1, max_coord))
        y1 = max(0, min(new_y1, max_coord))

        x2 = x1 + self.crop_display_size
        y2 = y1 + self.crop_display_size

        self.canvas.coords(self.rect_id, x1, y1, x2, y2)
        self.rect_x1 = x1
        self.rect_y1 = y1

    def crop_and_save(self):
        if not self.rect_id:
            return
            
        x1_display = self.rect_x1
        y1_display = self.rect_y1
        x2_display = self.rect_x1 + self.crop_display_size
        y2_display = self.rect_y1 + self.crop_display_size
            
        scale_x = self.original_image.width / self.displayed_image.width
        scale_y = self.original_image.height / self.displayed_image.height
        
        crop_box = (
            int(x1_display * scale_x),
            int(y1_display * scale_y),
            int(x2_display * scale_x),
            int(y2_display * scale_y)
        )
        cropped = self.original_image.crop(crop_box)
        final = cropped.resize((40, 40), Image.Resampling.LANCZOS)
        self.parent.avatar_img = final
        
        ctk_photo = ctk.CTkImage(light_image=final, dark_image=final, size=(40, 40))
        self.parent.avatar_btn.configure(image=ctk_photo, text="")
        self.parent.avatar_btn.image = ctk_photo
        
        if self.parent.messenger.client_socket:
            self.parent.send_avatar_update()
            
        self.destroy()

class Messenger:
    def __init__(self):
        self.clients = []
        self.nicknames = []
        self.avatars = {}
        self.server_socket = None
        self.client_socket = None
        self.is_server = False
        self.MAX_CLIENTS = 100

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()
        return local_ip

    def start_server(self):
        try:
            self.is_server = True
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.get_local_ip(), 55555))
            self.server_socket.listen()
            threading.Thread(target=self.accept_connections, daemon=True).start()
            return True
        except OSError:
            return False

    def accept_connections(self):
        while True:
            try:
                client, address = self.server_socket.accept()
                if len(self.clients) >= self.MAX_CLIENTS:
                    client.close()
                    continue
                threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()
            except:
                break

    def _recv_all(self, client, size):
        data = b''
        while len(data) < size:
            chunk = client.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _send_data(self, client_socket, data):
        data_len = struct.pack('>I', len(data))
        client_socket.sendall(data_len + data)

    def _send_data_to_server(self, data):
        try:
            data_len = struct.pack('>I', len(data))
            self.client_socket.sendall(data_len + data)
        except Exception:
            pass

    def handle_client(self, client):
        try:
            nick_len_data = self._recv_all(client, 4)
            if not nick_len_data: raise ConnectionResetError
            nick_len = struct.unpack('>I', nick_len_data)[0]
            
            nickname = self._recv_all(client, nick_len).decode('utf-8')
            if not nickname: raise ConnectionResetError

            avatar_len_data = self._recv_all(client, 4)
            if not avatar_len_data: raise ConnectionResetError
            avatar_len = struct.unpack('>I', avatar_len_data)[0]

            avatar_img = None
            if avatar_len > 0:
                avatar_data = self._recv_all(client, avatar_len)
                if not avatar_data: raise ConnectionResetError
                try:
                    avatar_img = Image.open(io.BytesIO(avatar_data)).resize((40, 40), Image.Resampling.LANCZOS)
                except:
                    pass
            
            self.clients.append(client)
            self.nicknames.append(nickname)
            self.avatars[client] = avatar_img
            self.broadcast(f"{nickname} joined!", system=True)
            self.broadcast_client_list_to_all()
            
            while True:
                msg_header = self._recv_all(client, 4)
                if not msg_header: break
                msg_len = struct.unpack('>I', msg_header)[0]
                msg_data = self._recv_all(client, msg_len)
                if not msg_data: break
                
                command, message = msg_data.split(b':', 1)
                command = command.decode('utf-8')
                
                if command == "MSG":
                    message = message.decode('utf-8', errors='ignore').strip()
                    if message.startswith("/p"):
                        parts = message.split(maxsplit=2)
                        if len(parts) < 3: continue
                        target_user, private_message = parts[1], parts[2]
                        self.send_private(nickname, target_user, private_message)
                    else:
                        self.broadcast(f"{nickname}: {message}")
                
                elif command == "AVATAR":
                    avatar_payload = message.decode('latin1')
                    avatar_data = avatar_payload.encode('latin1')
                    avatar_img = None
                    if avatar_data:
                        try:
                            avatar_img = Image.open(io.BytesIO(avatar_data)).resize((40, 40), Image.Resampling.LANCZOS)
                        except:
                            pass
                    self.avatars[client] = avatar_img
                    self.broadcast_avatar(client, avatar_payload)

        except Exception:
            pass
        finally:
            if client in self.clients:
                idx = self.clients.index(client)
                nickname = self.nicknames.pop(idx)
                self.clients.remove(client)
                self.avatars.pop(client, None)
                self.broadcast(f"{nickname} left!", system=True)
                self.broadcast_client_list_to_all()
                client.close()

    def connect_to_server(self, host):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, 55555))
            return True
        except:
            return False

    def send_message(self, message):
        try:
            data = f"MSG:{message}".encode('utf-8')
            self._send_data_to_server(data)
        except:
            pass
            
    def send_avatar_update(self, avatar_data):
        try:
            data = f"AVATAR:{avatar_data}".encode('latin1')
            self._send_data_to_server(data)
        except:
            pass

    def broadcast(self, message, system=False):
        for client in self.clients:
            try:
                prefix = "SYS:" if system else "MSG:"
                data = f"{prefix}{message}".encode('utf-8')
                self._send_data(client, data)
            except:
                pass

    def broadcast_avatar(self, sender_client, avatar_payload):
        for client in self.clients:
            try:
                data = f"AVATAR_UPDATE:{self.nicknames[self.clients.index(sender_client)]}:{avatar_payload}".encode('latin1')
                self._send_data(client, data)
            except:
                pass

    def broadcast_client_list_to_all(self):
        for target_client in self.clients:
            for client, nickname in zip(self.clients, self.nicknames):
                avatar_img = self.avatars.get(client)
                buf = io.BytesIO()
                if avatar_img:
                    try:
                        avatar_img.save(buf, format='PNG')
                    except Exception:
                        continue
                avatar_data = buf.getvalue()
                avatar_payload = avatar_data.decode('latin1', errors='ignore')
                
                payload = f"INIT_AVATAR:{nickname}:{avatar_payload}".encode('latin1')
                
                try:
                    self._send_data(target_client, payload)
                except:
                    pass

    def send_private(self, sender, receiver, message):
        if receiver in self.nicknames:
            idx = self.nicknames.index(receiver)
            client = self.clients[idx]
            try:
                data = f"PRIVATE:[P {sender}] {message}".encode('utf-8')
                self._send_data(client, data)
            except:
                pass

class AeroButton(ctk.CTkButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, corner_radius=12, font=("Segoe UI", 11, "bold"), text_color="white")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.messenger = Messenger()
        self.nickname = ""
        self.avatar_img = None
        self.user_avatars = {}
        self.theme = "light"
        self.themes = {
            "light": {"accent": "#4a90e2", "bg": "#f5f9ff", "card": "#ffffff", "input": "#f8fbff", "border": "#d0e4ff", "text": "#333333", "subtext": "#888888", "bubble": "#e0e0e0", "private": "#e8f5e9", "local_bubble": "#d1e7ff"},
            "dark":  {"accent": "#666666", "bg": "#1a1a1a", "card": "#2d2d2d", "input": "#3a3a3a", "border": "#555555", "text": "#e0e0e0", "subtext": "#aaaaaa", "bubble": "#424242", "private": "#424242", "local_bubble": "#5a5a5a"},
            "green": {"accent": "#2e7d32", "bg": "#f0f8f0", "card": "#ffffff", "input": "#f5fdf5", "border": "#c8e6c9", "text": "#1b5e20", "subtext": "#558b2f", "bubble": "#e0f2e1", "private": "#e0f2e1", "local_bubble": "#a5d6a7"}
        }
        self.setup_ui()
        self.apply_theme()

    def setup_ui(self):
        self.geometry("920x740")
        self.title("Krue")
        self.minsize(700, 600)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkFrame(self, height=80, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)

        self.info_btn = ctk.CTkButton(self.header, text="Info", width=60, height=40, corner_radius=10, font=("Segoe UI", 14, "bold"), text_color="white", command=self.open_info_window)
        self.info_btn.grid(row=0, column=0, padx=20, pady=20, sticky="w")

        self.title_label = ctk.CTkLabel(self.header, text="Krue", text_color="white", font=("Segoe UI", 28, "bold"))
        self.title_label.grid(row=0, column=0, pady=20)

        self.theme_switch = ctk.CTkSegmentedButton(self.header, values=["Light", "Dark", "Green"], command=self.change_theme)
        self.theme_switch.grid(row=0, column=1, padx=20, pady=20, sticky="e")
        self.theme_switch.set("Light")

        self.connection_frame = ctk.CTkFrame(self, corner_radius=16, border_width=1)
        self.connection_frame.grid(row=1, column=0, padx=20, pady=(15, 10), sticky="ew")
        self.connection_frame.grid_columnconfigure(1, weight=1)

        self.avatar_btn = ctk.CTkButton(self.connection_frame, text="Avatar", width=50, height=50, corner_radius=25, font=("Segoe UI", 16), command=self.open_avatar_options)
        self.avatar_btn.grid(row=0, column=0, padx=(15, 10), pady=15)

        self.nickname_entry = ctk.CTkEntry(self.connection_frame, placeholder_text="Your Nickname", width=180, height=40, corner_radius=12, font=("Segoe UI", 12))
        self.nickname_entry.grid(row=0, column=1, padx=5, pady=15, sticky="w")

        self.host_entry = ctk.CTkEntry(self.connection_frame, placeholder_text="Server IP", width=180, height=40, corner_radius=12, font=("Segoe UI", 12))
        self.host_entry.grid(row=0, column=2, padx=5, pady=15)

        self.connect_btn = AeroButton(self.connection_frame, text="Connect", width=100, height=40, command=self.connect)
        self.connect_btn.grid(row=0, column=3, padx=(10, 15), pady=15)

        self.chat_container = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_container.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.chat_container.grid_rowconfigure(0, weight=1)
        self.chat_container.grid_columnconfigure(0, weight=1)

        self.chat_frame = ctk.CTkScrollableFrame(self.chat_container, corner_radius=16, border_width=1)
        self.chat_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.input_frame = ctk.CTkFrame(self, corner_radius=16, border_width=1)
        self.input_frame.grid(row=3, column=0, padx=20, pady=(5, 20), sticky="ew")
        self.input_frame.grid_columnconfigure(1, weight=1)

        self.emoji_btn = ctk.CTkButton(self.input_frame, text="Smile", width=40, corner_radius=12, font=("Segoe UI", 16), command=self.show_emoji_menu)
        self.emoji_btn.grid(row=0, column=0, padx=(15, 5), pady=12)
        
        self.message_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Write a message...", height=45, border_width=0, corner_radius=12, font=("Segoe UI", 12))
        self.message_entry.grid(row=0, column=1, padx=5, pady=12, sticky="ew")
        self.message_entry.bind("<Return>", self.send_message)

        self.send_btn = AeroButton(self.input_frame, text="Send", width=45, height=45, command=self.send_message)
        self.send_btn.grid(row=0, column=2, padx=(5, 15), pady=12)

        self.status_frame = ctk.CTkFrame(self, height=35, corner_radius=0)
        self.status_frame.grid(row=4, column=0, sticky="ew")
        self.status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(self.status_frame, text="Disconnected", font=("Segoe UI", 10, "italic"))
        self.status_label.grid(row=0, column=0, padx=15, pady=8, sticky="w")

        self.grid_rowconfigure(2, weight=1)
        self.disable_chat()
        self.emoji_menu = None
        self.avatar_options_menu = None
        self.message_history = [] 

    def apply_theme(self):
        t = self.themes[self.theme]
        self.configure(fg_color=t["bg"])
        self.header.configure(fg_color=t["accent"])
        self.connection_frame.configure(fg_color=t["card"], border_color=t["border"])
        self.chat_frame.configure(fg_color=t["card"], border_color=t["border"])
        self.input_frame.configure(fg_color=t["card"], border_color=t["border"])
        self.status_frame.configure(fg_color=t["border"])
        self.nickname_entry.configure(fg_color=t["input"], border_color=t["accent"])
        self.host_entry.configure(fg_color=t["input"], border_color=t["accent"])
        self.message_entry.configure(fg_color=t["input"])
        self.avatar_btn.configure(fg_color=t["input"], hover_color=t["border"])
        self.emoji_btn.configure(fg_color=t["input"], hover_color=t["border"])
        self.connect_btn.configure(fg_color=t["accent"], hover_color=self.darken(t["accent"]))
        self.send_btn.configure(fg_color=t["accent"], hover_color=self.darken(t["accent"]))
        self.status_label.configure(text_color=t["accent"])
        self.info_btn.configure(fg_color=t["accent"], hover_color=self.darken(t["accent"]))


    def darken(self, color):
        try:
            c = self.winfo_rgb(color)
            c = tuple(int(x * 0.8 / 257) for x in c)
            return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
        except:
            return color

    def change_theme(self, value):
        mapping = {"Light": "light", "Dark": "dark", "Green": "green"}
        self.theme = mapping[value]
        self.apply_theme()
        self.update_chat_display()

    def open_info_window(self):
        for widget in self.winfo_children():
            if isinstance(widget, DeveloperInfoWindow):
                widget.lift()
                return
        
        DeveloperInfoWindow(self, self.theme)

    def open_avatar_options(self):
        if self.avatar_options_menu and self.avatar_options_menu.winfo_exists():
            self.avatar_options_menu.destroy()
            self.avatar_options_menu = None
            return

        x = self.avatar_btn.winfo_rootx()
        y = self.avatar_btn.winfo_rooty() + self.avatar_btn.winfo_height() + 5

        menu = ctk.CTkToplevel(self)
        menu.title("")
        menu.geometry(f"+{x}+{y}")
        menu.overrideredirect(True)
        menu.configure(fg_color=self.themes[self.theme]["card"])

        ctk.CTkButton(menu, text="Upload Image", command=lambda: self.select_avatar("file", menu)).pack(pady=(5, 2), padx=10)
        ctk.CTkButton(menu, text="Remove Avatar", command=lambda: self.select_avatar("remove", menu)).pack(pady=(2, 5), padx=10)
        
        self.avatar_options_menu = menu

    def send_avatar_update(self):
        if self.messenger.client_socket:
            buf = io.BytesIO()
            if self.avatar_img:
                try:
                    self.avatar_img.save(buf, format='PNG')
                except Exception:
                    return
            avatar_data = buf.getvalue()
            payload = avatar_data.decode('latin1', errors='ignore')
            self.messenger.send_avatar_update(payload)

    def select_avatar(self, choice, menu):
        menu.destroy()
        self.avatar_options_menu = None
        
        if choice == "file":
            path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
            if path:
                AvatarCropper(self, path)
        elif choice == "remove":
            self.avatar_img = None
            self.avatar_btn.configure(image=None, text="Avatar")
            self.send_avatar_update()

    def show_emoji_menu(self):
        if self.emoji_menu and self.emoji_menu.winfo_exists():
            self.emoji_menu.destroy()
            self.emoji_menu = None
            return
        emojis = ":3 ;3 ;) :) :( 0_0 :P :D xD ;D >) >3 "
        menu = ctk.CTkToplevel(self)
        menu.title("")
        menu.geometry(f"+{self.winfo_rootx() + 60}+{self.winfo_rooty() + 520}")
        menu.configure(fg_color=self.themes[self.theme]["card"])
        menu.overrideredirect(True)
        frame = ctk.CTkFrame(menu, fg_color=self.themes[self.theme]["card"], corner_radius=12, border_width=1, border_color=self.themes[self.theme]["border"])
        frame.pack(padx=5, pady=5)
        row = col = 0
        for e in emojis.split():
            btn = ctk.CTkButton(frame, text=e, width=40, height=40, fg_color="transparent", hover_color=self.themes[self.theme]["border"], corner_radius=8, font=("Segoe UI", 18), command=lambda x=e: self.insert_emoji(x, menu))
            btn.grid(row=row, column=col, padx=2, pady=2)
            col += 1
            if col > 7:
                col = 0
                row += 1
        self.emoji_menu = menu

    def insert_emoji(self, emoji, menu=None):
        self.message_entry.insert(ctk.END, emoji)
        if menu:
            menu.destroy()
            self.emoji_menu = None
            
    def connect(self):
        self.nickname = self.nickname_entry.get().strip()
        if not self.nickname:
            messagebox.showerror("Error", "Enter your nickname")
            return
        host = self.host_entry.get().strip()
        if not host:
            host = self.messenger.get_local_ip()
            if not self.messenger.start_server():
                messagebox.showerror("Error", "Could not start server")
                return
            self.status_label.configure(text=f"Server: {host}")
        else:
            self.status_label.configure(text=f"Connecting to {host}...")
        
        if not self.messenger.connect_to_server(host):
            messagebox.showerror("Error", f"Could not connect to {host}")
            self.status_label.configure(text="Disconnected")
            return
        
        try:
            nick_data = self.nickname.encode('utf-8')
            nick_len = struct.pack('>I', len(nick_data))
            
            buf = io.BytesIO()
            if self.avatar_img:
                try:
                    self.avatar_img.save(buf, format='PNG')
                except Exception:
                    pass
            avatar_data = buf.getvalue()
            avatar_len = struct.pack('>I', len(avatar_data))
            
            self.messenger.client_socket.sendall(nick_len + nick_data + avatar_len + avatar_data)
            
            threading.Thread(target=self.receive_messages, daemon=True).start()
            self.enable_chat()
            self.status_label.configure(text=f"Online as {self.nickname}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed:\n{e}")
            self.status_label.configure(text="Disconnected")

    def _recv_all(self, client, size):
        data = b''
        while len(data) < size:
            chunk = client.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def receive_messages(self):
        while True:
            try:
                msg_header = self._recv_all(self.messenger.client_socket, 4)
                if not msg_header: break
                msg_len = struct.unpack('>I', msg_header)[0]

                msg_data = self._recv_all(self.messenger.client_socket, msg_len)
                if not msg_data: break
                
                command, message_payload = msg_data.split(b':', 1)
                command = command.decode('utf-8')

                if command == "SYS":
                    self.display_message(message_payload.decode('utf-8'), "system")
                
                elif command == "PRIVATE":
                    self.display_message(message_payload.decode('utf-8'), "private")
                
                elif command == "MSG":
                    message = message_payload.decode('utf-8', errors='ignore').strip()
                    if ":" in message:
                        nick, text = message.split(":", 1)
                        self.display_message(f"{nick}: {text.strip()}")
                    else:
                        self.display_message(message)
                
                elif command == "AVATAR_UPDATE":
                    nick, avatar_payload = message_payload.decode('latin1').split(':', 1)
                    avatar_data = avatar_payload.encode('latin1')
                    
                    avatar_img = None
                    if avatar_data:
                        try:
                            avatar_img = Image.open(io.BytesIO(avatar_data)).resize((40, 40), Image.Resampling.LANCZOS)
                        except Exception:
                            pass
                    self.user_avatars[nick] = avatar_img
                    self.update_chat_display()

                elif command == "INIT_AVATAR":
                    nick, avatar_payload = message_payload.decode('latin1').split(':', 1)
                    avatar_data = avatar_payload.encode('latin1')
                    
                    avatar_img = None
                    if avatar_data:
                        try:
                            avatar_img = Image.open(io.BytesIO(avatar_data)).resize((40, 40), Image.Resampling.LANCZOS)
                        except Exception:
                            pass
                    self.user_avatars[nick] = avatar_img

            except Exception:
                break
        messagebox.showerror("Error", "Connection lost")
        self.disable_chat()
        self.status_label.configure(text="Disconnected")

    def update_chat_display(self):
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
        
        for msg_data in self.message_history:
            if len(msg_data) == 2:
                self.display_message(*msg_data, replay=True)

    def display_message(self, message, tag=None, replay=False):
        t = self.themes[self.theme]
        time_str = datetime.now().strftime("%H:%M")
        
        if tag != "system" and not replay:
            self.message_history.append((message, tag))

        if tag == "system":
            frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
            frame.pack(fill='x', padx=10, pady=4, anchor='center')
            color = "#2e7d32" if self.theme != "dark" else "#81c784"
            ctk.CTkLabel(frame, text=message, text_color=color, font=("Segoe UI", 10, "italic")).pack()
            return

        nick = text = ""
        is_private = tag == "private"
        
        if is_private:
            sender = message[4:message.find("]")]
            text = message[message.find("]")+2:]
            nick = sender
        elif ":" in message:
            nick, text = message.split(":", 1)
        else:
            nick, text = "System", message
            
        is_local = (nick.strip() == self.nickname)

        if is_private:
            bubble_color = t["private"]
        elif is_local:
            bubble_color = t["local_bubble"]
        else:
            bubble_color = t["bubble"]

        frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        frame.pack(fill='x', padx=10, pady=2, anchor='e' if is_local else 'w') 

        avatar_img = None
        if is_local:
            avatar_img = self.avatar_img
        else:
            avatar_img = self.user_avatars.get(nick.strip())

        msg_container = ctk.CTkFrame(frame, fg_color="transparent")
        
        if is_local:
            msg_container.pack(side='right', anchor='e', padx=(100, 0))
        else:
            msg_container.pack(side='left', anchor='w', padx=(0, 100))

        if avatar_img:
            ctk_img = ctk.CTkImage(light_image=avatar_img, dark_image=avatar_img, size=(30, 30))
            lbl = ctk.CTkLabel(msg_container, image=ctk_img, text="")
            lbl.image = ctk_img
            
            if is_local:
                lbl.pack(side='right', padx=(5, 0), pady=1) 
            else:
                lbl.pack(side='left', padx=(0, 5), pady=1) 

        msg_inner = ctk.CTkFrame(msg_container, fg_color=bubble_color, corner_radius=12, border_width=1, border_color=t["border"])
        
        if is_local:
            msg_inner.pack(side='right', padx=5, pady=1) 
        else:
            msg_inner.pack(side='left', padx=5, pady=1) 
            
        justify_align = 'right' if is_local else 'left'
        text_anchor = 'e' if is_local else 'w'
        
        header_frame = ctk.CTkFrame(msg_inner, fg_color="transparent")
        header_frame.pack(fill='x', padx=10, pady=(4, 0))
        header_frame.grid_columnconfigure(0, weight=1)
        
        time_col, nick_col = (0, 1) if not is_local else (1, 0)
        
        ctk.CTkLabel(header_frame, text=time_str, text_color=t["subtext"], font=("Segoe UI", 7), anchor=text_anchor).grid(row=0, column=time_col, sticky=text_anchor, padx=0)
        ctk.CTkLabel(header_frame, text=nick, text_color=t["accent"], font=("Segoe UI", 8, "bold"), anchor=text_anchor).grid(row=0, column=nick_col, sticky=text_anchor, padx=0)
            
        ctk.CTkLabel(msg_inner, text=text, text_color=t["text"], font=("Segoe UI", 9), wraplength=350, justify=justify_align, anchor=text_anchor).pack(anchor=text_anchor, padx=10, pady=(1, 4))
        
        if not replay:
            self.chat_frame.update_idletasks()
            self.chat_frame._parent_canvas.yview_moveto(1.0) 

    def send_message(self, event=None):
        msg = self.message_entry.get().strip()
        if msg:
            self.messenger.send_message(msg)
            self.message_entry.delete(0, ctk.END)

    def enable_chat(self):
        self.message_entry.configure(state="normal")
        self.send_btn.configure(state="normal")
        self.emoji_btn.configure(state="normal")
        self.connect_btn.configure(state="disabled")
        self.nickname_entry.configure(state="disabled")
        self.host_entry.configure(state="disabled")
        self.avatar_btn.configure(state="normal") 

    def disable_chat(self):
        self.message_entry.configure(state="disabled")
        self.send_btn.configure(state="disabled")
        self.emoji_btn.configure(state="disabled")
        self.avatar_btn.configure(state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()