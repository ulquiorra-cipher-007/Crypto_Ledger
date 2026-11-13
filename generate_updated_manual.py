#!/usr/bin/env python3
"""
Loads the existing PeakLedger Architecture Manual and appends Section 9:
CyberChain Integration & Unified CryptoLedger Platform Architecture.
Saves the updated document to the current directory.
"""
import os, sys, docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

# ── Helper functions (same styling as original manual) ──────────────────

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def set_table_borders(table, color="CBD5E1", sz="4", val="single"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="none"/><w:right w:val="none"/>'
        f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def add_hyperlink(paragraph, url, text, color="1D4ED8", underline=True, bold=False):
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)
    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    if color:
        c = OxmlElement('w:color'); c.set(qn('w:val'), color); rPr.append(c)
    if underline:
        u = OxmlElement('w:u'); u.set(qn('w:val'), 'single'); rPr.append(u)
    if bold:
        b = OxmlElement('w:b'); rPr.append(b)
    new_run.append(rPr)
    t = OxmlElement('w:t'); t.text = text; new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)

def add_callout_box(doc, text_list, title="ARCHITECTURAL PRINCIPLE", fill_hex="F8FAFC", border_hex="1E3A8A"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, fill_hex)
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="36" w:space="0" w:color="{border_hex}"/>'
        f'<w:top w:val="none"/><w:bottom w:val="none"/><w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    run_t = p.add_run(f"\U0001f4cc {title}\n")
    run_t.bold = True; run_t.font.name = "Calibri"; run_t.font.size = Pt(10.5)
    run_t.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
    for item in text_list:
        pi = cell.add_paragraph()
        pi.paragraph_format.space_before = Pt(2); pi.paragraph_format.space_after = Pt(2)
        r = pi.add_run(item); r.font.name = "Calibri"; r.font.size = Pt(9.5)
        r.font.color.rgb = RGBColor(0x33, 0x41, 0x55)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)

def add_code_block(doc, code_str, caption="Code Reference"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, "0F172A")
    set_cell_margins(cell, top=120, bottom=120, left=160, right=160)
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:left w:val="single" w:sz="20" w:space="0" w:color="38BDF8"/>'
        f'<w:top w:val="none"/><w:bottom w:val="none"/><w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0); p.paragraph_format.space_after = Pt(2)
    rc = p.add_run(f"// {caption}\n")
    rc.font.name = "Consolas"; rc.font.size = Pt(8.5)
    rc.font.color.rgb = RGBColor(0x38, 0xBD, 0xF8)
    for line in code_str.strip().split('\n'):
        pl = cell.add_paragraph()
        pl.paragraph_format.space_before = Pt(0); pl.paragraph_format.space_after = Pt(1)
        r = pl.add_run(line); r.font.name = "Consolas"; r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(0xF1, 0xF5, 0xF9)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)

def add_resource_links_table(doc, playlist_url, playlist_title, video_url, video_title, doc_url, doc_title):
    tbl = doc.add_table(rows=3, cols=2)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(tbl, color="CBD5E1")
    col_widths = [Inches(1.8), Inches(4.7)]
    for row in tbl.rows:
        for i, w in enumerate(col_widths):
            row.cells[i].width = w
            set_cell_margins(row.cells[i], top=50, bottom=50, left=100, right=100)
    # Row 0
    set_cell_background(tbl.cell(0, 0), "F8FAFC")
    p0 = tbl.cell(0, 0).paragraphs[0]; p0.paragraph_format.space_before = Pt(0); p0.paragraph_format.space_after = Pt(0)
    r0 = p0.add_run("\U0001f4fa Best YouTube Playlist:"); r0.bold = True; r0.font.size = Pt(9.0); r0.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    pv0 = tbl.cell(0, 1).paragraphs[0]; pv0.paragraph_format.space_before = Pt(0); pv0.paragraph_format.space_after = Pt(0)
    add_hyperlink(pv0, playlist_url, playlist_title, color="2563EB", underline=True, bold=True)
    # Row 1
    set_cell_background(tbl.cell(1, 0), "F8FAFC")
    p1 = tbl.cell(1, 0).paragraphs[0]; p1.paragraph_format.space_before = Pt(0); p1.paragraph_format.space_after = Pt(0)
    r1 = p1.add_run("\U0001f3a5 Deep Dive / One-Shot Video:"); r1.bold = True; r1.font.size = Pt(9.0); r1.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    pv1 = tbl.cell(1, 1).paragraphs[0]; pv1.paragraph_format.space_before = Pt(0); pv1.paragraph_format.space_after = Pt(0)
    add_hyperlink(pv1, video_url, video_title, color="2563EB", underline=True, bold=True)
    # Row 2
    set_cell_background(tbl.cell(2, 0), "F8FAFC")
    p2 = tbl.cell(2, 0).paragraphs[0]; p2.paragraph_format.space_before = Pt(0); p2.paragraph_format.space_after = Pt(0)
    r2 = p2.add_run("\U0001f4d6 Official Documentation:"); r2.bold = True; r2.font.size = Pt(9.0); r2.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    pv2 = tbl.cell(2, 1).paragraphs[0]; pv2.paragraph_format.space_before = Pt(0); pv2.paragraph_format.space_after = Pt(0)
    add_hyperlink(pv2, doc_url, doc_title, color="0D9488", underline=True, bold=True)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)

def H(doc, text, level):
    h = doc.add_heading(text, level=level)
    h.paragraph_format.keep_with_next = True
    run = h.runs[0]; run.font.name = "Calibri"
    if level == 1:
        h.paragraph_format.space_before = Pt(18); h.paragraph_format.space_after = Pt(8)
        run.font.size = Pt(18); run.bold = True; run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
    elif level == 2:
        h.paragraph_format.space_before = Pt(14); h.paragraph_format.space_after = Pt(6)
        run.font.size = Pt(14); run.bold = True; run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
    elif level == 3:
        h.paragraph_format.space_before = Pt(10); h.paragraph_format.space_after = Pt(4)
        run.font.size = Pt(12); run.bold = True; run.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)

def P(doc, text, bold_prefix=None):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(5); p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        rp = p.add_run(bold_prefix); rp.bold = True; rp.font.name = "Calibri"; rp.font.size = Pt(10.5)
        rp.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    r = p.add_run(text); r.font.name = "Calibri"; r.font.size = Pt(10.5); r.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

def B(doc, title, desc):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(3); p.paragraph_format.line_spacing = 1.15
    r1 = p.add_run(title + ": "); r1.bold = True; r1.font.name = "Calibri"; r1.font.size = Pt(10)
    r1.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
    r2 = p.add_run(desc); r2.font.name = "Calibri"; r2.font.size = Pt(10); r2.font.color.rgb = RGBColor(0x33, 0x41, 0x55)


# ── Main ────────────────────────────────────────────────────────────────

def main():
    src = os.path.join(os.path.dirname(__file__), "peakledger",
                       "PeakLedger_Complete_Architecture_and_Engineering_Manual.docx")
    dst = os.path.join(os.path.dirname(__file__),
                       "PeakLedger_Complete_Architecture_and_Engineering_Manual.docx")

    print(f"[*] Loading existing manual: {src}")
    doc = Document(src)

    # ================================================================
    # SECTION 9
    # ================================================================
    H(doc, "9. CyberChain Integration & Unified CryptoLedger Platform Architecture", 1)

    P(doc,
      "PeakLedger Version 2.5 operates as the computational forensic backend within the broader "
      "CryptoLedger unified platform. CryptoLedger integrates three independent, purpose-built "
      "subsystems into a seamless, end-to-end forensic evidence custody pipeline: the Entry Station "
      "for FIDO2 credential ingestion, CyberChain for Ethereum-based blockchain session anchoring "
      "and biometric authentication, and PeakLedger for cryptographic video forensic analysis. "
      "This section provides exhaustive architectural documentation of every CyberChain component, "
      "its integration interfaces with PeakLedger, the on-chain smart contract specification, "
      "the secondary SQL persistence layer, and the complete cross-system data flow.")

    add_callout_box(doc, [
        "Zero-Password Biometric Custody: FIDO2 WebAuthn passkeys ensure only biometrically verified forensic examiners access video evidence. No passwords or emails exist in the system.",
        "Automatic On-Chain Session Anchoring: Every PeakLedger forensic session is automatically sealed into an Ethereum smart contract (SessionAuditLedger.sol) upon examiner logout, creating an immutable blockchain audit trail.",
        "Dual-Persistence Integrity: Session records exist simultaneously on the Anvil EVM blockchain and in the secondary SQLite database (cyberchain.db), with SHA-256 cross-verification.",
        "End-to-End Chain of Custody: From FIDO2 credential enrollment (Entry Station) through forensic analysis (PeakLedger) to immutable blockchain commitment (CyberChain), every step is cryptographically anchored and legally auditable.",
        "Role-Based Access Segregation: Forensic examiners ('user' role) operate PeakLedger; only administrators ('admin' role) can inspect the blockchain audit ledger via the Admin Console."
    ], title="CYBERCHAIN-PEAKLEDGER INTEGRATION ARCHITECTURAL PILLARS")

    # ── 9.1 ──
    H(doc, "9.1 CryptoLedger Unified Platform Overview", 2)
    P(doc,
      "The CryptoLedger platform unifies three independent subsystems into a seamless forensic "
      "evidence custody pipeline, each engineered for a specific domain within the digital forensic "
      "chain of custody:")
    B(doc, "Entry Station (entry/entry_station.py, entry/cli.py)",
      "Dedicated FIDO2/WebAuthn credential ingestion station for pre-enrolling forensic examiners "
      "and administrators with smartphone Bluetooth QR passkeys. Only Name (Username) is compulsory; "
      "the architecture is entirely passwordless with zero email columns. Strictly enforces two roles: "
      "'user' (Forensic Examiner) and 'admin' (Administrator). Provides both a PyQt6 graphical interface "
      "with live user table and a full CLI mode with argparse support.")
    B(doc, "CyberChain (CyberChain/)",
      "Ethereum Virtual Machine (EVM) blockchain custody layer powered by Foundry Anvil. Provides "
      "FIDO2 hardware passkey authentication via embedded HTTP server with W3C WebAuthn hybrid hints, "
      "local Anvil EVM node lifecycle management, Solidity smart contract deployment "
      "(SessionAuditLedger.sol), automatic evidence harvesting from PeakLedger, and immutable on-chain "
      "session audit logging with dual-persistence to a secondary SQLite database (cyberchain.db).")
    B(doc, "PeakLedger (peakledger/)",
      "The C++20/CUDA cryptographic video forensic engine with Two-Layer Decoupled Architecture, "
      "as exhaustively documented in Sections 1 through 8 of this manual. PeakLedger operates as "
      "the computational backend subsystem, launched and monitored by CyberChain during authenticated "
      "forensic sessions.")
    P(doc, "")

    # ── 9.2 ──
    H(doc, "9.2 CyberChain Authentication & Session Lifecycle Architecture", 2)
    P(doc,
      "CyberChain implements a multi-layered authentication and session management architecture "
      "comprising four core modules: the FIDO2/WebAuthn authentication server, the Anvil EVM "
      "blockchain node manager, the SessionAuditLedger Solidity smart contract, and the secondary "
      "SQL database persistence layer.")

    # 9.2.1
    H(doc, "9.2.1 FIDO2/WebAuthn Cross-Device Passkey Authentication Server (auth_server.py)", 3)
    P(doc,
      "The authentication server provides passwordless, biometric-only forensic custody login "
      "via the W3C WebAuthn standard. It is implemented as an embedded Python HTTP server "
      "(http.server.ThreadingHTTPServer) running on port 8088 in a daemon thread.",
      "Architecture Overview: ")
    B(doc, "W3C WebAuthn with Hybrid Transport Hints",
      "The server renders an HTML/CSS/JS authentication page that invokes navigator.credentials.create() "
      "with hints: [\"hybrid\"] to prioritize Phone/Tablet Bluetooth QR code pairing. This forces the "
      "browser to display a scannable QR code that the examiner scans with their iPhone or Android "
      "camera, initiating a Bluetooth Low Energy (BLE) link. The phone then prompts for biometric "
      "verification (fingerprint or face recognition) directly on the device screen.")
    B(doc, "Dual Authenticator Support",
      "Supports both cross-device authentication (smartphone Bluetooth QR, 120-second timeout) and "
      "platform-local authentication (Windows Hello / Mac Touch ID, authenticatorAttachment: \"platform\", "
      "60-second timeout) as a fallback.")
    B(doc, "Strict Credential Validation",
      "Empty, null, or whitespace-only credential_id values are categorically rejected (HTTP 400). "
      "User cancellation or browser prompt closure (NotAllowedError) never falsely triggers verification. "
      "Only a genuine WebAuthn credential with a non-empty ID transitions the session to VERIFIED state.")
    B(doc, "Public Key Algorithms",
      "Supports ES256 (ECDSA P-256, alg: -7) and RS256 (RSA PKCS#1 v1.5, alg: -257) for maximum "
      "cross-device compatibility across iOS, Android, Windows Hello, and YubiKey hardware authenticators.")
    B(doc, "Session State Machine",
      "Authentication sessions are tracked in an in-memory dictionary (active_auth_sessions) keyed by "
      "a 12-character hex session_id (uuid4). Each session transitions through exactly two states: "
      "PENDING (awaiting passkey scan) and VERIFIED (credential confirmed). The CyberChain app polls "
      "is_session_verified() at 500ms intervals via QTimer.")
    P(doc, "")

    # 9.2.2
    H(doc, "9.2.2 Anvil EVM Blockchain Node Management (blockchain.py)", 3)
    P(doc,
      "The blockchain module manages the complete lifecycle of a local Foundry Anvil Ethereum "
      "development node, providing an ephemeral EVM blockchain that exists exclusively for the "
      "duration of each forensic session.",
      "Node Lifecycle Architecture: ")
    B(doc, "Binary Auto-Discovery",
      "Searches for the anvil.exe binary across multiple candidate paths: C:\\Users\\ASUS\\.foundry\\bin, "
      "~/.foundry/bin, ~/.cargo/bin, and the system PATH. Falls back to Ganache (ganache.cmd / ganache) "
      "if Anvil is unavailable, providing broad compatibility across development environments.")
    B(doc, "Subprocess Spawning",
      "Anvil is spawned as a background subprocess with subprocess.Popen using CREATE_NO_WINDOW "
      "(0x08000000) on Windows to prevent console window flicker. Standard output and error are "
      "redirected to DEVNULL for clean operation.")
    B(doc, "Port Readiness Verification",
      "After spawning, the module polls port 8545 via socket.create_connection with a 0.5-second "
      "timeout, retrying for up to 12 seconds. This ensures the JSON-RPC endpoint is fully operational "
      "before any Web3.py contract deployment or transaction submission.")
    B(doc, "Clean Shutdown Protocol",
      "Upon session completion, stop_anvil() executes a graceful three-stage shutdown: "
      "terminate() with a 3-second wait, followed by kill() as a fallback, ensuring no orphaned "
      "blockchain processes persist after the forensic session concludes.")
    P(doc, "")

    # 9.2.3
    H(doc, "9.2.3 SessionAuditLedger.sol Smart Contract (Solidity ^0.8.20)", 3)
    P(doc,
      "The SessionAuditLedger smart contract is the authoritative on-chain forensic audit ledger "
      "that permanently records user session lifecycles, forensic modifications, and cryptographic "
      "integrity hashes upon examiner logout.",
      "Contract Architecture: ")
    B(doc, "SessionLog Struct",
      "Stores 10 fields per session: userId (string), username (string), sessionId (string), "
      "entryTime (uint256 UNIX timestamp), exitTime (uint256 UNIX timestamp), sqlModificationsCount "
      "(uint256), sqlModificationsHash (string, SHA-256 hex digest), detailsJson (string, serialized "
      "JSON of all session modifications), blockTimestamp (uint256, block.timestamp), and recordedBy "
      "(address, msg.sender).")
    B(doc, "recordSessionLogout() External Function",
      "Records a completed user session with all parameters. Enforces sessionId non-emptiness and "
      "duplicate prevention (require(sessions[sessionId].entryTime == 0)). Pushes the sessionId to "
      "both the global sessionIds array and the user-specific userSessionMap. Emits the indexed "
      "SessionLogoutRecorded event for off-chain indexing.")
    B(doc, "View Functions",
      "getSession(sessionId): Returns the complete SessionLog struct. getUserSessions(userId): "
      "Returns all session IDs for a given user. totalSessions(): Returns the count of all recorded "
      "sessions. isSessionRecorded(sessionId): Boolean check for duplicate prevention.")
    B(doc, "Deployment via Web3.py",
      "The contract is deployed programmatically via Web3.py's contract factory pattern using "
      "Anvil's pre-funded account[0]. The ABI and bytecode are loaded from "
      "CyberChain/contracts/SessionAuditLedger.json. After deployment, the contract address, "
      "transaction hash, block number, gas used, and deployer address are captured and persisted.")

    add_code_block(doc, """\
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SessionAuditLedger {
    struct SessionLog {
        string userId;
        string username;
        string sessionId;
        uint256 entryTime;
        uint256 exitTime;
        uint256 sqlModificationsCount;
        string sqlModificationsHash;    // SHA-256 of all modifications
        string detailsJson;             // Full JSON payload
        uint256 blockTimestamp;
        address recordedBy;
    }

    mapping(string => SessionLog) private sessions;
    string[] private sessionIds;
    mapping(string => string[]) private userSessionMap;

    event SessionLogoutRecorded(
        string indexed userId,
        string indexed sessionId,
        uint256 entryTime, uint256 exitTime,
        uint256 sqlModificationsCount,
        string sqlModificationsHash,
        address indexed recordedBy
    );

    function recordSessionLogout(...) external returns (bool);
    function getSession(string calldata sessionId) external view returns (SessionLog memory);
    function getUserSessions(string calldata userId) external view returns (string[] memory);
    function totalSessions() external view returns (uint256);
    function isSessionRecorded(string calldata sessionId) external view returns (bool);
}""", caption="SessionAuditLedger.sol - On-Chain Forensic Audit Ledger Contract Architecture")

    # 9.2.4
    H(doc, "9.2.4 Secondary SQL Database Architecture (database.py)", 3)
    P(doc,
      "CyberChain maintains a secondary SQLite database (CyberChain/storage/cyberchain.db) that "
      "mirrors on-chain session records and stores user identity and passkey enrollment data. "
      "The database auto-initializes its schema on module import (init_db()) and starts with zero "
      "placeholder users.",
      "Database Schema: ")
    B(doc, "users Table",
      "Columns: id (TEXT PRIMARY KEY, UUID4), username (TEXT UNIQUE NOT NULL), role (TEXT NOT NULL "
      "DEFAULT 'user'), created_at (TEXT NOT NULL, ISO 8601). Strictly enforces only two roles: "
      "'user' and 'admin'. Includes role migration logic for existing databases.")
    B(doc, "passkeys Table",
      "Columns: id (TEXT PRIMARY KEY), user_id (TEXT, FOREIGN KEY -> users.id), username (TEXT NOT NULL), "
      "credential_id (TEXT UNIQUE NOT NULL), device_name (TEXT DEFAULT 'Smartphone Biometric Passkey'), "
      "created_at (TEXT NOT NULL). Foreign key cascading links passkeys to their owning user.")
    B(doc, "smart_contract_records Table",
      "17 columns providing complete session audit persistence: id (INTEGER PRIMARY KEY AUTOINCREMENT), "
      "session_id (TEXT UNIQUE NOT NULL), username, role, entry_time, exit_time, duration_seconds (REAL), "
      "changes_count (INTEGER), changes_hash (TEXT, SHA-256), changes_json (TEXT, full JSON payload), "
      "contract_address (TEXT), tx_hash (TEXT), block_number (INTEGER), deployer_address (TEXT), "
      "status (TEXT DEFAULT 'COMMITTED_ON_CHAIN'), recorded_at (TEXT), abi_json (TEXT).")
    B(doc, "Transactional APIs",
      "register_user(): Creates or retrieves users with role normalization. get_user_passkeys(): "
      "Lists all enrolled credentials. record_smart_contract_session(): INSERT OR REPLACE with "
      "computed duration. get_all_smart_contract_records(): Ordered DESC for admin console display. "
      "get_all_users(): JOIN with passkey count aggregation.")
    P(doc, "")

    # ── 9.3 ──
    H(doc, "9.3 CyberChain User Workstation - Complete Session Workflow (app.py)", 2)
    P(doc,
      "The CyberChain User Workstation (CyberChain/app.py) orchestrates the complete forensic "
      "custody session lifecycle through an automated five-step workflow. The application provides "
      "both a PyQt6 graphical interface and a CLI fallback mode.",
      "Workflow Architecture: ")
    B(doc, "Step 1 - Identity Presentation",
      "The examiner enters their Name (the only compulsory field) into a professionally styled "
      "login card interface (dark theme, background #080d14, accent #00ffcc). The user is checked "
      "against cyberchain.db; if not found, a new user record is created automatically.")
    B(doc, "Step 2 - FIDO2 Passkey Authentication",
      "Clicking 'Enter Passkey' starts the embedded auth server, creates a new authentication "
      "session (uuid4 hex[:12]), and opens the browser to the WebAuthn page. The browser displays "
      "a Bluetooth QR code. The examiner scans with their phone camera and confirms via fingerprint. "
      "CyberChain polls auth status at 500ms intervals via QTimer.")
    B(doc, "Step 3 - Blockchain Node & PeakLedger Launch",
      "Upon passkey verification, the Anvil EVM blockchain node starts automatically on port 8545. "
      "PeakLedger forensic workstation UI (peakledger/ui/main.py) is launched as a subprocess using "
      "pythonw.exe (CREATE_NO_WINDOW) with cwd set to peakledger/. The CyberChain window hides itself.")
    B(doc, "Step 4 - Forensic Session Monitoring",
      "A QTimer at 1000ms intervals monitors the PeakLedger subprocess via poll(). Session changes "
      "are tracked in an in-memory list with index, timestamp, and description. The initial change "
      "records the examiner's name, role, and session initialization.")
    B(doc, "Step 5 - Automatic Blockchain Commitment",
      "When PeakLedger closes (subprocess.poll() returns non-None), auto_commit_session() executes: "
      "(1) Harvests tamper_audit_report.json from peakledger/evidence/, extracting video_id, is_pristine, "
      "tampered_packets, suspect_root, and intervals. (2) Checks for Forensic_Report.html existence. "
      "(3) Records all audit findings as session changes. (4) Deploys SessionAuditLedger.sol to Anvil "
      "and calls recordSessionLogout() with the complete session data. (5) Persists the contract address, "
      "tx hash, block number, and full ABI to cyberchain.db via record_smart_contract_session(). "
      "(6) Stops the Anvil node. (7) Displays a professional confirmation dialog showing contract "
      "address, tx hash, block number, and sealed event count. (8) Exits the application.")
    P(doc, "")

    # ── 9.4 ──
    H(doc, "9.4 Administrator Console (admin_app.py)", 2)
    P(doc,
      "The CyberChain Admin Console is a secondary application exclusively accessible to "
      "administrators for inspecting the blockchain audit ledger and verifying forensic session "
      "integrity.",
      "Security & Access Control: ")
    B(doc, "Dual-Gate Admin Authentication",
      "Admin access requires two sequential verifications: (1) Pre-passkey role check against "
      "cyberchain.db rejects non-admin users before the WebAuthn ceremony even begins. (2) Post-passkey "
      "role re-verification ensures the authenticated user still holds admin privileges. Non-admin "
      "users are shown 'Access Denied' and redirected to the login screen.")
    B(doc, "Tab 1: Smart Contract Session Records",
      "Displays a 9-column table (Record ID, Session ID, Username, Role, Entry Time, Exit Time, "
      "Changes Count, Smart Contract Address, Tx Hash) with interactive row selection. Selecting a "
      "record displays the full changes JSON payload and performs live SHA-256 hash recomputation "
      "against the stored changes_hash, displaying a green 'FORENSIC HASH VERIFIED' or red "
      "'HASH MISMATCH' badge.")
    B(doc, "Tab 2: Registered Users & Passkeys",
      "Lists all enrolled users with their UUID (truncated to 8 chars), username, role (color-coded: "
      "admin=#00ffcc, user=#94a3b8), active passkey count, and creation date.")
    B(doc, "Tab 3: Contract ABI & Specification",
      "Displays the full Solidity source code of SessionAuditLedger.sol in a monospaced text editor "
      "(Cascadia Code / Consolas), providing complete transparency into the on-chain audit contract.")
    P(doc, "")

    # ── 9.5 ──
    H(doc, "9.5 Entry Station - Credential Ingestion Subsystem (entry/entry_station.py)", 2)
    P(doc,
      "The Entry Station is a dedicated, standalone application for pre-enrolling forensic "
      "examiners and administrators into the CyberChain ecosystem before they access the forensic "
      "workstation.",
      "Subsystem Architecture: ")
    B(doc, "Embedded WebAuthn Enrollment Server",
      "Runs an independent HTTP server on port 8089 (with fallback to 8090, 8091, 8888, or any "
      "available port) serving a WebAuthn enrollment page with hints: [\"hybrid\"] for Bluetooth "
      "QR code passkey capture. The enrollment page uses the same dark-themed UI as CyberChain.")
    B(doc, "Two-Panel GUI Layout",
      "Left panel: Name input field, Role dropdown ('user (Forensic Examiner)' / 'admin (Administrator)'), "
      "'Launch Phone Bluetooth Passkey Prompt' button with live scan status indicator, and 'Save User & "
      "Passkey to Database' commit button. Right panel: Live table displaying all enrolled users from "
      "cyberchain.db with Name, Role, Passkey count, and enrollment date.")
    B(doc, "QR Session Lifecycle",
      "Each passkey enrollment creates a unique 12-char hex session_id tracked in active_qr_sessions. "
      "The GUI polls for VERIFIED status at 800ms intervals via QTimer. Upon verification, the "
      "captured credential_id and device name are stored locally before database commit.")
    B(doc, "CLI Mode",
      "Full CLI support via argparse: --list (display all users), -u USERNAME -r ROLE -f FINGERPRINT "
      "(direct enrollment), or interactive mode with browser-based QR passkey capture and 30-second "
      "polling timeout.")
    B(doc, "Database Integration",
      "enroll_credential_into_db() validates non-empty username and credential_id, normalizes role "
      "to strictly 'user' or 'admin', and delegates to database.register_user() for ACID persistence "
      "to CyberChain/storage/cyberchain.db.")
    P(doc, "")

    # ── 9.6 ──
    H(doc, "9.6 Integrated Data Flow & Cross-System Communication Architecture", 2)
    P(doc,
      "The CryptoLedger platform implements a unidirectional, event-driven data flow architecture "
      "where each subsystem communicates through well-defined interfaces: filesystem artifacts, "
      "subprocess lifecycle events, SQLite databases, and JSON-RPC blockchain calls.",
      "Cross-System Data Flow: ")
    B(doc, "Entry Station -> cyberchain.db",
      "User identity (Name, UUID4) and FIDO2 credential enrollment (credential_id, device_name) "
      "are persisted to CyberChain/storage/cyberchain.db via SQLite INSERT operations. Role assignment "
      "('user' or 'admin') is committed atomically with the user record.")
    B(doc, "CyberChain app.py -> PeakLedger ui/main.py",
      "PeakLedger is launched as a subprocess via subprocess.Popen([pythonw.exe, peakledger/ui/main.py]) "
      "with the working directory set to peakledger/. Communication is lifecycle-based: CyberChain "
      "monitors PeakLedger's process status via poll() at 1-second intervals.")
    B(doc, "PeakLedger -> peakledger/evidence/",
      "During forensic analysis, PeakLedger generates three primary artifacts: tamper_audit_report.json "
      "(containing video_id, is_pristine, tampered_packets, suspect_root, and intervals), "
      "Forensic_Report.html (NIST SP 800-86 compliant courtroom report), and ledger.db (SQLite "
      "forensic ledger with dual blockchains and Layer 2 metadata).")
    B(doc, "CyberChain <- peakledger/evidence/",
      "Upon PeakLedger process termination, auto_commit_session() reads tamper_audit_report.json "
      "to extract verdict (AUTHENTIC vs TAMPERED with packet mutation count), Merkle root, and "
      "divergence interval data. The existence of Forensic_Report.html triggers a courtroom "
      "admissibility certification change record.")
    B(doc, "CyberChain -> Anvil EVM (localhost:8545)",
      "Web3.py HTTPProvider connects to the local Anvil node. SessionAuditLedger.sol is deployed "
      "via contract factory, and recordSessionLogout() is called with all session data including "
      "the SHA-256 hash of the serialized changes JSON.")
    B(doc, "CyberChain -> cyberchain.db",
      "record_smart_contract_session() persists the complete deployment record: contract_address, "
      "tx_hash, block_number, deployer_address, duration_seconds, changes_hash, changes_json, "
      "and the full contract ABI JSON. This dual-persistence (on-chain + SQL) enables offline "
      "audit verification even after the Anvil node terminates.")
    B(doc, "Admin Console <- cyberchain.db",
      "The admin application reads all smart_contract_records and performs live SHA-256 recomputation "
      "of changes_json against the stored changes_hash, providing real-time data integrity verification.")
    P(doc, "")

    # ── 9.7 ──
    H(doc, "9.7 Security Architecture & Forensic Chain of Custody", 2)
    P(doc,
      "The integrated CryptoLedger platform implements a defense-in-depth security architecture "
      "that guarantees forensic chain of custody from credential enrollment through evidence "
      "analysis to immutable blockchain commitment.",
      "Security Layers: ")
    B(doc, "Passwordless Biometric-Only Access",
      "FIDO2/WebAuthn ensures that only biometrically verified examiners can access the system. "
      "The architecture contains zero password fields, zero email columns, and zero shared secrets. "
      "Authentication relies exclusively on public-key cryptography with device-bound credentials.")
    B(doc, "Automatic On-Chain Session Anchoring",
      "Every PeakLedger forensic session is automatically committed to an Ethereum smart contract "
      "upon examiner logout, without manual intervention. The session entry time, exit time, "
      "examiner identity, and complete modification history are permanently sealed on-chain.")
    B(doc, "SHA-256 Cross-Verification",
      "The SHA-256 hash of all session modifications is computed independently and stored both "
      "on-chain (sqlModificationsHash field in SessionAuditLedger.sol) and off-chain (changes_hash "
      "column in cyberchain.db). The Admin Console performs live recomputation to detect any "
      "unauthorized alterations to the secondary database.")
    B(doc, "Dual-Persistence Immutability",
      "Session records exist simultaneously on the Anvil EVM blockchain (immutable smart contract "
      "storage) and in the secondary SQLite database (for offline access). Any discrepancy between "
      "the two stores is immediately detectable via SHA-256 hash comparison.")
    B(doc, "Role-Based Access Segregation",
      "The system strictly enforces two roles: 'user' (Forensic Examiner) with access to PeakLedger "
      "workstation only, and 'admin' (Administrator) with additional access to the blockchain audit "
      "console. Role verification is performed both before and after passkey authentication.")
    B(doc, "Ephemeral Blockchain Lifecycle",
      "The Anvil EVM node lifecycle is strictly bound to the user session: it starts on login and "
      "stops on logout. This eliminates persistent attack surfaces and ensures no unauthorized "
      "transactions can be submitted outside of authenticated forensic sessions.")
    B(doc, "Bharatiya Sakshya Adhiniyam (BSA) 2023 Compliance",
      "The dual-layer custody architecture (PeakLedger's cryptographic Merkle proofs + CyberChain's "
      "blockchain session anchoring) satisfies Section 63 of BSA 2023 for electronic record "
      "admissibility, providing mathematically verifiable chain-of-custody from video ingestion "
      "through examiner session to courtroom presentation.")
    P(doc, "")

    # ── 9.8 ──
    H(doc, "9.8 Technology Stack Additions for CyberChain Integration", 2)
    P(doc,
      "The CyberChain integration introduces four additional core technologies to the PeakLedger "
      "ecosystem, each selected for its cryptographic robustness, standards compliance, and "
      "forensic audit capabilities.")

    # 9.8.1 Web3.py
    H(doc, "9.8.1 Web3.py - Ethereum Python Interaction Library", 3)
    P(doc,
      "Web3.py is the comprehensive Python library for interacting with Ethereum-compatible "
      "blockchains. It provides contract deployment, transaction management, ABI encoding/decoding, "
      "account management, and JSON-RPC communication with EVM nodes.",
      "Context & Industry Standard: ")
    P(doc,
      "In CyberChain, Web3.py (Web3.HTTPProvider) connects to the local Anvil EVM node at "
      "http://127.0.0.1:8545. It loads contract artifacts (ABI + bytecode) from "
      "SessionAuditLedger.json, deploys the contract via contract factory constructor().transact(), "
      "executes recordSessionLogout() transactions with all session parameters, and retrieves "
      "on-chain session data via getSession().call() for verification.",
      "Role in CyberChain: ")
    add_resource_links_table(doc,
        "https://www.youtube.com/playlist?list=PLJz1HruEnenCwMg5NU_c6gU8FRw4sWu9f",
        "Patrick Collins - Python & Solidity Blockchain Development",
        "https://www.youtube.com/watch?v=M576WGiDBdQ",
        "freeCodeCamp.org - Web3.py: Ethereum Smart Contracts with Python (Full Course)",
        "https://web3py.readthedocs.io/",
        "Web3.py Official Documentation & API Reference")

    # 9.8.2 Foundry Anvil
    H(doc, "9.8.2 Foundry Anvil - Local EVM Development Blockchain Node", 3)
    P(doc,
      "Foundry Anvil is a blazingly fast local Ethereum development node written in Rust, part of "
      "the Foundry smart contract development toolkit. It provides instant block mining, 10 "
      "pre-funded accounts with 10,000 ETH each, and full EVM compatibility with zero configuration.",
      "Context & Industry Standard: ")
    P(doc,
      "In CyberChain, Anvil provides a zero-configuration, ephemeral EVM blockchain that starts "
      "on user login and stops on logout. It accepts standard JSON-RPC calls on port 8545, supports "
      "Solidity ^0.8.20 contract deployment, and provides deterministic account addresses for "
      "consistent contract deployment across sessions.",
      "Role in CyberChain: ")
    add_resource_links_table(doc,
        "https://www.youtube.com/playlist?list=PL4Rj_WH6yLgWe7TxankiqkrkVKXIwOP42",
        "Smart Contract Programmer - Foundry Tutorial Series",
        "https://www.youtube.com/watch?v=fNMfMxGxeag",
        "Patrick Collins - Foundry Full Course: Solidity Development & Testing",
        "https://book.getfoundry.sh/reference/anvil/",
        "Foundry Book - Anvil Reference & Configuration Guide")

    # 9.8.3 WebAuthn
    H(doc, "9.8.3 W3C WebAuthn / FIDO2 Cross-Device Passkey Authentication Standard", 3)
    P(doc,
      "WebAuthn (Web Authentication) is a W3C standard for passwordless authentication using "
      "public-key cryptography and biometric authenticators. FIDO2 extends WebAuthn with the "
      "Client-to-Authenticator Protocol (CTAP2) for cross-device Bluetooth and NFC communication.",
      "Context & Industry Standard: ")
    P(doc,
      "In CyberChain, WebAuthn with hints: [\"hybrid\"] enables cross-device authentication via "
      "smartphone Bluetooth QR code pairing. The auth_server.py implements "
      "navigator.credentials.create() with ES256 (alg: -7) and RS256 (alg: -257) algorithms, "
      "enforcing userVerification: \"required\" for mandatory biometric (fingerprint/face) "
      "confirmation. The entry_station.py uses identical WebAuthn parameters for credential enrollment.",
      "Role in CyberChain: ")
    add_resource_links_table(doc,
        "https://www.youtube.com/playlist?list=PLAhKmR1FnuF7kIp0tRUUaCGcRzB9L6PSB",
        "FIDO Alliance - WebAuthn & Passkey Implementation Series",
        "https://www.youtube.com/watch?v=aMo4ZlWznao",
        "Fireship - WebAuthn & Passkeys Explained in 100 Seconds",
        "https://www.w3.org/TR/webauthn-3/",
        "W3C Web Authentication Level 3 Specification")

    # 9.8.4 Solidity
    H(doc, "9.8.4 Solidity - Ethereum Smart Contract Programming Language", 3)
    P(doc,
      "Solidity is the primary high-level programming language for implementing smart contracts "
      "on the Ethereum Virtual Machine (EVM). It is statically typed, supports inheritance, "
      "libraries, and complex user-defined types, and compiles to EVM bytecode for on-chain execution.",
      "Context & Industry Standard: ")
    P(doc,
      "In CyberChain, SessionAuditLedger.sol (Solidity ^0.8.20) defines the on-chain forensic "
      "audit ledger. The contract stores SessionLog structs containing 10 fields of session lifecycle "
      "data, emits indexed SessionLogoutRecorded events for off-chain log monitoring, and provides "
      "getSession(), getUserSessions(), totalSessions(), and isSessionRecorded() view functions for "
      "audit querying. Duplicate session prevention is enforced via require() guards.",
      "Role in CyberChain: ")
    add_resource_links_table(doc,
        "https://www.youtube.com/playlist?list=PLO5VPQH6OWdVQwpQfw9rZ67O6Pjfo6q-p",
        "Smart Contract Programmer - Solidity Tutorial Series",
        "https://www.youtube.com/watch?v=gyMwXuJrbJQ",
        "Patrick Collins - Learn Solidity, Blockchain Development (Full Course)",
        "https://docs.soliditylang.org/",
        "Solidity Official Documentation & Language Reference")

    # ── Save ──
    print(f"[*] Saving updated manual to: {dst}")
    doc.save(dst)
    print(f"[+] SUCCESS: Updated PeakLedger Architecture Manual saved!")
    print(f"    Location: {dst}")
    print(f"    Total paragraphs: {len(doc.paragraphs)}")

if __name__ == "__main__":
    main()
