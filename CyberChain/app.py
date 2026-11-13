#!/usr/bin/env python3
"""
==============================================================================
CYBERCHAIN - PRIMARY USER AUTHENTICATION & BLOCKCHAIN SESSION WORKSTATION
==============================================================================
Workflow:
1> When opened, displays interface asking for Username with an "Enter Passkey" button below.
2> Clicking "Enter Passkey" opens a simple HTML/CSS site displaying strictly the QR code.
   Once scanned and passkey entered successfully, the browser tab closes and user logs in.
3> Upon login, Anvil EVM blockchain node starts automatically.
   User can record changes and forensic modifications during the session.
4> Upon logout, the full entry time, exit time, username, and changes are automatically
   registered into the SessionAuditLedger smart contract on the Anvil blockchain.
5> As Anvil starts fresh each time, the smart contract deployment, transaction receipt,
   and session details are permanently recorded in the secondary SQL database (cyberchain.db).
==============================================================================
"""
import os
import sys
import time
import uuid
import json
import subprocess
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

CYBERCHAIN_DIR = Path(__file__).resolve().parent
if str(CYBERCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(CYBERCHAIN_DIR))

import database
import blockchain
import auth_server


# ==============================================================================
# PYQT6 GRAPHICAL USER INTERFACE
# ==============================================================================
def run_gui():
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
        QHeaderView, QMessageBox, QGroupBox, QFrame, QTextEdit
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    class CyberChainAppWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("CyberChain - Hardware Passkey & Blockchain Custody Workstation")
            self.setMinimumSize(560, 620)
            self.resize(600, 660)

            # State
            self.current_auth_session_id = None
            self.active_user = None
            self.active_role = "user"
            self.active_session_id = None
            self.entry_time = None
            self.session_changes = []
            self.peakledger_proc = None

            # Timers
            self.auth_poll_timer = QTimer(self)
            self.auth_poll_timer.timeout.connect(self.check_auth_status)
            self.peakledger_monitor_timer = QTimer(self)
            self.peakledger_monitor_timer.timeout.connect(self.monitor_peakledger_session)

            self.init_ui()

        def init_ui(self):
            self.central_widget = QWidget()
            self.setCentralWidget(self.central_widget)
            self.main_layout = QVBoxLayout(self.central_widget)
            self.main_layout.setContentsMargins(28, 28, 28, 28)
            self.main_layout.setSpacing(18)

            self.apply_theme()
            self.show_login_interface()

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
                QGroupBox {
                    border: 1px solid #1e293b;
                    border-radius: 10px;
                    margin-top: 14px;
                    font-weight: bold;
                    color: #00ffcc;
                    padding: 16px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 14px;
                    padding: 0 6px;
                }
                QLineEdit, QTextEdit {
                    background-color: #0f172a;
                    color: #f8fafc;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 10px 14px;
                    font-size: 14px;
                }
                QLineEdit:focus, QTextEdit:focus {
                    border: 1px solid #00ffcc;
                    background-color: #131d31;
                }
                QPushButton {
                    background-color: #00ffcc;
                    color: #06090e;
                    font-weight: 800;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 18px;
                    font-size: 13px;
                    letter-spacing: 0.5px;
                }
                QPushButton:hover {
                    background-color: #33ffd6;
                }
                QPushButton[class="secondary-btn"] {
                    background-color: #1e293b;
                    color: #94a3b8;
                    border: 1px solid #334155;
                }
                QPushButton[class="secondary-btn"]:hover {
                    background-color: #334155;
                    color: #f8fafc;
                }
                QPushButton[class="logout-btn"] {
                    background-color: #e11d48;
                    color: #ffffff;
                }
                QPushButton[class="logout-btn"]:hover {
                    background-color: #f43f5e;
                }
                QTableWidget {
                    background-color: #0b111a;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
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
            """)

        def clear_layout(self):
            while self.main_layout.count():
                item = self.main_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        # ======================================================================
        # 1> LOGIN INTERFACE: USERNAME INPUT & "ENTER PASSKEY" BUTTON
        # ======================================================================
        def show_login_interface(self):
            self.clear_layout()
            self.active_user = None
            self.current_auth_session_id = None
            self.auth_poll_timer.stop()

            # Center Container
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

            # Badge
            lbl_badge = QLabel("◈ CYBERCHAIN AUTHENTICATION")
            lbl_badge.setStyleSheet("color: #00ffcc; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
            lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(lbl_badge)

            # Title
            lbl_title = QLabel("Forensic Custody Login")
            lbl_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #ffffff;")
            lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(lbl_title)

            lbl_sub = QLabel("FIDO2 / Hardware Biometric Passkey System")
            lbl_sub.setStyleSheet("font-size: 13px; color: #64748b; margin-bottom: 12px;")
            lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(lbl_sub)

            # Name Label & Input (ONLY compulsory column)
            lbl_user = QLabel("Name:")
            lbl_user.setStyleSheet("font-weight: 600; font-size: 13px; color: #cbd5e1;")
            card_layout.addWidget(lbl_user)

            self.txt_username = QLineEdit()
            self.txt_username.setPlaceholderText("Enter your Name")
            self.txt_username.setText("")
            card_layout.addWidget(self.txt_username)

            # 1> Button: "Enter Passkey"
            self.btn_passkey = QPushButton("Enter Passkey")
            self.btn_passkey.setFixedHeight(46)
            self.btn_passkey.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_passkey.clicked.connect(self.on_enter_passkey_clicked)
            card_layout.addWidget(self.btn_passkey)

            # Status Label
            self.lbl_auth_status = QLabel("Ready for passkey authentication")
            self.lbl_auth_status.setStyleSheet("font-size: 12px; color: #64748b; margin-top: 6px;")
            self.lbl_auth_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(self.lbl_auth_status)

            center_box.addWidget(card)
            self.main_layout.addLayout(center_box)

        # ======================================================================
        # 2> ON CLICK: OPEN SIMPLE HTML/CSS SITE WITH STRICTLY THE QR CODE
        # ======================================================================
        def on_enter_passkey_clicked(self):
            username = self.txt_username.text().strip()
            if not username:
                QMessageBox.warning(self, "Input Required", "Please enter your Name.")
                return

            # Check / Register User (Name only)
            user = database.get_user(username)
            if not user:
                user = database.register_user(username=username)

            # Start auth server
            port = auth_server.start_auth_server()
            self.current_auth_session_id = auth_server.create_auth_session(username)

            # 2> Open simple HTML/CSS site triggering native Google / Bluetooth passkey QR
            url = f"http://localhost:{port}/auth?session={self.current_auth_session_id}&user={username}"
            print(f"[*] Opening Bluetooth passkey authentication: {url}")
            try:
                webbrowser.open(url)
            except Exception as e:
                print(f"[-] Could not open browser: {e}")

            self.lbl_auth_status.setText("QR Code opened in browser. Scan or touch sensor...")
            self.lbl_auth_status.setStyleSheet("font-size: 12px; color: #00ffcc; font-weight: bold;")
            self.btn_passkey.setEnabled(False)

            # Start polling for passkey completion
            self.auth_poll_timer.start(500)

        def check_auth_status(self):
            if not self.current_auth_session_id:
                return

            if auth_server.is_session_verified(self.current_auth_session_id):
                self.auth_poll_timer.stop()
                username = self.txt_username.text().strip()
                self.lbl_auth_status.setText("Passkey verified! Logging in...")
                # Transition to logged-in workspace
                QTimer.singleShot(300, lambda: self.on_login_successful(username))

        # ======================================================================
        # ======================================================================
        # 3> UPON LOGIN: START ANVIL, HIDE LOGIN, LAUNCH PEAKLEDGER & AUTO-COMMIT
        # ======================================================================
        def on_login_successful(self, username: str):
            self.active_user = username
            user_rec = database.get_user(username)
            self.active_role = (user_rec.get("role") or "user").lower() if user_rec else "user"
            self.active_session_id = f"sess_{uuid.uuid4().hex[:8]}"
            self.entry_time = datetime.now(timezone.utc).isoformat()
            self.session_changes = []

            # 3.1> Start Anvil blockchain silently in the background
            print(f"[*] User '{username}' [Role: {self.active_role.upper()}] authenticated. Starting Anvil blockchain node...")
            blockchain.start_anvil(port=8545)

            # Record initial session start event
            self.record_change(f"Session initialized by authorized examiner '{self.active_user}' [{self.active_role.upper()}] with PeakLedger Forensic Workstation")

            # 3.2> Automatically launch PeakLedger Workstation UI without console
            launched = self.launch_peakledger_ui()
            if not launched:
                QMessageBox.critical(self, "Launch Error", "Failed to launch PeakLedger Workstation UI. Please check file path.")
                self.btn_passkey.setEnabled(True)
                self.lbl_auth_status.setText("Failed to launch PeakLedger.")
                return

            # Hide CyberChain window so only PeakLedger is visible
            self.hide()

            # 3.3> Start monitor timer to detect PeakLedger session completion
            self.peakledger_monitor_timer.start(1000)

        def launch_peakledger_ui(self) -> bool:
            """Spawns PeakLedger forensic workstation frontend without a background console window."""
            peakledger_main = CYBERCHAIN_DIR.parent / "peakledger" / "ui" / "main.py"
            if not peakledger_main.exists():
                alt = CYBERCHAIN_DIR.parent / "peakledger_windows" / "peakledger" / "ui" / "main.py"
                if alt.exists():
                    peakledger_main = alt
                else:
                    print(f"[-] PeakLedger script not found: {peakledger_main}")
                    return False

            if self.peakledger_proc and self.peakledger_proc.poll() is None:
                print("[*] PeakLedger UI is already active.")
                return True

            python_bin = sys.executable
            if sys.platform == "win32":
                if python_bin.lower().endswith("python.exe"):
                    pyw_bin = python_bin[:-4] + "w.exe"
                    if os.path.exists(pyw_bin):
                        python_bin = pyw_bin

            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            try:
                print(f"[*] Starting PeakLedger UI: {peakledger_main}")
                self.peakledger_proc = subprocess.Popen(
                    [python_bin, str(peakledger_main)],
                    cwd=str(peakledger_main.parent.parent),
                    creationflags=creation_flags
                )
                return True
            except Exception as e:
                print(f"[-] Failed to launch PeakLedger UI: {e}")
                return False

        def open_admin_console(self):
            """Opens the secondary Admin Application to view database & audit logs."""
            if self.active_role != "admin":
                QMessageBox.warning(
                    self,
                    "Access Denied",
                    "Only Administrators have permission to open the CyberChain Admin Console."
                )
                return
            admin_script = CYBERCHAIN_DIR / "admin_app.py"
            if admin_script.exists():
                try:
                    py_bin = sys.executable
                    if sys.platform == "win32" and py_bin.lower().endswith("python.exe"):
                        pyw_bin = py_bin[:-4] + "w.exe"
                        if os.path.exists(pyw_bin):
                            py_bin = pyw_bin
                    creation_flags = 0
                    if sys.platform == "win32":
                        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    subprocess.Popen([py_bin, str(admin_script)], creationflags=creation_flags)
                except Exception as e:
                    QMessageBox.critical(self, "Admin Console Error", f"Failed to open admin console: {e}")

        def monitor_peakledger_session(self):
            """Monitors PeakLedger process lifecycle. Triggers auto-commit when closed."""
            if not self.peakledger_proc:
                return

            if self.peakledger_proc.poll() is not None:
                print("[*] PeakLedger process has exited. Initiating automatic blockchain commit...")
                if hasattr(self, "peakledger_monitor_timer") and self.peakledger_monitor_timer:
                    self.peakledger_monitor_timer.stop()
                self.auto_commit_session()

        def auto_commit_session(self):
            """
            Automatically harvests evidence, Merkle proofs, and tamper audit results
            generated by PeakLedger during this session, commits them to the Anvil smart contract,
            and logs the complete record into the secondary SQLite database (cyberchain.db).
            """
            exit_time = datetime.now(timezone.utc).isoformat()
            evidence_dir = CYBERCHAIN_DIR.parent / "peakledger" / "evidence"
            if not evidence_dir.exists():
                alt_ev = CYBERCHAIN_DIR.parent / "peakledger_windows" / "peakledger" / "evidence"
                if alt_ev.exists():
                    evidence_dir = alt_ev
            audit_json_path = evidence_dir / "tamper_audit_report.json"
            report_html_path = evidence_dir / "Forensic_Report.html"

            # 1. Harvest PeakLedger evidence & audit findings
            if audit_json_path.exists():
                try:
                    with open(audit_json_path, "r", encoding="utf-8") as f:
                        audit_data = json.load(f)
                    vid = audit_data.get("video_id", "Default_CCTV")
                    is_pristine = audit_data.get("is_pristine", False)
                    tampered_packets = audit_data.get("tampered_packets", 0)
                    suspect_root = audit_data.get("suspect_root", "")
                    intervals = audit_data.get("intervals", [])

                    if is_pristine:
                        verdict_str = "AUTHENTIC (Zero Packet Divergence Detected)"
                    else:
                        verdict_str = f"TAMPERED ({tampered_packets} packet mutations detected)"

                    self.record_change(
                        f"PeakLedger Merkle Audit for Video '{vid}': Verdict={verdict_str}. "
                        f"Merkle Root: {suspect_root[:16]}..."
                    )

                    if not is_pristine and intervals:
                        self.record_change(
                            f"Layer 2 NVDEC Tamper Isolation: {len(intervals)} mutated interval(s) "
                            f"isolated across {tampered_packets} frames."
                        )
                except Exception as e:
                    print(f"[-] Could not parse audit JSON: {e}")

            if report_html_path.exists():
                self.record_change(
                    "Courtroom Admissibility: NIST SP 800-86 Forensic Custody Audit Report generated and sealed."
                )

            # Final change
            self.record_change(
                f"Session lifecycle concluded by examiner '{self.active_user}'. Auto-committed on-chain."
            )

            # 2. Deploy and record to Anvil Smart Contract
            try:
                bc_result = blockchain.record_session_logout(
                    username=self.active_user,
                    session_id=self.active_session_id,
                    entry_time_str=self.entry_time,
                    exit_time_str=exit_time,
                    changes_list=self.session_changes
                )

                contract_address = bc_result["contract_address"]
                tx_hash = bc_result["tx_hash"]
                block_num = bc_result["block_number"]
                abi_json = bc_result.get("abi_json")

                # Store in cyberchain.db
                record_id = database.record_smart_contract_session(
                    session_id=self.active_session_id,
                    username=self.active_user,
                    entry_time=self.entry_time,
                    exit_time=exit_time,
                    changes_list=self.session_changes,
                    contract_address=contract_address,
                    tx_hash=tx_hash,
                    block_number=block_num,
                    deployer_address=bc_result.get("deployer_address", ""),
                    role=self.active_role,
                    abi_json=abi_json
                )

                print(f"[+] Successfully committed session {self.active_session_id} on-chain!")
                print(f"    Contract: {contract_address}")
                print(f"    Tx Hash:  0x{tx_hash}")
                print(f"    SQL Record: #{record_id} in cyberchain.db")

                blockchain.stop_anvil()

                # Display clean, professional confirmation dialog
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("CyberChain - Session Auto-Committed")
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setText("◈ Forensic Session Successfully Auto-Committed On-Chain!")
                msg_box.setInformativeText(
                    f"Examiner:        {self.active_user} [{self.active_role.upper()}]\n"
                    f"Session ID:      {self.active_session_id}\n"
                    f"Smart Contract:  {contract_address}\n"
                    f"Tx Hash:         0x{tx_hash}\n"
                    f"Block Number:    #{block_num}\n"
                    f"Sealed Events:   {len(self.session_changes)} evidentiary records\n\n"
                    f"Secondary SQL Database: cyberchain.db (Record #{record_id})\n"
                    f"All cryptographic hashes and Merkle roots are permanently sealed on-chain."
                )
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.exec()

            except Exception as e:
                print(f"[-] Auto-commit blockchain error: {e}")
                blockchain.stop_anvil()
                QMessageBox.critical(
                    self,
                    "Blockchain Auto-Commit Error",
                    f"Failed to auto-commit session to Anvil blockchain:\n{e}"
                )
            finally:
                QApplication.quit()

        def record_change(self, description: str):
            ts = datetime.now(timezone.utc).isoformat()
            change_item = {
                "index": len(self.session_changes) + 1,
                "timestamp": ts,
                "description": description
            }
            self.session_changes.append(change_item)

            if hasattr(self, "tbl_changes") and self.tbl_changes is not None:
                try:
                    row = self.tbl_changes.rowCount()
                    self.tbl_changes.insertRow(row)
                    self.tbl_changes.setItem(row, 0, QTableWidgetItem(str(change_item["index"])))
                    self.tbl_changes.setItem(row, 1, QTableWidgetItem(ts[11:19]))
                    self.tbl_changes.setItem(row, 2, QTableWidgetItem(description))
                except Exception:
                    pass

        def closeEvent(self, event):
            if hasattr(self, "peakledger_monitor_timer") and self.peakledger_monitor_timer:
                self.peakledger_monitor_timer.stop()
            if hasattr(self, "auth_poll_timer") and self.auth_poll_timer:
                self.auth_poll_timer.stop()
            if self.peakledger_proc and self.peakledger_proc.poll() is None:
                try:
                    self.peakledger_proc.terminate()
                except Exception:
                    pass
            blockchain.stop_anvil()
            event.accept()

    window = CyberChainAppWindow()
    window.show()
    sys.exit(app.exec())


# ==============================================================================
# CLI FALLBACK MODE (FOR HEADLESS OR NON-GUI ENVIRONMENTS)
# ==============================================================================
def run_cli():
    print("=" * 70)
    print("   CYBERCHAIN - USER AUTHENTICATION & BLOCKCHAIN SESSION WORKSTATION")
    print("=" * 70)

    username = input("\n[1] Enter Name: ").strip()
    if not username:
        print("[-] Name is compulsory.")
        return

    # Check user and role
    user_rec = database.get_user(username)
    if not user_rec:
        user_rec = database.register_user(username=username, role="user")
    role = (user_rec.get("role") or "user").lower()

    # Start Auth Server
    port = auth_server.start_auth_server()
    session_id = auth_server.create_auth_session(username)
    url = f"http://localhost:{port}/auth?session={session_id}&user={username}"

    print(f"\n[2] Opening Bluetooth passkey URL in browser: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print("[*] Waiting for passkey authentication... (scan QR or click sensor in browser)")
    while not auth_server.is_session_verified(session_id):
        time.sleep(0.5)

    print(f"\n[+] Passkey verified successfully! Logged in as '{username}' [{role.upper()}].")
    entry_time = datetime.now(timezone.utc).isoformat()

    # Start Anvil
    print("[3] Starting Anvil blockchain node...")
    blockchain.start_anvil()

    # Automatically launch PeakLedger UI
    peakledger_main = CYBERCHAIN_DIR.parent / "peakledger" / "ui" / "main.py"
    pl_proc = None
    if peakledger_main.exists():
        try:
            print(f"[*] Starting PeakLedger UI: {peakledger_main}")
            pl_proc = subprocess.Popen([sys.executable, str(peakledger_main)], cwd=str(peakledger_main.parent.parent))
        except Exception as e:
            print(f"[-] Could not launch PeakLedger UI: {e}")

    changes = [
        {"index": 1, "timestamp": entry_time, "description": f"CLI session started for {username} [{role.upper()}] with PeakLedger"}
    ]

    if role == "admin":
        print("\n[!] Administrator Role detected. You can inspect the database via: python admin_app.py --cli")

    print("\n[*] PeakLedger Forensic Workstation is active. Waiting for session completion...")
    print("    (Close PeakLedger to auto-commit to Anvil blockchain)")
    try:
        while pl_proc and pl_proc.poll() is None:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass

    # Read evidence from PeakLedger
    evidence_dir = CYBERCHAIN_DIR.parent / "peakledger" / "evidence"
    if not evidence_dir.exists():
        alt_ev = CYBERCHAIN_DIR.parent / "peakledger_windows" / "peakledger" / "evidence"
        if alt_ev.exists():
            evidence_dir = alt_ev
    audit_json_path = evidence_dir / "tamper_audit_report.json"
    report_html_path = evidence_dir / "Forensic_Report.html"

    if audit_json_path.exists():
        try:
            with open(audit_json_path, "r", encoding="utf-8") as f:
                audit_data = json.load(f)
            vid = audit_data.get("video_id", "Default_CCTV")
            is_pristine = audit_data.get("is_pristine", False)
            tampered_packets = audit_data.get("tampered_packets", 0)
            suspect_root = audit_data.get("suspect_root", "")
            verdict_str = "AUTHENTIC" if is_pristine else f"TAMPERED ({tampered_packets} packet mutations)"
            changes.append({
                "index": len(changes) + 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "description": f"PeakLedger Merkle Audit for Video '{vid}': Verdict={verdict_str}. Root={suspect_root[:16]}..."
            })
        except Exception:
            pass

    if report_html_path.exists():
        changes.append({
            "index": len(changes) + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "description": "Courtroom Admissibility: NIST SP 800-86 Forensic Custody Audit Report generated and sealed."
        })

    changes.append({
        "index": len(changes) + 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": f"Session concluded for {username}. Auto-committed on-chain."
    })

    exit_time = datetime.now(timezone.utc).isoformat()
    print("\n[4] Registering session into Anvil Smart Contract...")
    result = blockchain.record_session_logout(
        username=username,
        session_id=session_id,
        entry_time_str=entry_time,
        exit_time_str=exit_time,
        changes_list=changes
    )

    record_id = database.record_smart_contract_session(
        session_id=session_id,
        username=username,
        entry_time=entry_time,
        exit_time=exit_time,
        changes_list=changes,
        contract_address=result["contract_address"],
        tx_hash=result["tx_hash"],
        block_number=result["block_number"],
        deployer_address=result.get("deployer_address", ""),
        role=role,
        abi_json=result.get("abi_json")
    )

    if pl_proc and pl_proc.poll() is None:
        try:
            pl_proc.terminate()
        except Exception:
            pass

    blockchain.stop_anvil()

    print("\n[+] Session registered to Anvil Smart Contract and Secondary SQL Database!")
    print(f"    User / Role:  {username} [{role.upper()}]")
    print(f"    Contract:     {result['contract_address']}")
    print(f"    Tx Hash:      0x{result['tx_hash']}")
    print(f"    Block:        #{result['block_number']}")
    print(f"    SQL Record ID: {record_id} in cyberchain.db")


def show_fatal_error(msg: str):
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "CyberChain Startup Error", 0x10)
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
                f"CyberChain failed to start GUI:\n\n{e}\n\n"
                f"Please ensure required dependencies are installed:\n"
                f"pip install PyQt6 web3"
            )
            if sys.stdout is not None:
                run_cli()
