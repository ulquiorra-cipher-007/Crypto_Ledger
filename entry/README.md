# CyberChain Dedicated Credentials & Biometric Passkey Entry Station

This folder (`entry/`) provides the ingestion station to register user credentials and enroll hardware/biometric passkeys directly into `CyberChain/storage/cyberchain.db`.

## Features:
- **Username, Email, Role, Password**: Enrolls forensic accounts with role authorities.
- **Smartphone Biometric Passkey QR Scan**: Generates an instant QR code. Pointing your smartphone camera triggers Touch ID / Android Biometric / WebAuthn, registers the passkey, and closes the mobile window automatically.
- **Zero React / Zero Svelte**: Streamlined pure HTML/CSS/JS WebAuthn implementation.
- **Secondary SQL Database**: Directly committed to `CyberChain/storage/cyberchain.db`.

## How to Run:
- **Windows**:
  Double-click `entry.bat` (or `run.bat`).
- **Linux / WSL**:
  ```bash
  ./run.sh
  ```
- **CLI Commands**:
  - List all enrolled users:
    ```bash
    python cli.py --list
    ```
  - Enroll via CLI:
    ```bash
    python cli.py -u examiner_02 -e examiner02@cyberchain.local -p Password123! -r FORENSIC_EXAMINER
    ```
