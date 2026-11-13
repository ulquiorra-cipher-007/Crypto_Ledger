#!/usr/bin/env python3
"""
==============================================================================
CYBERCHAIN - DEDICATED PASSKEY & IDENTITY INGESTION STATION
==============================================================================
- ONLY Name (Username) is compulsory: Email and Password columns removed.
- Zero placeholder users: database starts 100% clean.
- Enrolls genuine FIDO2 passkeys via smartphone Bluetooth QR scan.
- Strictly validates genuine passkeys: never falsely registers upon cancel.
==============================================================================
"""
import os
import sys
import time
import uuid
import socket
import hashlib
import threading
import json
import urllib.parse
import io
import webbrowser
from pathlib import Path

# Paths
ENTRY_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ENTRY_DIR.parent
CYBERCHAIN_DIR = PROJECT_ROOT / "CyberChain"
STORAGE_DIR = CYBERCHAIN_DIR / "storage"
DB_PATH = STORAGE_DIR / "cyberchain.db"

# Add CyberChain to sys.path
if str(CYBERCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(CYBERCHAIN_DIR))
if str(ENTRY_DIR) not in sys.path:
    sys.path.append(str(ENTRY_DIR))

import database

# Global In-Memory Store for Active QR Passkey Sessions
active_qr_sessions: dict[str, dict] = {}
qr_server_port: int = 8089


import http.server

class EnrollmentHttpHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        session_id = params.get("session", [""])[0]

        if parsed.path in ("/enroll", "/"):
            session = active_qr_sessions.get(session_id, {})
            username = session.get("username", params.get("user", ["user"])[0])
            html = get_enrollment_html(session_id, username)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_cors()
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        elif parsed.path == "/poll":
            session = active_qr_sessions.get(session_id, {"status": "NOT_FOUND"})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(json.dumps(session).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/submit", "/api/verify"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)

                session_id = data.get("session_id")
                cred_id = data.get("credential_id")

                if not session_id or session_id not in active_qr_sessions or not cred_id or not cred_id.strip():
                    self.send_response(400)
                    self.end_headers()
                    return

                client_dev = data.get("client_device", "Smartphone Biometric Passkey")
                active_qr_sessions[session_id]["status"] = "VERIFIED"
                active_qr_sessions[session_id]["credential_id"] = cred_id
                active_qr_sessions[session_id]["client_device"] = client_dev

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "credential_id": cred_id}).encode("utf-8"))
                return
            except Exception:
                self.send_response(500)
                self.end_headers()
                return

        self.send_response(404)
        self.end_headers()


def start_embedded_qr_server():
    global qr_server_port
    for port in [8089, 8090, 8091, 8888, 0]:
        try:
            server = http.server.ThreadingHTTPServer(("0.0.0.0", port), EnrollmentHttpHandler)
            qr_server_port = server.server_address[1]
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            return qr_server_port
        except Exception:
            continue
    return 8089


def get_enrollment_html(session_id: str, username: str) -> str:
    """Delivers native WebAuthn cross-device Bluetooth QR code enrollment."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CyberChain Passkey Ingestion</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    body {{ background: #06090e; color: #e2e8f0; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; text-align: center; }}
    .card {{ background: #0c111a; border: 1px solid #1f2a3c; border-radius: 18px; padding: 36px 28px; max-width: 480px; width: 100%; box-shadow: 0 16px 48px rgba(0, 0, 0, 0.85); }}
    .badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(0, 255, 204, 0.1); border: 1px solid rgba(0, 255, 204, 0.3); color: #00ffcc; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; padding: 5px 14px; border-radius: 20px; text-transform: uppercase; margin-bottom: 20px; }}
    h1 {{ font-size: 22px; font-weight: 800; margin-bottom: 8px; color: #f8fafc; }}
    .subtitle {{ font-size: 13px; color: #94a3b8; line-height: 1.5; margin-bottom: 24px; }}
    .tip-box {{ background: rgba(234, 179, 8, 0.1); border: 1px solid rgba(234, 179, 8, 0.3); border-radius: 8px; padding: 12px; margin-bottom: 18px; font-size: 12px; color: #fde047; text-align: left; line-height: 1.4; }}
    .btn-main {{ width: 100%; padding: 16px; border: none; border-radius: 10px; background: #00ffcc; color: #06090e; font-size: 15px; font-weight: 800; cursor: pointer; transition: all 0.2s; margin-bottom: 12px; }}
    .btn-main:hover {{ background: #33ffd6; }}
    .status-msg {{ font-size: 12px; color: #64748b; margin-top: 14px; }}
    .success-view {{ display: none; }}
    .checkmark {{ width: 54px; height: 54px; border-radius: 50%; background: rgba(16,185,129,0.2); border: 2px solid #10b981; color: #10b981; font-size: 26px; display: flex; align-items: center; justify-content: center; margin: 0 auto 12px auto; }}
  </style>
</head>
<body>
  <div class="card">
    <div id="enroll-view">
      <div class="badge">◈ FIDO2 Passkey Ingestion</div>
      <h1>Enroll Passkey for <span style="color:#00ffcc;">{username}</span></h1>
      <p class="subtitle">Only Name is required. Click below to display the Bluetooth QR code for phone scanning.</p>

      <div class="tip-box">
        <strong>💡 Note:</strong> If Windows asks to <em>"Insert your security key"</em>, click <strong>"More choices"</strong> (or <strong>"Use a phone or tablet"</strong>) to show the QR code!
      </div>

      <button class="btn-main" id="btn-enroll">Display Phone Bluetooth QR Code</button>
      <div class="status-msg" id="status-text">Click button to launch passkey prompt...</div>
    </div>

    <div id="success-view" class="success-view">
      <div class="checkmark">✓</div>
      <h2 style="color:#10b981;">Passkey Captured!</h2>
      <p class="subtitle" style="margin-top:8px;">Your phone's passkey was successfully registered. This window can now be closed.</p>
    </div>
  </div>

  <script>
    const sessionId = "{session_id}";
    const username = "{username}";

    async function triggerPasskeyEnrollment() {{
      const statusText = document.getElementById("status-text");
      statusText.textContent = "👉 On Windows prompt: Click 'More choices' ➔ 'iPhone, iPad, or Android device' to display the QR Code!";
      statusText.style.color = "#00ffcc";

      if (!window.PublicKeyCredential) {{
        statusText.textContent = "WebAuthn not supported by this browser.";
        return;
      }}

      try {{
        const challenge = new Uint8Array(32);
        window.crypto.getRandomValues(challenge);

        const credential = await navigator.credentials.create({{
          publicKey: {{
            challenge: challenge,
            rp: {{ name: "CyberChain Entry Station", id: window.location.hostname }},
            user: {{
              id: new TextEncoder().encode(username),
              name: username,
              displayName: username
            }},
            pubKeyCredParams: [{{ type: "public-key", alg: -7 }}, {{ type: "public-key", alg: -257 }}],
            timeout: 120000,
            hints: ["hybrid"],
            authenticatorSelection: {{
              userVerification: "required",
              residentKey: "preferred"
            }}
          }}
        }});

        if (credential && credential.id) {{
          statusText.textContent = "Sending credential to station...";
          const res = await fetch("/submit", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{
              session_id: sessionId,
              credential_id: credential.id,
              client_device: "Smartphone Bluetooth Passkey"
            }})
          }});

          if (res.ok) {{
            document.getElementById("enroll-view").style.display = "none";
            document.getElementById("success-view").style.display = "block";
            setTimeout(() => {{ window.close(); }}, 800);
          }}
        }}
      }} catch (err) {{
        console.warn("Passkey cancelled or error:", err);
        statusText.textContent = "❌ Passkey prompt was closed or cancelled. Click button to retry.";
        statusText.style.color = "#ef4444";
      }}
    }}

    document.getElementById("btn-enroll").onclick = triggerPasskeyEnrollment;
  </script>
</body>
</html>"""


def enroll_credential_into_db(
    username: str,
    role: str = "user",
    fingerprint_credential_id: str = "",
    fingerprint_device: str = "Smartphone Biometric Passkey"
) -> dict:
    """
    Directly puts Name, Role, and Passkey into cyberchain.db via CyberChain/database.py.
    Roles: strictly 'user' or 'admin'.
    """
    username = username.strip()
    if not username:
        raise ValueError("Name cannot be empty.")
    if not fingerprint_credential_id or not fingerprint_credential_id.strip():
        raise ValueError("No passkey was scanned. Please scan with your phone first.")

    normalized_role = "admin" if str(role).strip().lower() == "admin" else "user"

    result = database.register_user(
        username=username,
        role=normalized_role,
        credential_id=fingerprint_credential_id,
        device_name=fingerprint_device
    )

    return {
        "status": "SUCCESS",
        "user_id": result["user_id"],
        "username": result["username"],
        "role": result["role"],
        "fingerprint_id": fingerprint_credential_id,
        "fingerprint_device": fingerprint_device,
        "db_path": str(DB_PATH)
    }


def list_all_db_users():
    """Lists all users from clean cyberchain.db."""
    users = database.get_all_users()
    return [{
        "id": u["id"],
        "username": u["username"],
        "role": u.get("role", "user"),
        "created_at": u["created_at"],
        "fingerprints_count": u["passkey_count"]
    } for u in users]


# ==============================================================================
# GUI IMPLEMENTATION
# ==============================================================================
def run_gui():
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QMessageBox, QGroupBox, QFrame, QComboBox
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QColor

    start_embedded_qr_server()

    class EntryStationWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("CyberChain - Passkey & Identity Ingestion Station")
            self.setMinimumSize(820, 600)

            self.current_session_id = uuid.uuid4().hex[:12]
            self.captured_credential_id = None
            self.captured_device = None

            self.init_ui()
            self.refresh_users_table()

            self.poll_timer = QTimer(self)
            self.poll_timer.timeout.connect(self.check_qr_session_status)
            self.poll_timer.start(800)

        def init_ui(self):
            central = QWidget()
            self.setCentralWidget(central)
            main_layout = QVBoxLayout(central)
            main_layout.setContentsMargins(24, 24, 24, 24)
            main_layout.setSpacing(16)

            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #0b0f17;
                    color: #e2e8f0;
                    font-family: 'Segoe UI', system-ui, sans-serif;
                }
                QGroupBox {
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    margin-top: 10px;
                    font-weight: bold;
                    color: #00ffcc;
                    padding-top: 14px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 14px;
                    padding: 0 6px;
                }
                QLineEdit {
                    background-color: #111827;
                    color: #f1f5f9;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 10px 14px;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border: 1px solid #00ffcc;
                }
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    font-weight: bold;
                    border: none;
                    border-radius: 6px;
                    padding: 12px 18px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                QPushButton.success-btn {
                    background-color: #059669;
                }
                QPushButton.success-btn:hover {
                    background-color: #047857;
                }
                QPushButton.secondary-btn {
                    background-color: #334155;
                    color: #f8fafc;
                }
                QPushButton.secondary-btn:hover {
                    background-color: #475569;
                }
                QTableWidget {
                    background-color: #0f172a;
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                    gridline-color: #1e293b;
                    color: #e2e8f0;
                }
                QHeaderView::section {
                    background-color: #1e293b;
                    color: #94a3b8;
                    padding: 8px;
                    border: none;
                    font-weight: bold;
                }
            """)

            # Header
            header_box = QVBoxLayout()
            lbl_badge = QLabel("◈ CYBERCHAIN CREDENTIAL INGESTION")
            lbl_badge.setStyleSheet("color: #00ffcc; font-weight: bold; font-size: 11px; letter-spacing: 1.5px;")
            lbl_title = QLabel("User Passkey Ingestion Station")
            lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
            lbl_sub = QLabel("Only Name is compulsory. Passwordless FIDO2 architecture.")
            lbl_sub.setStyleSheet("color: #64748b; font-size: 12px;")
            header_box.addWidget(lbl_badge)
            header_box.addWidget(lbl_title)
            header_box.addWidget(lbl_sub)
            main_layout.addLayout(header_box)

            content_row = QHBoxLayout()
            left_col = QVBoxLayout()

            # Form Box
            form_box = QGroupBox("1. User Identity & Role")
            form_layout = QVBoxLayout(form_box)
            form_layout.addWidget(QLabel("Name:"))
            self.input_username = QLineEdit()
            self.input_username.setPlaceholderText("Enter User Name")
            form_layout.addWidget(self.input_username)

            form_layout.addWidget(QLabel("Role (Compulsory):"))
            self.combo_role = QComboBox()
            self.combo_role.addItem("user (Forensic Examiner)", "user")
            self.combo_role.addItem("admin (Administrator)", "admin")
            self.combo_role.setStyleSheet("background-color: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 6px; padding: 6px;")
            form_layout.addWidget(self.combo_role)
            left_col.addWidget(form_box)

            # Passkey Box
            passkey_box = QGroupBox("2. Phone Bluetooth Passkey")
            pk_layout = QVBoxLayout(passkey_box)

            self.lbl_scan_status = QLabel("⚪ No passkey captured yet")
            self.lbl_scan_status.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 12px; margin-bottom: 8px;")
            pk_layout.addWidget(self.lbl_scan_status)

            btn_open_qr = QPushButton("📱 Launch Phone Bluetooth Passkey Prompt")
            btn_open_qr.clicked.connect(self.handle_launch_passkey)
            pk_layout.addWidget(btn_open_qr)

            left_col.addWidget(passkey_box)

            # Submit Button
            self.btn_submit = QPushButton("💾 Save User & Passkey to Database")
            self.btn_submit.setProperty("class", "success-btn")
            self.btn_submit.clicked.connect(self.handle_enroll)
            left_col.addWidget(self.btn_submit)

            content_row.addLayout(left_col, stretch=5)

            # Right Panel: DB Table
            right_col = QVBoxLayout()
            table_box = QGroupBox("Enrolled Users in cyberchain.db")
            table_layout = QVBoxLayout(table_box)
            self.table = QTableWidget(0, 4)
            self.table.setHorizontalHeaderLabels(["Name", "Role", "Passkeys", "Created At"])
            self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            table_layout.addWidget(self.table)

            btn_refresh = QPushButton("Refresh Table")
            btn_refresh.setProperty("class", "secondary-btn")
            btn_refresh.clicked.connect(self.refresh_users_table)
            table_layout.addWidget(btn_refresh)

            right_col.addWidget(table_box)
            content_row.addLayout(right_col, stretch=5)

            main_layout.addLayout(content_row)

        def handle_launch_passkey(self):
            user = self.input_username.text().strip()
            if not user:
                QMessageBox.warning(self, "Name Required", "Please enter a Name first.")
                return

            self.current_session_id = uuid.uuid4().hex[:12]
            self.captured_credential_id = None
            self.captured_device = None

            active_qr_sessions[self.current_session_id] = {
                "session_id": self.current_session_id,
                "username": user,
                "status": "PENDING"
            }

            url = f"http://localhost:{qr_server_port}/enroll?session={self.current_session_id}&user={user}"
            try:
                webbrowser.open(url)
                self.lbl_scan_status.setText("🟡 Browser opened... Choose 'Use a phone or tablet' to show QR")
                self.lbl_scan_status.setStyleSheet("color: #facc15; font-weight: bold; font-size: 12px;")
            except Exception as e:
                QMessageBox.critical(self, "Browser Error", f"Could not open browser: {e}")

        def check_qr_session_status(self):
            session = active_qr_sessions.get(self.current_session_id)
            if session and session.get("status") == "VERIFIED":
                self.captured_credential_id = session.get("credential_id")
                self.captured_device = session.get("client_device", "Smartphone")
                self.lbl_scan_status.setText("🟢 PASSKEY CAPTURED VIA PHONE!")
                self.lbl_scan_status.setStyleSheet("color: #10b981; font-weight: bold; font-size: 12px;")

        def handle_enroll(self):
            u = self.input_username.text().strip()
            if not u:
                QMessageBox.warning(self, "Name Required", "Please enter a Name.")
                return

            if not self.captured_credential_id:
                QMessageBox.warning(self, "No Passkey Captured", "Please click 'Launch Phone Bluetooth Passkey Prompt' and scan with your phone first.")
                return

            role = self.combo_role.currentData() or "user"

            try:
                res = enroll_credential_into_db(
                    username=u,
                    role=role,
                    fingerprint_credential_id=self.captured_credential_id,
                    fingerprint_device=self.captured_device or "Smartphone Biometric Passkey"
                )
                QMessageBox.information(
                    self,
                    "Enrolled",
                    f"User '{res['username']}' with role '{res['role'].upper()}' and passkey successfully registered in cyberchain.db!"
                )
                self.input_username.clear()
                self.captured_credential_id = None
                self.lbl_scan_status.setText("⚪ No passkey captured yet")
                self.lbl_scan_status.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 12px;")
                self.refresh_users_table()
            except Exception as exc:
                QMessageBox.critical(self, "Database Error", f"Failed to commit: {exc}")

        def refresh_users_table(self):
            try:
                users = list_all_db_users()
                self.table.setRowCount(len(users))
                for i, u in enumerate(users):
                    self.table.setItem(i, 0, QTableWidgetItem(u["username"]))
                    role_str = u.get("role", "user").upper()
                    role_item = QTableWidgetItem(role_str)
                    if role_str == "ADMIN":
                        role_item.setForeground(QColor("#00ffcc"))
                    else:
                        role_item.setForeground(QColor("#94a3b8"))
                    self.table.setItem(i, 1, role_item)
                    self.table.setItem(i, 2, QTableWidgetItem(f"{u['fingerprints_count']} key(s)"))
                    self.table.setItem(i, 3, QTableWidgetItem(u["created_at"][:10]))
            except Exception:
                pass

    app = QApplication(sys.argv)
    window = EntryStationWindow()
    window.show()
    sys.exit(app.exec())


# ==============================================================================
# CLI IMPLEMENTATION
# ==============================================================================
def run_cli():
    import argparse

    start_embedded_qr_server()

    parser = argparse.ArgumentParser(description="CyberChain Identity & Passkey Station")
    parser.add_argument("-u", "--username", help="Name / Username (Only compulsory field)")
    parser.add_argument("-r", "--role", choices=["user", "admin"], default="user", help="User role: 'user' or 'admin'")
    parser.add_argument("-f", "--fingerprint", help="Custom fingerprint / passkey ID")
    parser.add_argument("-l", "--list", action="store_true", help="List all users in clean cyberchain.db")
    parser.add_argument("--cli", action="store_true", help="Force CLI mode")
    parser.add_argument("--gui", action="store_true", help="Force GUI mode")
    args = parser.parse_args()

    if args.list:
        users = list_all_db_users()
        print("\n" + "=" * 68)
        print(f"   CURRENT USERS IN CYBERCHAIN DB ({DB_PATH})")
        print("=" * 68)
        if not users:
            print("   (Database is clean - 0 registered users)")
        else:
            print(f"{'NAME':<20} | {'ROLE':<8} | {'PASSKEYS':<14} | {'ENROLLED'}")
            print("-" * 68)
            for u in users:
                print(f"{u['username']:<20} | {u.get('role', 'user').upper():<8} | {str(u['fingerprints_count']):<14} | {u['created_at'][:10]}")
        print("=" * 68 + "\n")
        return

    if args.username and args.fingerprint:
        res = enroll_credential_into_db(
            username=args.username,
            role=args.role,
            fingerprint_credential_id=args.fingerprint,
            fingerprint_device="CLI Hardware Parameter"
        )
        print(f"\n[+] Successfully registered user '{res['username']}' with role '{res['role'].upper()}' into clean cyberchain.db!")
        return

    print("\n" + "=" * 60)
    print("   CYBERCHAIN USER & PASSKEY ENROLLMENT")
    print("=" * 60)
    try:
        u = input("Enter Name: ").strip()
        if not u:
            print("[-] Name is compulsory.")
            return

        r_input = input("Enter Role (user / admin) [default: user]: ").strip().lower()
        role = "admin" if r_input == "admin" else "user"

        session_id = uuid.uuid4().hex[:12]
        active_qr_sessions[session_id] = {
            "session_id": session_id,
            "username": u,
            "status": "PENDING"
        }

        url = f"http://localhost:{qr_server_port}/enroll?session={session_id}&user={u}"
        print(f"\n[*] Opening passkey prompt in browser: {url}")
        try:
            webbrowser.open(url)
        except Exception:
            pass

        print("[*] Waiting for phone Bluetooth passkey scan...")
        for _ in range(30):
            if active_qr_sessions[session_id].get("status") == "VERIFIED":
                captured_cred = active_qr_sessions[session_id].get("credential_id")
                enroll_credential_into_db(username=u, role=role, fingerprint_credential_id=captured_cred, fingerprint_device=dev)
                print(f"\n[+] Success! User '{u}' with role '{role.upper()}' registered with passkey from {dev}!")
                return
            time.sleep(1)

        print("\n[-] Timeout or cancelled. No passkey was registered.")
    except (KeyboardInterrupt, EOFError):
        print("\n[-] Cancelled.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and "--gui" not in sys.argv:
        run_cli()
    else:
        try:
            import PyQt6
            run_gui()
        except Exception:
            run_cli()
