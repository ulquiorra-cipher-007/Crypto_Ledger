#!/usr/bin/env python3
"""
==============================================================================
CYBERCHAIN - SECONDARY ADMIN APPLICATION
==============================================================================
Sole Functionality:
- Opened by Admin to inspect the Secondary SQL Database (cyberchain.db).
- Displays all smart contract sessions recorded upon logout:
  * Username & User ID
  * Entry Time & Exit Time
  * Full JSON list of session changes and modifications
  * Smart Contract Address on Anvil
  * Blockchain Transaction Hash & Block Number
  * Verification of Changes SHA-256 Hash
- Displays all registered users and their enrolled hardware/biometric passkeys.
==============================================================================
"""
import os
import sys
import json
import hashlib
import webbrowser
from datetime import datetime
from pathlib import Path

CYBERCHAIN_DIR = Path(__file__).resolve().parent
if str(CYBERCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(CYBERCHAIN_DIR))

import database
import auth_server

# ==============================================================================
# PYQT6 ADMIN GUI
# ==============================================================================
def run_gui():
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
        QTabWidget, QTextEdit, QSplitter, QGroupBox, QFrame, QMessageBox,
        QLineEdit
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QColor

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    class AdminAppWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("CyberChain Admin Console - Hardware Passkey Authentication")
            self.setMinimumSize(560, 620)
            self.resize(600, 660)

            self.current_auth_session_id = None
            self.auth_poll_timer = QTimer(self)
            self.auth_poll_timer.timeout.connect(self.check_auth_status)
            
            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)
            self.main_layout = QVBoxLayout(self.central_widget)
            self.main_layout.setContentsMargins(28, 28, 28, 28)
            self.main_layout.setSpacing(18)
            self.apply_theme()
            
            self.show_login_interface()

        def clear_layout(self):
            while self.main_layout.count():
                item = self.main_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        def show_login_interface(self):
            self.clear_layout()
            self.setWindowTitle("CyberChain Admin Console - Hardware Passkey Authentication")
            self.setMinimumSize(560, 620)
            self.resize(600, 660)
            self.current_auth_session_id = None
            self.auth_poll_timer.stop()

            center_box = QVBoxLayout()
            center_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

            card = QFrame()
            card.setObjectName("loginCard")
            card.setFixedWidth(460)
            card.setStyleSheet("""
                #loginCard {
                    background-color: #0d131d;
                    border: 1px solid #1f293d;
                    border-radius: 16px;
                }
                #loginCard QLabel {
                    background: transparent;
                    border: none;
                    padding: 0px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(32, 32, 32, 32)
            card_layout.setSpacing(16)

            lbl_badge = QLabel("◈ CYBERCHAIN ADMINISTRATOR AUTHENTICATION")
            lbl_badge.setStyleSheet("color: #00ffcc; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
            lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(lbl_badge)

            lbl_title = QLabel("Admin Console Login")
            lbl_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #ffffff;")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(lbl_title)

            lbl_sub = QLabel("FIDO2 / Hardware Biometric Passkey System")
            lbl_sub.setStyleSheet("font-size: 13px; color: #64748b; margin-bottom: 12px;")
            lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(lbl_sub)

            lbl_user = QLabel("Name:")
            lbl_user.setStyleSheet("font-weight: 600; font-size: 13px; color: #cbd5e1;")
            card_layout.addWidget(lbl_user)

            self.txt_username = QLineEdit()
            self.txt_username.setPlaceholderText("Enter Admin Name")
            self.txt_username.returnPressed.connect(self.on_enter_passkey_clicked)
            card_layout.addWidget(self.txt_username)

            self.btn_passkey = QPushButton("Enter Passkey")
            self.btn_passkey.setFixedHeight(46)
            self.btn_passkey.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_passkey.clicked.connect(self.on_enter_passkey_clicked)
            card_layout.addWidget(self.btn_passkey)

            self.lbl_auth_status = QLabel("Ready for admin passkey authentication")
            self.lbl_auth_status.setStyleSheet("font-size: 12px; color: #64748b; margin-top: 6px;")
            self.lbl_auth_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(self.lbl_auth_status)

            center_box.addWidget(card)
            self.main_layout.addLayout(center_box)

        def on_enter_passkey_clicked(self):
            username = self.txt_username.text().strip()
            if not username:
                QMessageBox.warning(self, "Input Required", "Please enter your Name.")
                return

            # Strictly verify admin privileges before initiating passkey
            user = database.get_user(username)
            role = (user.get("role") or "user").lower() if user else None

            if not user or role != "admin":
                self.lbl_auth_status.setText("Not permitted. Administrator privileges required.")
                self.lbl_auth_status.setStyleSheet("font-size: 12px; color: #ef4444; font-weight: bold; margin-top: 6px;")
                QMessageBox.critical(
                    self,
                    "Access Denied",
                    f"Not permitted.\n\nUser '{username}' does not have Administrator privileges."
                )
                self.btn_passkey.setEnabled(True)
                return

            port = auth_server.start_auth_server()
            self.current_auth_session_id = auth_server.create_auth_session(username)

            url = f"http://localhost:{port}/auth?session={self.current_auth_session_id}&user={username}"
            try:
                webbrowser.open(url)
            except Exception as e:
                pass

            self.lbl_auth_status.setText("QR Code opened in browser. Scan or touch sensor...")
            self.lbl_auth_status.setStyleSheet("font-size: 12px; color: #00ffcc; font-weight: bold; margin-top: 6px;")
            self.btn_passkey.setEnabled(False)
            self.auth_poll_timer.start(500)

        def check_auth_status(self):
            if not self.current_auth_session_id:
                return

            if auth_server.is_session_verified(self.current_auth_session_id):
                self.auth_poll_timer.stop()
                username = self.txt_username.text().strip()
                
                user_rec = database.get_user(username)
                role = (user_rec.get("role") or "user").lower() if user_rec else "user"
                
                if role != "admin":
                    self.lbl_auth_status.setText("Not permitted. Administrator privileges required.")
                    self.lbl_auth_status.setStyleSheet("font-size: 12px; color: #ef4444; font-weight: bold; margin-top: 6px;")
                    QMessageBox.critical(
                        self,
                        "Access Denied",
                        f"Not permitted.\n\nUser '{username}' does not have Administrator privileges."
                    )
                    self.show_login_interface()
                    return
                
                self.lbl_auth_status.setText("Admin Passkey verified! Loading console...")
                self.lbl_auth_status.setStyleSheet("font-size: 12px; color: #00ffcc; font-weight: bold; margin-top: 6px;")
                QTimer.singleShot(300, self.show_admin_interface)

        def show_admin_interface(self):
            self.clear_layout()
            self.setWindowTitle("CyberChain Admin Workstation - Blockchain & SQL Audit Inspector")
            self.setMinimumSize(1080, 720)
            self.resize(1140, 760)

            # Center on screen
            try:
                screen_geometry = self.screen().availableGeometry()
                x = (screen_geometry.width() - 1140) // 2
                y = (screen_geometry.height() - 760) // 2
                self.move(max(0, x), max(0, y))
            except Exception:
                pass

            # Header
            header_box = QHBoxLayout()
            title_layout = QVBoxLayout()

            lbl_badge = QLabel("◈ CYBERCHAIN ADMINISTRATOR INTERFACE")
            lbl_badge.setStyleSheet("color: #00ffcc; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
            title_layout.addWidget(lbl_badge)

            lbl_title = QLabel("Blockchain & Smart Contract Audit Console")
            lbl_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #ffffff;")
            title_layout.addWidget(lbl_title)

            lbl_sub = QLabel(f"Authoritative Secondary Database: {database.DB_PATH}")
            lbl_sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
            title_layout.addWidget(lbl_sub)

            header_box.addLayout(title_layout)
            header_box.addStretch()

            btn_refresh = QPushButton("⟳ Refresh Ledger")
            btn_refresh.clicked.connect(self.on_refresh_clicked)
            header_box.addWidget(btn_refresh)

            btn_logout = QPushButton("⎋ Logout")
            btn_logout.setProperty("class", "logout-btn")
            btn_logout.clicked.connect(self.show_login_interface)
            header_box.addWidget(btn_logout)

            self.main_layout.addLayout(header_box)

            # Tabs
            tabs = QTabWidget()
            tabs.addTab(self.create_smart_contracts_tab(), "Smart Contract Session Records")
            tabs.addTab(self.create_users_tab(), "Registered Users && Passkeys")
            tabs.addTab(self.create_contract_abi_tab(), "Contract ABI && Specification")
            self.main_layout.addWidget(tabs)
            
            self.refresh_records()
            self.refresh_users()

        def apply_theme(self):
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #080d14;
                    color: #e2e8f0;
                    font-family: 'Segoe UI', system-ui, sans-serif;
                }
                QLabel {
                    background-color: transparent;
                    border: none;
                    padding: 0px;
                }
                QTabWidget::pane {
                    border: 1px solid #1e293b;
                    background-color: #0d131d;
                    border-radius: 8px;
                }
                QTabBar::tab {
                    background: #111827;
                    color: #94a3b8;
                    padding: 10px 20px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                    margin-right: 4px;
                    font-weight: bold;
                }
                QTabBar::tab:selected {
                    background: #1e293b;
                    color: #00ffcc;
                    border-bottom: 2px solid #00ffcc;
                }
                QTableWidget {
                    background-color: #090e17;
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                    gridline-color: #1e293b;
                    color: #e2e8f0;
                }
                QHeaderView::section {
                    background-color: #131b26;
                    color: #94a3b8;
                    padding: 8px;
                    border: none;
                    font-weight: bold;
                }
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    font-weight: 700;
                    border: none;
                    border-radius: 6px;
                    padding: 10px 16px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                QTextEdit {
                    background-color: #090e17;
                    color: #38bdf8;
                    font-family: 'Cascadia Code', 'Consolas', monospace;
                    font-size: 12px;
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                }
            """)

        # ----------------------------------------------------------------------
        # TAB 1: SMART CONTRACT RECORDS
        # ----------------------------------------------------------------------
        def create_smart_contracts_tab(self) -> QWidget:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(14, 14, 14, 14)

            splitter = QSplitter(Qt.Orientation.Vertical)

            # Table of Records
            # Table of Records
            self.tbl_records = QTableWidget(0, 9)
            self.tbl_records.setHorizontalHeaderLabels([
                "Record ID", "Session ID", "Username", "Role", "Entry Time", "Exit Time",
                "Changes", "Smart Contract Address", "Tx Hash"
            ])
            self.tbl_records.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            self.tbl_records.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            self.tbl_records.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
            self.tbl_records.itemSelectionChanged.connect(self.on_record_selected)
            splitter.addWidget(self.tbl_records)

            # Details & Integrity Box
            detail_box = QGroupBox("Selected Smart Contract Details && Forensic Hash Verification")
            detail_layout = QVBoxLayout(detail_box)

            self.lbl_verify_status = QLabel("Select a recorded session above to inspect details and verify cryptographic hash.")
            self.lbl_verify_status.setStyleSheet("font-size: 13px; color: #94a3b8; font-weight: bold;")
            detail_layout.addWidget(self.lbl_verify_status)

            self.txt_changes_json = QTextEdit()
            self.txt_changes_json.setReadOnly(True)
            self.txt_changes_json.setPlaceholderText("Full JSON modifications payload recorded to Anvil smart contract...")
            detail_layout.addWidget(self.txt_changes_json)

            splitter.addWidget(detail_box)
            splitter.setSizes([380, 260])

            layout.addWidget(splitter)
            return tab

        def refresh_records(self):
            records = database.get_all_smart_contract_records()
            self.tbl_records.setRowCount(0)
            self.cached_records = {str(r["id"]): r for r in records}

            for r in records:
                row = self.tbl_records.rowCount()
                self.tbl_records.insertRow(row)
                self.tbl_records.setItem(row, 0, QTableWidgetItem(str(r["id"])))
                self.tbl_records.setItem(row, 1, QTableWidgetItem(r["session_id"]))
                self.tbl_records.setItem(row, 2, QTableWidgetItem(r["username"]))

                role_str = r.get("role", "user").upper()
                role_item = QTableWidgetItem(role_str)
                if role_str == "ADMIN":
                    role_item.setForeground(QColor("#00ffcc"))
                else:
                    role_item.setForeground(QColor("#94a3b8"))
                self.tbl_records.setItem(row, 3, role_item)

                self.tbl_records.setItem(row, 4, QTableWidgetItem(r["entry_time"][:19].replace("T", " ")))
                self.tbl_records.setItem(row, 5, QTableWidgetItem(r["exit_time"][:19].replace("T", " ")))
                self.tbl_records.setItem(row, 6, QTableWidgetItem(str(r["changes_count"])))
                self.tbl_records.setItem(row, 7, QTableWidgetItem(r["contract_address"]))
                self.tbl_records.setItem(row, 8, QTableWidgetItem("0x" + r["tx_hash"][:16] + "..."))

        def on_record_selected(self):
            selected = self.tbl_records.selectedItems()
            if not selected:
                return

            row = selected[0].row()
            rec_id = self.tbl_records.item(row, 0).text()
            rec = self.cached_records.get(rec_id)
            if not rec:
                return

            changes_json_str = rec["changes_json"]
            self.txt_changes_json.setPlainText(changes_json_str)

            # Recalculate SHA-256 hash to verify data integrity
            computed_hash = hashlib.sha256(changes_json_str.encode()).hexdigest()
            stored_hash = rec["changes_hash"].replace("0x", "")

            if computed_hash == stored_hash:
                status_text = (
                    f"✓ FORENSIC HASH VERIFIED: SHA-256({computed_hash[:16]}...) MATCHES ON-CHAIN RECORD!\n"
                    f"Contract: {rec['contract_address']} | Block #{rec['block_number']} | Role: {rec.get('role', 'user').upper()} | Status: {rec['status']}"
                )
                self.lbl_verify_status.setStyleSheet("font-size: 13px; color: #10b981; font-weight: bold;")
            else:
                status_text = (
                    f"⚠ HASH MISMATCH! Database record may have been altered.\n"
                    f"Computed: {computed_hash} != Stored: {stored_hash}"
                )
                self.lbl_verify_status.setStyleSheet("font-size: 13px; color: #ef4444; font-weight: bold;")

            self.lbl_verify_status.setText(status_text)

        # ----------------------------------------------------------------------
        # TAB 2: REGISTERED USERS & PASSKEYS
        # ----------------------------------------------------------------------
        def create_users_tab(self) -> QWidget:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(14, 14, 14, 14)

            self.tbl_users = QTableWidget(0, 5)
            self.tbl_users.setHorizontalHeaderLabels([
                "User ID", "Name", "Role", "Active Passkeys", "Created At"
            ])
            self.tbl_users.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            self.tbl_users.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            layout.addWidget(self.tbl_users)

            return tab

        def refresh_users(self):
            users = database.get_all_users()
            self.tbl_users.setRowCount(0)
            for u in users:
                row = self.tbl_users.rowCount()
                self.tbl_users.insertRow(row)
                self.tbl_users.setItem(row, 0, QTableWidgetItem(u["id"][:8] + "..."))
                self.tbl_users.setItem(row, 1, QTableWidgetItem(u["username"]))

                role_str = u.get("role", "user").upper()
                role_item = QTableWidgetItem(role_str)
                if role_str == "ADMIN":
                    role_item.setForeground(QColor("#00ffcc"))
                else:
                    role_item.setForeground(QColor("#94a3b8"))
                self.tbl_users.setItem(row, 2, role_item)

                self.tbl_users.setItem(row, 3, QTableWidgetItem(f"{u['passkey_count']} credential(s)"))
                self.tbl_users.setItem(row, 4, QTableWidgetItem(u["created_at"][:10]))

        # ----------------------------------------------------------------------
        # TAB 3: CONTRACT ABI & SPECIFICATION
        # ----------------------------------------------------------------------
        def create_contract_abi_tab(self) -> QWidget:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(14, 14, 14, 14)

            sol_path = CYBERCHAIN_DIR / "contracts" / "SessionAuditLedger.sol"
            sol_content = sol_path.read_text(encoding="utf-8") if sol_path.exists() else "Contract file not found."

            txt_sol = QTextEdit()
            txt_sol.setReadOnly(True)
            txt_sol.setPlainText(sol_content)
            layout.addWidget(txt_sol)

            return tab

        def on_refresh_clicked(self):
            self.refresh_records()
            self.refresh_users()
            QMessageBox.information(self, "Refreshed", "Secondary SQL Database refreshed successfully.")

    window = AdminAppWindow()
    window.show()
    sys.exit(app.exec())


# ==============================================================================
# CLI FALLBACK MODE
# ==============================================================================
def run_cli():
    print("=" * 75)
    print("   CYBERCHAIN ADMIN - BLOCKCHAIN & SECONDARY SQL DB INSPECTOR")
    print("=" * 75)

    username = input("\n[1] Enter Admin Name: ").strip()
    if not username:
        print("[-] Name is compulsory.")
        return

    user_rec = database.get_user(username)
    role = (user_rec.get("role") or "user").lower() if user_rec else None

    if not user_rec or role != "admin":
        print(f"[-] Access Denied: Not permitted. User '{username}' does not have Administrator privileges.")
        return

    port = auth_server.start_auth_server()
    session_id = auth_server.create_auth_session(username)
    url = f"http://localhost:{port}/auth?session={session_id}&user={username}"

    print(f"\n[2] Opening Bluetooth passkey URL in browser: {url}")
    import time
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print("[*] Waiting for passkey authentication... (scan QR or click sensor in browser)")
    while not auth_server.is_session_verified(session_id):
        time.sleep(0.5)

    print(f"\n[+] Admin Passkey verified successfully! Loading console...\n")

    records = database.get_all_smart_contract_records()
    print(f"[+] Total Smart Contract Session Records in cyberchain.db: {len(records)}\n")
    print(f"{'ID':<4} {'USERNAME':<14} {'ROLE':<8} {'SESSION ID':<16} {'CHANGES':<8} {'CONTRACT ADDRESS'}")
    print("-" * 80)
    for r in records:
        print(f"{r['id']:<4} {r['username']:<14} {r.get('role', 'user').upper():<8} {r['session_id']:<16} {r['changes_count']:<8} {r['contract_address']}")

    users = database.get_all_users()
    print(f"\n[+] Registered Users ({len(users)}):")
    for u in users:
        print(f"  • {u['username']} [{u.get('role', 'user').upper()}] - Passkeys: {u['passkey_count']}")


def show_fatal_error(msg: str):
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "CyberChain Admin Error", 0x10)
            return
        except Exception:
            pass
    try:
        print(f"[ERROR] {msg}", file=sys.stderr)
    except Exception:
        pass


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    elif sys.platform != "win32" and not os.environ.get("DISPLAY"):
        run_cli()
    else:
        try:
            run_gui()
        except Exception as e:
            show_fatal_error(
                f"CyberChain Admin failed to start GUI:\n\n{e}\n\n"
                f"Please ensure required dependencies are installed:\n"
                f"pip install PyQt6 web3"
            )
            if sys.stdout is not None:
                run_cli()
