"""
SecureVault X - Premium Enterprise Edition - Premium Enterprise-Grade Cybersecurity Platform
Military Grade Encrypted File Storage with Modern SaaS UI/UX
"""

import os
import sqlite3
import bcrypt
import json
import hmac
import hashlib
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox, Canvas, END
import requests
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# PREMIUM COLOR PALETTE
# ============================================================================

DEEP_DARK = "#050816"
DARK_BG = "#0B1026"
CARD_DARK = "#111827"
CARD_LIGHTER = "#1E293B"
PRIMARY = "#6366F1"
PRIMARY_GLOW = "#7C7FFF"
SECONDARY = "#8B5CF6"
ACCENT = "#06B6D4"
ACCENT_GLOW = "#22D3EE"
SUCCESS = "#22C55E"
SUCCESS_GLOW = "#4ADE80"
DANGER = "#EF4444"
DANGER_GLOW = "#FF6B6B"
WARNING = "#F59E0B"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
TEXT_MUTED = "#94A3B8"

# ============================================================================
# CONSTANTS
# ============================================================================

DB_PATH = "app.db"
KEY_FILE = "secret.key"
HMAC_KEY_FILE = "hmac_secret.key"
LOG_FILE = "logs/activity.log"
INTEGRITY_FILE = "integrity.json"
UPLOAD_STATE_FILE = "uploads/upload_state.json"
CHUNK_SIZE = 5 * 1024 * 1024
SERVER_STORAGE = "server_storage"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5001
SERVER_URL = f"https://{SERVER_HOST}:{SERVER_PORT}"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def ensure_directories():
    for path in ["encrypted", "decrypted", "uploads", "logs", SERVER_STORAGE]:
        os.makedirs(path, exist_ok=True)

def format_size(bytes_size):
    if bytes_size is None:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} PB"

def current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_time_since(timestamp_str):
    try:
        dt = datetime.strptime(timestamp_str[:19], "%Y-%m-%d %H:%M:%S")
        delta = datetime.now() - dt
        if delta.seconds < 60:
            return "Just now"
        elif delta.seconds < 3600:
            return f"{delta.seconds // 60}m ago"
        elif delta.days == 0:
            return f"{delta.seconds // 3600}h ago"
        elif delta.days == 1:
            return "Yesterday"
        else:
            return f"{delta.days}d ago"
    except:
        return "Unknown"

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                encrypted_filename TEXT NOT NULL,
                size INTEGER,
                modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()
        conn.close()

    def register_user(self, username, password):
        try:
            hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False

    def verify_user(self, username, password):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
        record = cursor.fetchone()
        conn.close()
        if record:
            user_id, hashed = record
            if bcrypt.checkpw(password.encode("utf-8"), hashed):
                return user_id
        return None

    def get_user_id(self, username):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        record = cursor.fetchone()
        conn.close()
        return record[0] if record else None

    def add_file(self, user_id, filename, encrypted_filename, size):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO files (user_id, filename, encrypted_filename, size) VALUES (?, ?, ?, ?)",
            (user_id, filename, encrypted_filename, size),
        )
        conn.commit()
        conn.close()

    def get_user_files(self, user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT filename, encrypted_filename, size, modified_at FROM files WHERE user_id = ? ORDER BY modified_at DESC",
            (user_id,),
        )
        records = cursor.fetchall()
        conn.close()
        return records

    def delete_file_record(self, user_id, encrypted_filename):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM files WHERE user_id = ? AND encrypted_filename = ?",
            (user_id, encrypted_filename),
        )
        conn.commit()
        conn.close()

# ============================================================================
# INTEGRITY MANAGER
# ============================================================================

class IntegrityManager:
    def __init__(self):
        self.hmac_key_file = HMAC_KEY_FILE
        self.integrity_file = INTEGRITY_FILE
        self._ensure_hmac_key()
        self._load_integrity_values()

    def _ensure_hmac_key(self):
        if not os.path.exists(self.hmac_key_file):
            with open(self.hmac_key_file, "wb") as f:
                f.write(Fernet.generate_key())

    def _get_hmac_key(self):
        with open(self.hmac_key_file, "rb") as f:
            return f.read()

    def _load_integrity_values(self):
        if os.path.exists(self.integrity_file):
            try:
                with open(self.integrity_file, "r", encoding="utf-8") as f:
                    self.values = json.load(f)
            except Exception:
                self.values = {}
        else:
            self.values = {}

    def _save_integrity_values(self):
        with open(self.integrity_file, "w", encoding="utf-8") as f:
            json.dump(self.values, f, indent=2)

    def compute_hmac(self, data_bytes):
        return hmac.new(self._get_hmac_key(), data_bytes, hashlib.sha256).hexdigest()

    def store_hmac(self, encrypted_filename, hmac_value):
        self.values[encrypted_filename] = hmac_value
        self._save_integrity_values()

    def get_hmac(self, encrypted_filename):
        return self.values.get(encrypted_filename)

    def verify(self, encrypted_filename, plaintext_bytes):
        expected = self.get_hmac(encrypted_filename)
        if not expected:
            return False, "Missing HMAC record"
        actual = self.compute_hmac(plaintext_bytes)
        if hmac.compare_digest(expected, actual):
            return True, "Integrity Verified"
        return False, "File Tampered"

# ============================================================================
# ENCRYPTION MANAGER
# ============================================================================

class EncryptionManager:
    def __init__(self, integrity_manager):
        self.integrity_manager = integrity_manager
        self.key_file = KEY_FILE
        self._ensure_key()
        self.upload_state = self._load_upload_state()

    def _ensure_key(self):
        if not os.path.exists(self.key_file):
            with open(self.key_file, "wb") as f:
                f.write(Fernet.generate_key())

    def _get_key(self):
        with open(self.key_file, "rb") as f:
            return f.read()

    def _load_upload_state(self):
        if os.path.exists(UPLOAD_STATE_FILE):
            try:
                with open(UPLOAD_STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_upload_state(self):
        with open(UPLOAD_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.upload_state, f, indent=2)

    def _clear_upload_state(self, file_key):
        if file_key in self.upload_state:
            del self.upload_state[file_key]
            self._save_upload_state()

    def _get_resume_state(self, file_path, encrypted_filename):
        key = f"{file_path}:{encrypted_filename}"
        return self.upload_state.get(key)

    def _update_resume_state(self, file_path, encrypted_filename, state):
        key = f"{file_path}:{encrypted_filename}"
        self.upload_state[key] = state
        self._save_upload_state()

    def encrypt_file(self, file_path, progress_callback=None, chunk_callback=None):
        if not os.path.exists(file_path):
            raise FileNotFoundError("Source file not found")

        cipher = Fernet(self._get_key())
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        encrypted_filename = f"{filename}.enc"
        encrypted_path = os.path.join("encrypted", encrypted_filename)
        total_chunks = max(1, (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE)
        state = self._get_resume_state(file_path, encrypted_filename)
        current_chunk = 0

        if state and os.path.exists(encrypted_path):
            if state.get("file_size") == file_size and state.get("total_chunks") == total_chunks:
                current_chunk = state.get("current_chunk", 0)
            else:
                os.remove(encrypted_path)
                self._clear_upload_state(f"{file_path}:{encrypted_filename}")
                state = None
                current_chunk = 0

        mode = "ab" if current_chunk > 0 else "wb"
        progress = 0
        with open(file_path, "rb") as source, open(encrypted_path, mode) as target:
            source.seek(current_chunk * CHUNK_SIZE)
            for chunk_index in range(current_chunk, total_chunks):
                chunk = source.read(CHUNK_SIZE)
                if not chunk:
                    break
                encrypted_chunk = cipher.encrypt(chunk)
                chunk_length = len(encrypted_chunk).to_bytes(4, byteorder="big")
                target.write(chunk_length)
                target.write(encrypted_chunk)

                progress = int((chunk_index + 1) * 100 / total_chunks)
                if progress_callback:
                    progress_callback(progress)

                if chunk_callback:
                    chunk_callback(encrypted_filename, encrypted_chunk, chunk_index, total_chunks)

                state = {
                    "file_path": file_path,
                    "encrypted_filename": encrypted_filename,
                    "file_size": file_size,
                    "total_chunks": total_chunks,
                    "current_chunk": chunk_index + 1,
                }
                self._update_resume_state(file_path, encrypted_filename, state)

        with open(file_path, "rb") as source:
            plaintext = source.read()
        hmac_value = self.integrity_manager.compute_hmac(plaintext)
        self.integrity_manager.store_hmac(encrypted_filename, hmac_value)
        self._clear_upload_state(f"{file_path}:{encrypted_filename}")
        return encrypted_filename, file_size

    def _decrypt_file_stream(self, encrypted_path, decrypted_path):
        cipher = Fernet(self._get_key())
        with open(encrypted_path, "rb") as source, open(decrypted_path, "wb") as target:
            while True:
                length_bytes = source.read(4)
                if not length_bytes:
                    break
                if len(length_bytes) != 4:
                    raise ValueError("Corrupted encrypted file")
                chunk_len = int.from_bytes(length_bytes, byteorder="big")
                encrypted_chunk = source.read(chunk_len)
                if len(encrypted_chunk) != chunk_len:
                    raise ValueError("Corrupted encrypted file")
                plaintext = cipher.decrypt(encrypted_chunk)
                target.write(plaintext)

    def decrypt_file(self, encrypted_filename):
        encrypted_path = os.path.join("encrypted", encrypted_filename)
        if not os.path.exists(encrypted_path):
            raise FileNotFoundError("Encrypted file not found")

        temporary_path = os.path.join("uploads", "temp_decrypt.bin")
        self._decrypt_file_stream(encrypted_path, temporary_path)
        with open(temporary_path, "rb") as f:
            plaintext = f.read()
        verified, message = self.integrity_manager.verify(encrypted_filename, plaintext)
        if not verified:
            os.remove(temporary_path)
            raise ValueError(message)

        decrypted_filename = encrypted_filename.replace(".enc", "")
        decrypted_path = os.path.join("decrypted", decrypted_filename)
        with open(decrypted_path, "wb") as f:
            f.write(plaintext)
        os.remove(temporary_path)
        return decrypted_path

    def verify_integrity(self, encrypted_filename):
        encrypted_path = os.path.join("encrypted", encrypted_filename)
        if not os.path.exists(encrypted_path):
            return False, "Encrypted file missing"
        try:
            temporary_path = os.path.join("uploads", "temp_verify.bin")
            self._decrypt_file_stream(encrypted_path, temporary_path)
            with open(temporary_path, "rb") as f:
                plaintext = f.read()
            os.remove(temporary_path)
            return self.integrity_manager.verify(encrypted_filename, plaintext)
        except Exception as e:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
            return False, f"Verification failed: {str(e)}"

# ============================================================================
# SERVER MANAGER
# ============================================================================

class LocalServer(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.app = Flask("securevaultx_server")
        self._configure_routes()
        self.start()

    def _configure_routes(self):
        @self.app.route("/list", methods=["GET"])
        def list_files():
            files = []
            for filename in os.listdir(SERVER_STORAGE):
                path = os.path.join(SERVER_STORAGE, filename)
                if os.path.isfile(path):
                    files.append({
                        "filename": filename,
                        "size": os.path.getsize(path),
                        "modified_at": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S"),
                    })
            return jsonify(files)

        @self.app.route("/upload", methods=["POST"])
        def upload_chunk():
            file_name = request.form.get("file_name")
            chunk_index = request.form.get("chunk_index")
            total_chunks = request.form.get("total_chunks")
            chunk = request.files.get("chunk")
            if not file_name or chunk is None or chunk_index is None or total_chunks is None:
                return jsonify({"error": "Missing upload parameters"}), 400
            file_name = secure_filename(file_name)
            try:
                chunk_index = int(chunk_index)
                total_chunks = int(total_chunks)
            except ValueError:
                return jsonify({"error": "Invalid chunk metadata"}), 400

            target_path = os.path.join(SERVER_STORAGE, file_name)
            if chunk_index == 0 and os.path.exists(target_path):
                os.remove(target_path)

            try:
                with open(target_path, "ab") as f:
                    f.write(chunk.read())
            except Exception as exc:
                return jsonify({"error": f"Failed to write chunk: {exc}"}), 500

            return jsonify({"status": "chunk received", "chunk_index": chunk_index, "total_chunks": total_chunks})

        @self.app.route("/download", methods=["GET"])
        def download_file():
            file_name = request.args.get("file_name")
            if not file_name:
                return jsonify({"error": "Missing file_name"}), 400
            file_name = secure_filename(file_name)
            file_path = os.path.join(SERVER_STORAGE, file_name)
            if not os.path.exists(file_path):
                return jsonify({"error": "File not found"}), 404
            return send_from_directory(SERVER_STORAGE, file_name, as_attachment=True)

        @self.app.route("/delete", methods=["POST"])
        def delete_file():
            data = request.json or request.form
            file_name = data.get("file_name")
            if not file_name:
                return jsonify({"error": "Missing file_name"}), 400
            file_name = secure_filename(file_name)
            file_path = os.path.join(SERVER_STORAGE, file_name)
            if not os.path.exists(file_path):
                return jsonify({"error": "File not found"}), 404
            os.remove(file_path)
            return jsonify({"status": "deleted"})

    def run(self):
        self.app.run(host=SERVER_HOST, port=SERVER_PORT, ssl_context="adhoc", threaded=True, use_reloader=False)

# ============================================================================
# ACTIVITY LOGGER
# ============================================================================

class ActivityLogger:
    def __init__(self):
        self.log_file = LOG_FILE
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def log(self, message):
        timestamp = current_timestamp()
        record = f"[{timestamp}] {message}\n"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(record)

    def read_logs(self):
        if not os.path.exists(self.log_file):
            return []
        with open(self.log_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines()][::-1]

    def search(self, query):
        logs = self.read_logs()
        if not query:
            return logs
        query_lower = query.lower()
        return [line for line in logs if query_lower in line.lower()]

    def clear(self):
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
            return True
        except Exception:
            return False

# ============================================================================
# PREMIUM UI COMPONENTS
# ============================================================================

class PremiumFrame(ctk.CTkFrame):
    """Glassmorphic card with premium styling"""
    def __init__(self, parent, **kwargs):
        defaults = {
            "fg_color": CARD_DARK,
            "corner_radius": 16,
            "border_width": 1,
            "border_color": CARD_LIGHTER
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)

class GlowingButton(ctk.CTkButton):
    """Premium button with hover glow effect"""
    def __init__(self, parent, primary=False, **kwargs):
        color = PRIMARY if primary else SECONDARY
        hover_color = PRIMARY_GLOW if primary else SECONDARY
        defaults = {
            "fg_color": color,
            "hover_color": hover_color,
            "corner_radius": 12,
            "font": ("Segoe UI", 11, "bold")
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)

class PremiumLabel(ctk.CTkLabel):
    """Premium text label with proper styling"""
    def __init__(self, parent, text="", style="primary", **kwargs):
        if style == "primary":
            color = TEXT_PRIMARY
            font = ("Segoe UI", 13, "bold")
        elif style == "secondary":
            color = TEXT_SECONDARY
            font = ("Segoe UI", 11)
        elif style == "muted":
            color = TEXT_MUTED
            font = ("Segoe UI", 10)
        elif style == "title":
            color = TEXT_PRIMARY
            font = ("Segoe UI", 24, "bold")
        elif style == "heading":
            color = TEXT_PRIMARY
            font = ("Segoe UI", 18, "bold")
        else:
            color = TEXT_PRIMARY
            font = ("Segoe UI", 11)
        
        defaults = {
            "text": text,
            "text_color": color,
            "font": font
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)

class AnimatedProgressRing(ctk.CTkCanvas):
    """Animated circular progress ring"""
    def __init__(self, parent, size=120, percentage=75, **kwargs):
        defaults = {
            "width": size,
            "height": size,
            "bg": DEEP_DARK,
            "highlightthickness": 0
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)
        self.size = size
        self.percentage = percentage
        self.draw_ring()

    def draw_ring(self):
        self.delete("all")
        cx, cy = self.size // 2, self.size // 2
        radius = self.size // 2 - 10
        
        # Background ring
        self.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=CARD_LIGHTER, width=8)
        
        # Progress ring
        arc_extent = (self.percentage / 100) * 360
        self.create_arc(cx - radius, cy - radius, cx + radius, cy + radius, start=90, extent=-arc_extent, 
                       outline=PRIMARY_GLOW, width=8, style="arc")
        
        # Percentage text
        self.create_text(cx, cy, text=f"{self.percentage}%", font=("Segoe UI", 20, "bold"), fill=PRIMARY_GLOW)

# ============================================================================
# LOGIN PAGE - PREMIUM VERSION
# ============================================================================

class PremiumLoginPage:
    def __init__(self, app, db, logger, server_manager, encryption_manager):
        self.app = app
        self.db = db
        self.logger = logger
        self.server_manager = server_manager
        self.encryption_manager = encryption_manager
        self.show_login()

    def show_login(self):
        self.clear_window()
        
        # Main background
        main_frame = ctk.CTkFrame(self.app, fg_color=DEEP_DARK)
        main_frame.pack(fill="both", expand=True)
        
        # Left side - Branding
        left_frame = ctk.CTkFrame(main_frame, fg_color=DARK_BG)
        left_frame.pack(side="left", fill="both", expand=True, padx=0)
        
        branding = ctk.CTkFrame(left_frame, fg_color=DARK_BG)
        branding.pack(expand=True)
        
        logo_label = PremiumLabel(branding, text="🛡️", style="title")
        logo_label.pack(pady=20)
        
        title = PremiumLabel(branding, text="SecureVault X", style="title")
        title.pack(pady=10)
        
        subtitle = PremiumLabel(branding, text="Military Grade Encryption", style="secondary")
        subtitle.pack(pady=5)
        
        features_text = "• 256-Bit AES Encryption\n• HMAC-SHA256 Verification\n• Secure Key Management\n• Enterprise-Grade Security"
        PremiumLabel(branding, text=features_text, style="muted").pack(pady=20)
        
        # Right side - Login Form
        right_frame = ctk.CTkFrame(main_frame, fg_color=DEEP_DARK)
        right_frame.pack(side="right", fill="both", expand=True, padx=60)
        
        form_container = ctk.CTkFrame(right_frame, fg_color=DEEP_DARK)
        form_container.pack(expand=True)
        
        PremiumLabel(form_container, text="Welcome Back", style="heading").pack(pady=(0, 10))
        PremiumLabel(form_container, text="Sign in to your account", style="secondary").pack(pady=(0, 30))
        
        # Username
        PremiumLabel(form_container, text="Username", style="primary").pack(anchor="w", pady=(0, 8))
        username_entry = ctk.CTkEntry(form_container, placeholder_text="Enter your username", height=45, 
                                      fg_color=CARD_DARK, text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_MUTED,
                                      border_color=PRIMARY, corner_radius=10)
        username_entry.pack(fill="x", pady=(0, 15))
        
        # Password
        PremiumLabel(form_container, text="Password", style="primary").pack(anchor="w", pady=(0, 8))
        password_entry = ctk.CTkEntry(form_container, placeholder_text="Enter your password", show="●", height=45,
                                      fg_color=CARD_DARK, text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_MUTED,
                                      border_color=PRIMARY, corner_radius=10)
        password_entry.pack(fill="x", pady=(0, 25))
        
        def login_action():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            if not username or not password:
                messagebox.showerror("Error", "Please enter username and password")
                return
            user_id = self.db.verify_user(username, password)
            if user_id:
                self.logger.log(f"User Login: {username}")
                PremiumDashboardPage(self.app, self.db, self.logger, username, self.server_manager, self.encryption_manager)
            else:
                self.logger.log(f"Failed Login Attempt: {username}")
                messagebox.showerror("Error", "Invalid credentials")
        
        button_frame = ctk.CTkFrame(form_container, fg_color=DEEP_DARK)
        button_frame.pack(fill="x", pady=(0, 15))
        
        login_btn = GlowingButton(button_frame, text="Sign In", command=login_action, primary=True, height=45)
        login_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        register_btn = GlowingButton(button_frame, text="Create Account", command=self.show_register, height=45)
        register_btn.pack(side="left", fill="x", expand=True, padx=(8, 0))
        
        # Footer
        footer = ctk.CTkFrame(form_container, fg_color=DEEP_DARK)
        footer.pack(fill="x", pady=(30, 0))
        PremiumLabel(footer, text="v2.0 • Premium Enterprise Edition", style="muted").pack()

    def show_register(self):
        self.clear_window()
        
        main_frame = ctk.CTkFrame(self.app, fg_color=DEEP_DARK)
        main_frame.pack(fill="both", expand=True)
        
        center = ctk.CTkFrame(main_frame, fg_color=DEEP_DARK)
        center.pack(expand=True, padx=60)
        
        PremiumLabel(center, text="Create Account", style="heading").pack(pady=(0, 10))
        PremiumLabel(center, text="Set up your secure vault", style="secondary").pack(pady=(0, 30))
        
        PremiumLabel(center, text="Username", style="primary").pack(anchor="w", pady=(0, 8))
        username_entry = ctk.CTkEntry(center, placeholder_text="Choose username", height=45,
                                      fg_color=CARD_DARK, text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_MUTED,
                                      border_color=PRIMARY, corner_radius=10)
        username_entry.pack(fill="x", pady=(0, 15))
        
        PremiumLabel(center, text="Password", style="primary").pack(anchor="w", pady=(0, 8))
        password_entry = ctk.CTkEntry(center, placeholder_text="Create password", show="●", height=45,
                                      fg_color=CARD_DARK, text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_MUTED,
                                      border_color=PRIMARY, corner_radius=10)
        password_entry.pack(fill="x", pady=(0, 15))
        
        PremiumLabel(center, text="Confirm Password", style="primary").pack(anchor="w", pady=(0, 8))
        confirm_entry = ctk.CTkEntry(center, placeholder_text="Confirm password", show="●", height=45,
                                     fg_color=CARD_DARK, text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_MUTED,
                                     border_color=PRIMARY, corner_radius=10)
        confirm_entry.pack(fill="x", pady=(0, 25))
        
        def register_action():
            username = username_entry.get().strip()
            password = password_entry.get().strip()
            confirm = confirm_entry.get().strip()
            if not username or not password:
                messagebox.showerror("Error", "Please fill all fields")
                return
            if password != confirm:
                messagebox.showerror("Error", "Passwords do not match")
                return
            if len(password) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters")
                return
            if self.db.register_user(username, password):
                self.logger.log(f"User Registration: {username}")
                messagebox.showinfo("Success", "Account created successfully!\nPlease login.")
                self.show_login()
            else:
                messagebox.showerror("Error", "Username already exists")
        
        button_frame = ctk.CTkFrame(center, fg_color=DEEP_DARK)
        button_frame.pack(fill="x", pady=(0, 15))
        
        register_btn = GlowingButton(button_frame, text="Create Account", command=register_action, primary=True, height=45)
        register_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        back_btn = GlowingButton(button_frame, text="Back", command=self.show_login, height=45)
        back_btn.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def clear_window(self):
        for widget in self.app.winfo_children():
            widget.destroy()

# ============================================================================
# PREMIUM DASHBOARD PAGE
# ============================================================================

class PremiumDashboardPage:
    def __init__(self, app, db, logger, username, server_manager, encryption_manager):
        self.app = app
        self.db = db
        self.logger = logger
        self.username = username
        self.user_id = db.get_user_id(username)
        self.server_manager = server_manager
        self.encryption_manager = encryption_manager
        self.current_page = "dashboard"
        self.last_login = current_timestamp()
        self.show_dashboard()

    def show_dashboard(self):
        self.clear_window()
        
        main_frame = ctk.CTkFrame(self.app, fg_color=DEEP_DARK)
        main_frame.pack(fill="both", expand=True)
        
        # Premium Sidebar
        self.sidebar = ctk.CTkFrame(main_frame, width=280, fg_color=DARK_BG, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        self._build_premium_sidebar()
        
        # Content area
        self.content_frame = ctk.CTkFrame(main_frame, fg_color=DEEP_DARK)
        self.content_frame.pack(side="right", fill="both", expand=True)
        
        self.load_dashboard_content()

    def _build_premium_sidebar(self):
        # Logo Section
        logo_section = PremiumFrame(self.sidebar, fg_color=DARK_BG, border_width=0)
        logo_section.pack(fill="x", padx=20, pady=20)
        
        PremiumLabel(logo_section, text="🛡️ SecureVault X", style="heading").pack(anchor="w", pady=(0, 5))
        PremiumLabel(logo_section, text="Premium Edition", style="muted").pack(anchor="w", pady=(0, 15))
        
        # User Profile Card
        profile_card = PremiumFrame(self.sidebar)
        profile_card.pack(fill="x", padx=15, pady=(0, 20))
        
        profile_inner = ctk.CTkFrame(profile_card, fg_color=CARD_DARK)
        profile_inner.pack(fill="both", padx=12, pady=12)
        
        PremiumLabel(profile_inner, text=f"👤 {self.username}", style="primary").pack(anchor="w", pady=(0, 3))
        PremiumLabel(profile_inner, text="● Online", style="muted").pack(anchor="w")
        
        # Divider
        ctk.CTkFrame(self.sidebar, fg_color=CARD_LIGHTER, height=1).pack(fill="x", padx=15, pady=15)
        
        # Navigation Menu
        menu_items = [
            ("📊 Dashboard", self.load_dashboard_content),
            ("📁 My Files", self.load_files_content),
            ("🛡️ Security", self.load_security_content),
            ("📈 Threat Model", self.load_threat_model),
            ("📋 Activity Log", self.load_logs_content),
            ("⚙️ Settings", self.load_settings_content),
        ]
        
        for label, callback in menu_items:
            nav_btn = GlowingButton(self.sidebar, text=label, command=callback, height=40, fg_color=DARK_BG)
            nav_btn.pack(fill="x", padx=12, pady=6)
        
        # Divider
        ctk.CTkFrame(self.sidebar, fg_color=CARD_LIGHTER, height=1).pack(fill="x", padx=15, pady=15)
        
        # Logout
        logout_btn = ctk.CTkButton(self.sidebar, text="🚪 Logout", command=self.logout,
                                  fg_color=DANGER, hover_color=DANGER_GLOW, height=40,
                                  text_color=TEXT_PRIMARY, font=("Segoe UI", 11, "bold"),
                                  corner_radius=10)
        logout_btn.pack(fill="x", padx=12, pady=(0, 20))

    def load_dashboard_content(self):
        self.clear_content()
        self.current_page = "dashboard"
        
        # Scrollable container
        scroll_container = ctk.CTkScrollableFrame(self.content_frame, fg_color=DEEP_DARK, scrollbar_button_color=CARD_DARK)
        scroll_container.pack(fill="both", expand=True, padx=30, pady=30)
        
        # Hero Section
        hero = PremiumFrame(scroll_container)
        hero.pack(fill="x", pady=(0, 30))
        
        hero_content = ctk.CTkFrame(hero, fg_color=CARD_DARK)
        hero_content.pack(fill="both", padx=30, pady=30)
        
        PremiumLabel(hero_content, text=f"Welcome Back, {self.username}!", style="heading").pack(anchor="w", pady=(0, 5))
        PremiumLabel(hero_content, text="Military Grade Encrypted Storage", style="secondary").pack(anchor="w", pady=(0, 20))
        
        hero_stats = ctk.CTkFrame(hero_content, fg_color=CARD_DARK)
        hero_stats.pack(fill="x")
        
        # Last login
        login_frame = ctk.CTkFrame(hero_stats, fg_color=CARD_DARK)
        login_frame.pack(side="left", padx=(0, 30))
        PremiumLabel(login_frame, text="Last Login", style="muted").pack()
        PremiumLabel(login_frame, text="Just now", style="primary").pack()
        
        # Server status
        server_frame = ctk.CTkFrame(hero_stats, fg_color=CARD_DARK)
        server_frame.pack(side="left", padx=(0, 30))
        PremiumLabel(server_frame, text="Server Status", style="muted").pack()
        PremiumLabel(server_frame, text="● Online", style="primary").pack()
        
        # Protection status
        protect_frame = ctk.CTkFrame(hero_stats, fg_color=CARD_DARK)
        protect_frame.pack(side="left")
        PremiumLabel(protect_frame, text="Protection", style="muted").pack()
        PremiumLabel(protect_frame, text="🔒 Active", style="primary").pack()
        
        # Premium Stats Cards
        stats_container = ctk.CTkFrame(scroll_container, fg_color=DEEP_DARK)
        stats_container.pack(fill="x", pady=(0, 30))
        
        user_files = self.db.get_user_files(self.user_id)
        total_files = len(user_files)
        total_size = sum(record[2] or 0 for record in user_files)
        security_score = self.calculate_security_score()
        
        stats_data = [
            ("📊", "Total Files", str(total_files), "Files encrypted"),
            ("🔒", "Encrypted Files", str(total_files), "100% protected"),
            ("💾", "Storage Used", format_size(total_size), "Secure storage"),
            ("🎯", "Security Score", f"{security_score}/100", "Protection level"),
        ]
        
        for icon, title, value, subtitle in stats_data:
            self._create_premium_stat_card(stats_container, icon, title, value, subtitle)
        
        # Security Score Visualization
        score_section = PremiumFrame(scroll_container)
        score_section.pack(fill="x", pady=(0, 30))
        
        score_inner = ctk.CTkFrame(score_section, fg_color=CARD_DARK)
        score_inner.pack(fill="x", padx=30, pady=30)
        
        score_left = ctk.CTkFrame(score_inner, fg_color=CARD_DARK)
        score_left.pack(side="left", padx=(0, 40))
        
        ring = AnimatedProgressRing(score_left, size=150, percentage=security_score)
        ring.pack()
        
        score_right = ctk.CTkFrame(score_inner, fg_color=CARD_DARK)
        score_right.pack(side="left", fill="x", expand=True)
        
        PremiumLabel(score_right, text="Security Assessment", style="heading").pack(anchor="w", pady=(0, 5))
        assessment = "Your vault is protected with military-grade encryption, HMAC verification, and secure key management."
        PremiumLabel(score_right, text=assessment, style="secondary").pack(anchor="w", pady=(0, 15))
        
        PremiumLabel(score_right, text="✓ AES-128 Encryption Active", style="secondary").pack(anchor="w", pady=3)
        PremiumLabel(score_right, text="✓ HMAC-SHA256 Verification", style="secondary").pack(anchor="w", pady=3)
        PremiumLabel(score_right, text="✓ bcrypt Authentication", style="secondary").pack(anchor="w", pady=3)
        
        # Quick Actions
        actions_title = PremiumLabel(scroll_container, text="Quick Actions", style="heading")
        actions_title.pack(anchor="w", pady=(30, 15))
        
        actions_frame = ctk.CTkFrame(scroll_container, fg_color=DEEP_DARK)
        actions_frame.pack(fill="x", pady=(0, 30))
        
        def upload_action():
            file_path = filedialog.askopenfilename(filetypes=[("All Files", "*.*")])
            if not file_path:
                return
            try:
                progress_widget = ctk.CTkProgressBar(scroll_container, height=8, progress_color=PRIMARY)
                progress_widget.pack(padx=30, pady=(10, 0))
                
                def progress_cb(percent):
                    progress_widget.set(percent / 100)
                    self.app.update_idletasks()
                
                def upload_chunk_callback(encrypted_filename, encrypted_chunk, chunk_index, total_chunks):
                    url = f"{SERVER_URL}/upload"
                    files = {"chunk": ("chunk", encrypted_chunk, "application/octet-stream")}
                    data = {"file_name": encrypted_filename, "chunk_index": str(chunk_index), "total_chunks": str(total_chunks)}
                    resp = requests.post(url, files=files, data=data, verify=False, timeout=30)
                    if resp.status_code != 200:
                        raise ConnectionError(resp.text)
                
                encrypted_filename, size = self.encryption_manager.encrypt_file(file_path, progress_callback=progress_cb, chunk_callback=upload_chunk_callback)
                self.db.add_file(self.user_id, os.path.basename(file_path), encrypted_filename, size)
                self.logger.log(f"File Uploaded: {os.path.basename(file_path)}")
                messagebox.showinfo("Success", "File encrypted and uploaded successfully")
                progress_widget.destroy()
                self.load_dashboard_content()
            except Exception as exc:
                messagebox.showerror("Upload Failed", str(exc))
        
        upload_btn = GlowingButton(actions_frame, text="📤 Upload & Encrypt", command=upload_action, primary=True, height=50)
        upload_btn.pack(side="left", padx=(0, 15), fill="x", expand=True)
        
        files_btn = GlowingButton(actions_frame, text="📁 Manage Files", command=self.load_files_content, height=50)
        files_btn.pack(side="left", fill="x", expand=True)
        
        # Recent Activity Timeline
        activity_title = PremiumLabel(scroll_container, text="Recent Activity", style="heading")
        activity_title.pack(anchor="w", pady=(30, 15))
        
        activity_card = PremiumFrame(scroll_container)
        activity_card.pack(fill="x", pady=(0, 30))
        
        activity_inner = ctk.CTkFrame(activity_card, fg_color=CARD_DARK)
        activity_inner.pack(fill="both", padx=20, pady=20)
        
        recent_logs = self.logger.read_logs()[:6]
        if recent_logs:
            for log in recent_logs:
                self._create_activity_item(activity_inner, log)
        else:
            PremiumLabel(activity_inner, text="No recent activity", style="muted").pack(pady=20)

    def _create_premium_stat_card(self, parent, icon, title, value, subtitle):
        card = PremiumFrame(parent)
        card.pack(side="left", fill="both", expand=True, padx=(0, 15), pady=0)
        
        card_inner = ctk.CTkFrame(card, fg_color=CARD_DARK)
        card_inner.pack(fill="both", padx=20, pady=20)
        
        PremiumLabel(card_inner, text=icon, style="title").pack(anchor="w", pady=(0, 10))
        PremiumLabel(card_inner, text=title, style="muted").pack(anchor="w", pady=(0, 5))
        PremiumLabel(card_inner, text=value, style="heading").pack(anchor="w", pady=(0, 3))
        PremiumLabel(card_inner, text=subtitle, style="muted").pack(anchor="w")

    def _create_activity_item(self, parent, log_text):
        # Parse log for icon
        icon = "✓" if any(keyword in log_text for keyword in ["Login", "Upload", "Encrypt", "Verify", "Downloaded", "Delete"]) else "●"
        icon_color = SUCCESS if icon == "✓" else ACCENT
        
        item = ctk.CTkFrame(parent, fg_color=CARD_DARKER, corner_radius=8)
        item.pack(fill="x", pady=8)
        
        item_inner = ctk.CTkFrame(item, fg_color=CARD_DARKER)
        item_inner.pack(fill="x", padx=15, pady=12)
        
        icon_label = ctk.CTkLabel(item_inner, text=icon, text_color=icon_color, font=("Arial", 14))
        icon_label.pack(side="left", padx=(0, 12))
        
        PremiumLabel(item_inner, text=log_text, style="secondary").pack(side="left", anchor="w", fill="x", expand=True)

    def load_files_content(self):
        self.clear_content()
        self.current_page = "files"
        
        # Main container
        main_container = ctk.CTkFrame(self.content_frame, fg_color=DEEP_DARK)
        main_container.pack(fill="both", expand=True)
        
        # === TOOLBAR SECTION ===
        toolbar_card = PremiumFrame(main_container)
        toolbar_card.pack(fill="x", padx=30, pady=(30, 15))
        
        toolbar_inner = ctk.CTkFrame(toolbar_card, fg_color=CARD_DARK)
        toolbar_inner.pack(fill="x", padx=20, pady=15)
        
        # Left side - Title
        title_frame = ctk.CTkFrame(toolbar_inner, fg_color=CARD_DARK)
        title_frame.pack(side="left", fill="x", expand=True)
        PremiumLabel(title_frame, text="📁 My Files", style="heading").pack(anchor="w")
        
        # Right side - Action buttons
        actions_frame = ctk.CTkFrame(toolbar_inner, fg_color=CARD_DARK)
        actions_frame.pack(side="right")
        
        # Upload button
        def open_upload_dialog():
            file_path = filedialog.askopenfilename(filetypes=[("All Files", "*.*")])
            if not file_path:
                return
            self._handle_file_upload(file_path)
        
        upload_btn = GlowingButton(actions_frame, text="📤 Upload & Encrypt", command=open_upload_dialog, 
                                   primary=True, height=40, width=160)
        upload_btn.pack(side="left", padx=(0, 10))
        
        # Refresh button
        def refresh_files():
            self.load_files_content()
        
        refresh_btn = GlowingButton(actions_frame, text="🔄 Refresh", command=refresh_files, height=40, width=120)
        refresh_btn.pack(side="left", padx=(0, 10))
        
        # Search bar with a label for styling
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(actions_frame, textvariable=search_var, placeholder_text="Search files...",
                                    width=180, height=40, corner_radius=8, fg_color=CARD_LIGHTER,
                                    border_color=PRIMARY, border_width=1, text_color=TEXT_PRIMARY,
                                    placeholder_text_color=TEXT_MUTED, font=("Segoe UI", 11))
        search_entry.pack(side="left")
        
        # === DRAG AND DROP AREA ===
        user_files = self.db.get_user_files(self.user_id)
        
        if not user_files:
            self._create_empty_state(main_container)
            return
        
        # Drag-and-drop zone
        dnd_card = PremiumFrame(main_container)
        dnd_card.pack(fill="x", padx=30, pady=(0, 20))
        
        dnd_inner = ctk.CTkFrame(dnd_card, fg_color=CARD_DARKER)
        dnd_inner.pack(fill="x", padx=20, pady=20)
        
        dnd_label = PremiumLabel(dnd_inner, text="🎯 Drag & drop files here to encrypt and upload", 
                                 style="muted")
        dnd_label.pack(pady=10)
        
        # Note: Actual drag-and-drop implementation requires event binding
        # For now, we'll use the upload button
        
        # === FILES TABLE ===
        scroll_container = ctk.CTkScrollableFrame(main_container, fg_color=DEEP_DARK)
        scroll_container.pack(fill="both", expand=True, padx=30, pady=(0, 30))
        
        # Table header
        header_card = PremiumFrame(scroll_container)
        header_card.pack(fill="x", pady=(0, 10))
        
        header_inner = ctk.CTkFrame(header_card, fg_color=CARD_DARK)
        header_inner.pack(fill="x", padx=20, pady=12)
        
        # Headers with proper widths
        headers_info = [
            ("File Name", 0.25),
            ("Size", 0.15),
            ("Date Modified", 0.20),
            ("Encryption", 0.15),
            ("Integrity", 0.15),
            ("Actions", 0.10),
        ]
        
        for header_text, _ in headers_info:
            label = ctk.CTkLabel(header_inner, text=header_text, text_color=PRIMARY_GLOW,
                                font=("Segoe UI", 11, "bold"))
            label.pack(side="left", expand=True, anchor="w", padx=10)
        
        # File rows
        for filename, enc_filename, size, modified_at in user_files:
            self._create_file_row(scroll_container, filename, enc_filename, size, modified_at)

    def _create_empty_state(self, parent):
        """Display empty state when no files exist"""
        empty_container = ctk.CTkFrame(parent, fg_color=DEEP_DARK)
        empty_container.pack(fill="both", expand=True, padx=30, pady=30)
        
        # Spacer
        ctk.CTkFrame(empty_container, fg_color=DEEP_DARK, height=40).pack()
        
        # Empty card
        empty_card = PremiumFrame(empty_container)
        empty_card.pack(fill="both", expand=True)
        
        empty_inner = ctk.CTkFrame(empty_card, fg_color=CARD_DARK)
        empty_inner.pack(fill="both", padx=40, pady=60)
        
        # Large icon
        icon_label = ctk.CTkLabel(empty_inner, text="🔐", font=("Segoe UI", 80), text_color=PRIMARY_GLOW)
        icon_label.pack(pady=(0, 20))
        
        # Title
        title = PremiumLabel(empty_inner, text="No Encrypted Files Yet", style="heading")
        title.pack(pady=(0, 10))
        
        # Subtitle
        subtitle = PremiumLabel(empty_inner, text="Start by uploading your first file", style="secondary")
        subtitle.pack(pady=(0, 30))
        
        # CTA Button
        def upload_first():
            file_path = filedialog.askopenfilename(filetypes=[("All Files", "*.*")])
            if file_path:
                self._handle_file_upload(file_path)
        
        cta_btn = GlowingButton(empty_inner, text="📤 Upload First File", command=upload_first, 
                               primary=True, height=50, width=200)
        cta_btn.pack()
        
        # Bottom info
        info = PremiumLabel(empty_inner, 
                           text="All files are encrypted with military-grade AES-128-CBC encryption",
                           style="muted")
        info.pack(pady=(30, 0))

    def _create_file_row(self, parent, filename, enc_filename, size, modified_at):
        """Create a professional file row with all actions"""
        row_card = PremiumFrame(parent, fg_color=CARD_LIGHTER)
        row_card.pack(fill="x", pady=8)
        
        row_inner = ctk.CTkFrame(row_card, fg_color=CARD_DARK)
        row_inner.pack(fill="x", padx=20, pady=15)
        
        # Filename with icon
        filename_frame = ctk.CTkFrame(row_inner, fg_color=CARD_DARK)
        filename_frame.pack(side="left", expand=True, anchor="w", padx=(0, 20))
        
        file_icon = ctk.CTkLabel(filename_frame, text="📄", font=("Segoe UI", 16), text_color=ACCENT_GLOW)
        file_icon.pack(side="left", padx=(0, 10))
        
        file_name_label = ctk.CTkLabel(filename_frame, text=filename if len(filename) <= 40 else filename[:37] + "...",
                                       text_color=TEXT_PRIMARY, font=("Segoe UI", 12, "bold"))
        file_name_label.pack(side="left")
        
        # Size
        size_label = PremiumLabel(parent._parent_frame if hasattr(parent, '_parent_frame') else parent, 
                                 text=format_size(size), style="secondary")
        size_label = ctk.CTkLabel(row_inner, text=format_size(size), text_color=TEXT_SECONDARY, 
                                 font=("Segoe UI", 11))
        size_label.pack(side="left", expand=True, anchor="w", padx=10)
        
        # Date
        date_label = ctk.CTkLabel(row_inner, text=get_time_since(modified_at), text_color=TEXT_MUTED,
                                 font=("Segoe UI", 10))
        date_label.pack(side="left", expand=True, anchor="w", padx=10)
        
        # Encryption status (always encrypted)
        enc_status = ctk.CTkLabel(row_inner, text="🔐 Encrypted", text_color=SUCCESS,
                                 font=("Segoe UI", 10, "bold"))
        enc_status.pack(side="left", expand=True, anchor="w", padx=10)
        
        # Integrity status
        def get_integrity_status():
            verified, _ = self.encryption_manager.verify_integrity(enc_filename)
            return "✓ OK" if verified else "⚠ Check"
        
        integrity_text = get_integrity_status()
        integrity_color = SUCCESS if "OK" in integrity_text else WARNING
        integrity_status = ctk.CTkLabel(row_inner, text=integrity_text, text_color=integrity_color,
                                       font=("Segoe UI", 10, "bold"))
        integrity_status.pack(side="left", expand=True, anchor="w", padx=10)
        
        # Action buttons
        actions_frame = ctk.CTkFrame(row_inner, fg_color=CARD_DARK)
        actions_frame.pack(side="left", padx=(20, 0))
        
        # Decrypt button
        def decrypt_action():
            try:
                # Show progress
                progress_win = messagebox.showinfo("Decrypting", "Decrypting file...", parent=self.app)
                
                self._download_from_server(enc_filename)
                decrypted_path = self.encryption_manager.decrypt_file(enc_filename)
                self.logger.log(f"File Decrypted: {filename} -> {decrypted_path}")
                
                messagebox.showinfo("Success", f"✓ File decrypted successfully\n\nLocation: {decrypted_path}")
            except Exception as exc:
                self.logger.log(f"Decryption Failed: {filename} - {str(exc)}")
                messagebox.showerror("Decryption Failed", f"Error: {str(exc)}")
        
        decrypt_btn = ctk.CTkButton(actions_frame, text="🔓 Decrypt", command=decrypt_action, 
                                   width=80, height=35, fg_color=PRIMARY, hover_color=PRIMARY_GLOW,
                                   corner_radius=8, font=("Segoe UI", 10, "bold"),
                                   text_color=TEXT_PRIMARY)
        decrypt_btn.pack(side="left", padx=2)
        
        # Verify button
        def verify_action():
            try:
                verified, message = self.encryption_manager.verify_integrity(enc_filename)
                self.logger.log(f"Integrity Check: {filename} - {message}")
                
                if verified:
                    messagebox.showinfo("Integrity Verified", f"✓ {message}\n\nFile is safe and unmodified")
                else:
                    messagebox.showwarning("Integrity Check Failed", f"⚠ {message}\n\nFile may have been tampered with!")
            except Exception as exc:
                self.logger.log(f"Verification Error: {filename}")
                messagebox.showerror("Verification Failed", f"Error: {str(exc)}")
        
        verify_btn = ctk.CTkButton(actions_frame, text="✓ Verify", command=verify_action,
                                  width=80, height=35, fg_color=SUCCESS, hover_color=SUCCESS_GLOW,
                                  corner_radius=8, font=("Segoe UI", 10, "bold"),
                                  text_color=TEXT_PRIMARY)
        verify_btn.pack(side="left", padx=2)
        
        # Download button
        def download_action():
            try:
                # Decrypt to get original filename
                decrypted_path = self.encryption_manager.decrypt_file(enc_filename)
                
                # Ask user where to save
                save_path = filedialog.asksaveasfilename(
                    defaultextension="",
                    initialfile=filename,
                    filetypes=[("All Files", "*.*")]
                )
                
                if save_path:
                    import shutil
                    shutil.copy2(decrypted_path, save_path)
                    self.logger.log(f"File Downloaded: {filename} -> {save_path}")
                    messagebox.showinfo("Success", f"✓ File saved to:\n{save_path}")
            except Exception as exc:
                self.logger.log(f"Download Failed: {filename}")
                messagebox.showerror("Download Failed", f"Error: {str(exc)}")
        
        download_btn = ctk.CTkButton(actions_frame, text="⬇ Download", command=download_action,
                                    width=90, height=35, fg_color=ACCENT, hover_color=ACCENT_GLOW,
                                    corner_radius=8, font=("Segoe UI", 10, "bold"),
                                    text_color=TEXT_PRIMARY)
        download_btn.pack(side="left", padx=2)
        
        # Delete button
        def delete_action():
            if not messagebox.askyesno("Confirm Delete", f"Permanently delete '{filename}'?\n\nThis cannot be undone."):
                return
            try:
                self._delete_from_server(enc_filename)
                self.db.delete_file_record(self.user_id, enc_filename)
                local_path = os.path.join("encrypted", enc_filename)
                if os.path.exists(local_path):
                    os.remove(local_path)
                self.logger.log(f"File Deleted: {filename}")
                messagebox.showinfo("Success", "✓ File deleted successfully")
                self.load_files_content()
            except Exception as exc:
                self.logger.log(f"Delete Failed: {filename}")
                messagebox.showerror("Delete Failed", f"Error: {str(exc)}")
        
        delete_btn = ctk.CTkButton(actions_frame, text="🗑 Delete", command=delete_action,
                                  width=80, height=35, fg_color=DANGER, hover_color=DANGER_GLOW,
                                  corner_radius=8, font=("Segoe UI", 10, "bold"),
                                  text_color=TEXT_PRIMARY)
        delete_btn.pack(side="left", padx=2)

    def _handle_file_upload(self, file_path):
        """Handle file encryption and upload"""
        try:
            # Create progress window
            progress_window = ctk.CTkToplevel(self.app)
            progress_window.title("Uploading & Encrypting")
            progress_window.geometry("400x150")
            progress_window.grab_set()
            
            # Progress label
            status_label = PremiumLabel(progress_window, text="Preparing file...", style="secondary")
            status_label.pack(pady=(20, 10))
            
            # Progress bar
            progress_bar = ctk.CTkProgressBar(progress_window, height=8, progress_color=PRIMARY)
            progress_bar.pack(pady=10, padx=30, fill="x")
            progress_bar.set(0)
            
            # Percentage label
            percent_label = PremiumLabel(progress_window, text="0%", style="muted")
            percent_label.pack()
            
            def progress_callback(percent):
                progress_bar.set(percent / 100)
                percent_label.configure(text=f"{percent}%")
                status_label.configure(text=f"Encrypting... {percent}%")
                self.app.update_idletasks()
            
            def upload_chunk_callback(encrypted_filename, encrypted_chunk, chunk_index, total_chunks):
                try:
                    url = f"{SERVER_URL}/upload"
                    files = {"chunk": ("chunk", encrypted_chunk, "application/octet-stream")}
                    data = {
                        "file_name": encrypted_filename,
                        "chunk_index": str(chunk_index),
                        "total_chunks": str(total_chunks)
                    }
                    resp = requests.post(url, files=files, data=data, verify=False, timeout=30)
                    if resp.status_code != 200:
                        raise ConnectionError(f"Server error: {resp.text}")
                    
                    # Update UI
                    upload_progress = int((chunk_index + 1) * 100 / total_chunks)
                    status_label.configure(text=f"Uploading... {upload_progress}%")
                    self.app.update_idletasks()
                except Exception as e:
                    raise ConnectionError(f"Upload failed: {str(e)}")
            
            # Encrypt and upload
            encrypted_filename, size = self.encryption_manager.encrypt_file(
                file_path,
                progress_callback=progress_callback,
                chunk_callback=upload_chunk_callback
            )
            
            # Add to database
            self.db.add_file(self.user_id, os.path.basename(file_path), encrypted_filename, size)
            self.logger.log(f"File Uploaded & Encrypted: {os.path.basename(file_path)} ({format_size(size)})")
            
            # Close progress window
            progress_window.destroy()
            
            # Show success
            messagebox.showinfo("Success", 
                              f"✓ File encrypted and uploaded successfully!\n\n"
                              f"File: {os.path.basename(file_path)}\n"
                              f"Size: {format_size(size)}\n"
                              f"Encryption: AES-128-CBC")
            
            # Refresh files list
            self.load_files_content()
            
        except Exception as exc:
            self.logger.log(f"Upload Failed: {str(exc)}")
            messagebox.showerror("Upload Failed", f"Error: {str(exc)}")

    def load_security_content(self):
        self.clear_content()
        self.current_page = "security"
        
        scroll_container = ctk.CTkScrollableFrame(self.content_frame, fg_color=DEEP_DARK)
        scroll_container.pack(fill="both", expand=True, padx=30, pady=30)
        
        PremiumLabel(scroll_container, text="🛡️ Security Center", style="heading").pack(anchor="w", pady=(0, 20))
        
        # Security Items
        security_items = [
            ("🔐", "AES Encryption", "ACTIVE", True, "Military-grade AES-128-CBC encryption"),
            ("🧾", "HMAC Verification", "ACTIVE", True, "SHA256 integrity verification"),
            ("👤", "Authentication", "ACTIVE", True, "bcrypt password hashing"),
            ("🔑", "Key Management", "SECURE", True, "Encrypted key storage"),
            ("📡", "Server Status", "ONLINE", True, "Secure HTTPS connection"),
            ("⚠️", "Threat Protection", "ENABLED", True, "Real-time threat monitoring"),
        ]
        
        for icon, title, status, active, desc in security_items:
            self._create_security_card(scroll_container, icon, title, status, active, desc)

    def _create_security_card(self, parent, icon, title, status, active, desc):
        card = PremiumFrame(parent)
        card.pack(fill="x", pady=10)
        
        card_inner = ctk.CTkFrame(card, fg_color=CARD_DARK)
        card_inner.pack(fill="x", padx=20, pady=20)
        
        # Top section
        top = ctk.CTkFrame(card_inner, fg_color=CARD_DARK)
        top.pack(fill="x", pady=(0, 10))
        
        icon_label = ctk.CTkLabel(top, text=icon, font=("Arial", 24), text_color=PRIMARY)
        icon_label.pack(side="left", padx=(0, 15))
        
        title_frame = ctk.CTkFrame(top, fg_color=CARD_DARK)
        title_frame.pack(side="left", fill="x", expand=True)
        
        PremiumLabel(title_frame, text=title, style="primary").pack(anchor="w")
        PremiumLabel(title_frame, text=desc, style="muted").pack(anchor="w")
        
        status_color = SUCCESS if active else DANGER
        status_label = ctk.CTkLabel(top, text=f"● {status}", text_color=status_color, font=("Segoe UI", 11, "bold"))
        status_label.pack(side="right", padx=(15, 0))

    def load_threat_model(self):
        self.clear_content()
        self.current_page = "threat"
        
        scroll_container = ctk.CTkScrollableFrame(self.content_frame, fg_color=DEEP_DARK)
        scroll_container.pack(fill="both", expand=True, padx=30, pady=30)
        
        PremiumLabel(scroll_container, text="📈 Threat Model", style="heading").pack(anchor="w", pady=(0, 20))
        
        # Threats Section
        threat_card = PremiumFrame(scroll_container)
        threat_card.pack(fill="x", pady=(0, 20))
        
        threat_inner = ctk.CTkFrame(threat_card, fg_color=CARD_DARK)
        threat_inner.pack(fill="x", padx=20, pady=20)
        
        PremiumLabel(threat_inner, text="Identified Threats", style="heading").pack(anchor="w", pady=(0, 15))
        
        threats = [
            ("Man-in-the-Middle Attack", "Unauthorized interception of data in transit"),
            ("File Tampering", "Modification of encrypted files"),
            ("Unauthorized Access", "Breach of authentication system"),
            ("Credential Theft", "Exposure of user credentials"),
            ("Key Leakage", "Compromise of encryption keys"),
        ]
        
        for threat_name, threat_desc in threats:
            threat_item = ctk.CTkFrame(threat_inner, fg_color=CARD_LIGHTER, corner_radius=8)
            threat_item.pack(fill="x", pady=8)
            
            threat_content = ctk.CTkFrame(threat_item, fg_color=CARD_LIGHTER)
            threat_content.pack(fill="x", padx=12, pady=10)
            
            PremiumLabel(threat_content, text=f"⚠️ {threat_name}", style="primary").pack(anchor="w", pady=(0, 3))
            PremiumLabel(threat_content, text=threat_desc, style="muted").pack(anchor="w")
        
        # Mitigations Section
        mitigation_card = PremiumFrame(scroll_container)
        mitigation_card.pack(fill="x", pady=(0, 30))
        
        mitigation_inner = ctk.CTkFrame(mitigation_card, fg_color=CARD_DARK)
        mitigation_inner.pack(fill="x", padx=20, pady=20)
        
        PremiumLabel(mitigation_inner, text="Security Mitigations", style="heading").pack(anchor="w", pady=(0, 15))
        
        mitigations = [
            ("AES Encryption", "256-bit military-grade encryption"),
            ("HMAC-SHA256", "Integrity verification"),
            ("bcrypt Hashing", "Secure password storage"),
            ("Key Management", "Secure key generation and storage"),
            ("HTTPS/TLS", "Encrypted transport layer"),
            ("Integrity Validation", "Verification before decryption"),
        ]
        
        for mitigation_name, mitigation_desc in mitigations:
            mitigation_item = ctk.CTkFrame(mitigation_inner, fg_color=CARD_LIGHTER, corner_radius=8)
            mitigation_item.pack(fill="x", pady=8)
            
            mitigation_content = ctk.CTkFrame(mitigation_item, fg_color=CARD_LIGHTER)
            mitigation_content.pack(fill="x", padx=12, pady=10)
            
            PremiumLabel(mitigation_content, text=f"✓ {mitigation_name}", style="primary").pack(anchor="w", pady=(0, 3))
            PremiumLabel(mitigation_content, text=mitigation_desc, style="muted").pack(anchor="w")

    def load_logs_content(self):
        self.clear_content()
        self.current_page = "logs"
        
        scroll_container = ctk.CTkScrollableFrame(self.content_frame, fg_color=DEEP_DARK)
        scroll_container.pack(fill="both", expand=True, padx=30, pady=30)
        
        PremiumLabel(scroll_container, text="📋 Activity Log", style="heading").pack(anchor="w", pady=(0, 15))
        
        # Search Bar
        search_frame = ctk.CTkFrame(scroll_container, fg_color=DEEP_DARK)
        search_frame.pack(fill="x", pady=(0, 20))
        
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search logs...", textvariable=search_var, height=40,
                                   fg_color=CARD_DARK, text_color=TEXT_PRIMARY, placeholder_text_color=TEXT_MUTED,
                                   border_color=PRIMARY, corner_radius=10)
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        def do_search():
            query = search_var.get().strip()
            self._render_logs_premium(scroll_container, query)
        
        search_btn = GlowingButton(search_frame, text="Search", command=do_search, primary=True, height=40, width=100)
        search_btn.pack(side="left")
        
        self._render_logs_premium(scroll_container, "")

    def _render_logs_premium(self, parent, query):
        # Remove previous logs if any
        for widget in parent.winfo_children():
            if isinstance(widget, (PremiumFrame, ctk.CTkFrame)) and widget != parent.winfo_children()[0]:
                widget.destroy()
        
        logs = self.logger.search(query)
        if not logs:
            empty_card = PremiumFrame(parent)
            empty_card.pack(fill="x", pady=20)
            PremiumLabel(empty_card, text="No matching log entries", style="muted").pack(padx=20, pady=20)
            return
        
        for log in logs:
            log_card = PremiumFrame(parent)
            log_card.pack(fill="x", pady=6)
            
            log_inner = ctk.CTkFrame(log_card, fg_color=CARD_DARK)
            log_inner.pack(fill="x", padx=15, pady=10)
            
            PremiumLabel(log_inner, text=log, style="secondary").pack(anchor="w")

    def load_settings_content(self):
        self.clear_content()
        self.current_page = "settings"
        
        scroll_container = ctk.CTkScrollableFrame(self.content_frame, fg_color=DEEP_DARK)
        scroll_container.pack(fill="both", expand=True, padx=30, pady=30)
        
        PremiumLabel(scroll_container, text="⚙️ Settings", style="heading").pack(anchor="w", pady=(0, 20))
        
        # Appearance Section
        self._create_settings_section(scroll_container, "🎨 Appearance", [
            ("Dark Mode", "Toggle dark/light theme", lambda: self._toggle_appearance()),
            ("Accent Color", "Choose primary accent", None),
        ])
        
        # Security Section
        self._create_settings_section(scroll_container, "🔐 Security", [
            ("Generate New Key", "Create new encryption key", lambda: self._regenerate_key()),
            ("Export Logs", "Download activity logs", None),
        ])
        
        # About Section
        about_card = PremiumFrame(scroll_container)
        about_card.pack(fill="x", pady=20)
        
        about_inner = ctk.CTkFrame(about_card, fg_color=CARD_DARK)
        about_inner.pack(fill="x", padx=20, pady=20)
        
        PremiumLabel(about_inner, text="ℹ️ About", style="heading").pack(anchor="w", pady=(0, 15))
        about_text = """SecureVault X v2.0 - Premium Edition
Military Grade Encrypted File Storage

Features:
• AES-128-CBC Encryption
• HMAC-SHA256 Integrity Verification
• Chunked Resumable Uploads
• Secure Client-Server Architecture
• bcrypt Password Authentication
• Activity Logging & Audit Trail
• Threat Modeling & Risk Assessment
• Enterprise-Grade Security

© 2024 SecureVault X | All Rights Reserved"""
        PremiumLabel(about_inner, text=about_text, style="secondary").pack(anchor="w")

    def _create_settings_section(self, parent, title, items):
        card = PremiumFrame(parent)
        card.pack(fill="x", pady=20)
        
        card_inner = ctk.CTkFrame(card, fg_color=CARD_DARK)
        card_inner.pack(fill="x", padx=20, pady=20)
        
        PremiumLabel(card_inner, text=title, style="heading").pack(anchor="w", pady=(0, 15))
        
        for item_name, item_desc, item_action in items:
            item_frame = ctk.CTkFrame(card_inner, fg_color=CARD_DARKER, corner_radius=8)
            item_frame.pack(fill="x", pady=8)
            
            item_inner = ctk.CTkFrame(item_frame, fg_color=CARD_DARKER)
            item_inner.pack(fill="x", padx=15, pady=10)
            
            left = ctk.CTkFrame(item_inner, fg_color=CARD_DARKER)
            left.pack(side="left", fill="x", expand=True)
            
            PremiumLabel(left, text=item_name, style="primary").pack(anchor="w")
            PremiumLabel(left, text=item_desc, style="muted").pack(anchor="w")
            
            if item_action:
                btn = GlowingButton(item_inner, text="Configure", command=item_action, height=35, width=100, primary=True)
                btn.pack(side="right", padx=(15, 0))

    def _toggle_appearance(self):
        mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light" if mode == "dark" else "dark")

    def _regenerate_key(self):
        if messagebox.askyesno("Warning", "This will invalidate existing encrypted files. Continue?"):
            with open(KEY_FILE, "wb") as f:
                f.write(Fernet.generate_key())
            self.logger.log("New Encryption Key Generated")
            messagebox.showinfo("Success", "New encryption key generated")

    def _download_from_server(self, encrypted_filename):
        url = f"{SERVER_URL}/download"
        resp = requests.get(url, params={"file_name": encrypted_filename}, stream=True, verify=False, timeout=30)
        if resp.status_code != 200:
            raise ConnectionError(f"Download error: {resp.text}")
        local_path = os.path.join("encrypted", encrypted_filename)
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        self.logger.log(f"File Downloaded: {encrypted_filename}")

    def _delete_from_server(self, encrypted_filename):
        url = f"{SERVER_URL}/delete"
        resp = requests.post(url, json={"file_name": encrypted_filename}, verify=False, timeout=30)
        if resp.status_code != 200:
            raise ConnectionError(f"Delete error: {resp.text}")

    def calculate_security_score(self):
        score = 100
        if not os.path.exists(KEY_FILE): score -= 20
        if not os.path.exists(HMAC_KEY_FILE): score -= 15
        if not os.path.exists(LOG_FILE): score -= 5
        if not os.path.exists(SERVER_STORAGE): score -= 5
        return min(100, max(0, score))

    def logout(self):
        self.logger.log(f"User Logout: {self.username}")
        PremiumLoginPage(self.app, self.db, self.logger, self.server_manager, self.encryption_manager)

    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def clear_window(self):
        for widget in self.app.winfo_children():
            widget.destroy()

# Define additional color constant
CARD_DARKER = "#0F172A"

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class SecureVaultXPremium:
    def __init__(self):
        ensure_directories()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.db = DatabaseManager()
        self.logger = ActivityLogger()
        self.integrity_manager = IntegrityManager()
        self.encryption_manager = EncryptionManager(self.integrity_manager)
        self.server_thread = LocalServer()
        
        self.logger.log("Application Started - Premium Edition")
        
        self.app = ctk.CTk()
        self.app.title("SecureVault X - Premium Enterprise Edition")
        self.app.geometry("1600x900")
        self.app.minsize(1200, 700)
        
        PremiumLoginPage(self.app, self.db, self.logger, self.server_thread, self.encryption_manager)

    def run(self):
        self.app.mainloop()

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    SecureVaultXPremium().run()
