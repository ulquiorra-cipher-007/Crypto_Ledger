# CyberChain - Streamlined Hardware Passkey & Smart Contract Session Ledger

CyberChain provides a streamlined, zero-bloat authentication and on-chain session auditing architecture:
- **No React / No Svelte**: Pure, minimal HTML/CSS/JS for QR code display and native mobile WebAuthn passkey scanning.
- **Severed from PeakLedger**: Fully decoupled, standalone custody and authentication system.
- **On-Demand Anvil EVM Blockchain**: Automatically starts Anvil upon login and records session entry, exit, username, and modifications as a smart contract upon logout.
- **Secondary SQL Database (`cyberchain.db`)**: Stores all smart contract deployments, transactions, and session records permanently across ephemeral Anvil restarts.
- **Admin Audit Console (`admin_app.py`)**: Dedicated application to inspect on-chain session records and verify cryptographic SHA-256 integrity proofs.

---

## 🏛️ System Architecture

```
1. APP OPEN (app.py)
   ┌─────────────────────────────────────────────────────────────┐
   │ Interface: Username Input + "Enter Passkey" Button          │
   └──────────────────────────────┬──────────────────────────────┘
                                  │ Clicks "Enter Passkey"
                                  ▼
2. QR CODE DISPLAY (auth_server.py)
   ┌─────────────────────────────────────────────────────────────┐
   │ Pure HTML/CSS Page: Displays strictly the QR code           │
   │ - Mobile scans QR code -> prompts Touch ID / Passkey        │
   │ - Tab polls status and automatically closes (`window.close()│
   └──────────────────────────────┬──────────────────────────────┘
                                  │ Scanned & Verified
                                  ▼
3. SESSION & ANVIL STARTUP
   ┌─────────────────────────────────────────────────────────────┐
   │ - Anvil EVM Blockchain node starts (:8545)                  │
   │ - User logs modifications / changes during session          │
   └──────────────────────────────┬──────────────────────────────┘
                                  │ User Clicks "Logout"
                                  ▼
4. SMART CONTRACT DEPLOYMENT & SECONDARY SQL DB COMMIT
   ┌─────────────────────────────────────────────────────────────┐
   │ - Anvil receives `recordSessionLogout` on `SessionAuditLedger`
   │ - Tx hash, block number, contract address, entry/exit times,│
   │   and full modifications JSON saved to secondary SQL DB     │
   │ - Anvil node stops gracefully                               │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
5. ADMIN INSPECTOR (admin_app.py)
   ┌─────────────────────────────────────────────────────────────┐
   │ Secondary Admin App inside CyberChain:                      │
   │ - Inspects all smart contracts & sessions in SQLite DB       │
   │ - Recomputes SHA-256 hash to prove forensic tamper integrity│
   │ - Inspects registered users and passkey credentials         │
   └─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Running the Applications

### User Workstation (`app.py`):
- **Windows**: Double-click `run_app.bat` or run:
  ```cmd
  python app.py
  ```
- **Linux / WSL**:
  ```bash
  ./run_app.sh
  ```

### Admin Audit Console (`admin_app.py`):
- **Windows**: Double-click `run_admin.bat` or run:
  ```cmd
  python admin_app.py
  ```
- **Linux / WSL**:
  ```bash
  ./run_admin.sh
  ```
