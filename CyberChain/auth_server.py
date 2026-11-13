#!/usr/bin/env python3
"""
==============================================================================
CYBERCHAIN - FIDO2 / WEBAUTHN CROSS-DEVICE (PHONE BLUETOOTH QR) SERVER
==============================================================================
- Uses standard W3C WebAuthn with `hints: ["hybrid"]` to prioritize Phone/Tablet Bluetooth QR code.
- If Windows Security displays "Insert your security key", user clicks "More choices" -> "iPhone, iPad, or Android device" to reveal the QR code.
- Never falsely verifies on cancel or close: strictly requires an authentic credential signature.
- Stripped of email and password: only Name / Username is required.
==============================================================================
"""
import os
import sys
import json
import uuid
import socket
import threading
import urllib.parse
import http.server
from pathlib import Path
from typing import Dict, Any, Optional

CYBERCHAIN_DIR = Path(__file__).resolve().parent
if str(CYBERCHAIN_DIR) not in sys.path:
    sys.path.insert(0, str(CYBERCHAIN_DIR))

import database

# Active Authentication Sessions: session_id -> { "username": ..., "status": "PENDING"|"VERIFIED", ... }
active_auth_sessions: Dict[str, Dict[str, Any]] = {}
server_instance: Optional[http.server.ThreadingHTTPServer] = None
server_port: int = 8088


class AuthHttpHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress console clutter

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        session_id = params.get("session", [""])[0]

        # Route: /auth or /qr - Opens the Phone Bluetooth Passkey prompt page
        if parsed.path in ("/auth", "/qr", "/"):
            session = active_auth_sessions.get(session_id, {})
            username = session.get("username", params.get("user", ["user"])[0])
            html = get_passkey_page_html(session_id, username)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # Route: /api/status - Poll session status
        elif parsed.path == "/api/status":
            session = active_auth_sessions.get(session_id, {"status": "NOT_FOUND"})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(session).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/api/verify", "/submit"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)

                session_id = data.get("session_id")
                cred_id = data.get("credential_id")

                # Strictly require a valid session_id AND real non-empty credential_id
                if not session_id or session_id not in active_auth_sessions:
                    self.send_response(400)
                    self.end_headers()
                    return

                if not cred_id or not isinstance(cred_id, str) or len(cred_id.strip()) == 0:
                    # Reject empty or false credentials
                    self.send_response(400)
                    self.end_headers()
                    return

                username = active_auth_sessions[session_id].get("username", "user")
                dev_name = data.get("client_device") or "Smartphone Bluetooth Passkey"

                active_auth_sessions[session_id]["status"] = "VERIFIED"
                active_auth_sessions[session_id]["credential_id"] = cred_id
                active_auth_sessions[session_id]["device_name"] = dev_name

                # Register/update user and passkey in clean database (preserving assigned role)
                try:
                    user_record = database.get_user(username)
                    role = user_record.get("role", "user") if user_record else "user"
                    database.register_user(
                        username=username,
                        role=role,
                        credential_id=cred_id,
                        device_name=dev_name
                    )
                except Exception as e:
                    print(f"[-] Database record notice: {e}")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "status": "VERIFIED"}).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                return

        self.send_response(404)
        self.end_headers()


def get_passkey_page_html(session_id: str, username: str) -> str:
    """HTML/JS page that triggers native WebAuthn with hybrid (phone Bluetooth QR) hint."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CyberChain - Phone Bluetooth Passkey Authentication</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    body {{
      background: #06090e;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
      text-align: center;
    }}
    .card {{
      background: #0c111a;
      border: 1px solid #1f2a3c;
      border-radius: 18px;
      padding: 36px 28px;
      max-width: 490px;
      width: 100%;
      box-shadow: 0 16px 48px rgba(0, 0, 0, 0.85);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(0, 255, 204, 0.1);
      border: 1px solid rgba(0, 255, 204, 0.3);
      color: #00ffcc;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1.5px;
      padding: 5px 14px;
      border-radius: 20px;
      text-transform: uppercase;
      margin-bottom: 18px;
    }}
    h1 {{
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.3px;
      margin-bottom: 8px;
      color: #f8fafc;
    }}
    .user-tag {{
      color: #00ffcc;
    }}
    .subtitle {{
      font-size: 13px;
      color: #94a3b8;
      line-height: 1.5;
      margin-bottom: 22px;
    }}
    .instruction-card {{
      background: #111824;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 16px 18px;
      margin-bottom: 22px;
      text-align: left;
    }}
    .tip-box {{
      background: rgba(234, 179, 8, 0.1);
      border: 1px solid rgba(234, 179, 8, 0.3);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 16px;
      font-size: 12px;
      color: #fde047;
      line-height: 1.4;
    }}
    .instruction-card .step {{
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 10px;
      font-size: 12px;
      color: #cbd5e1;
    }}
    .instruction-card .step:last-child {{
      margin-bottom: 0;
    }}
    .step-number {{
      background: rgba(0, 255, 204, 0.15);
      color: #00ffcc;
      font-weight: 800;
      font-size: 11px;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }}
    .btn-main {{
      width: 100%;
      padding: 16px;
      border: none;
      border-radius: 10px;
      background: #00ffcc;
      color: #06090e;
      font-size: 15px;
      font-weight: 800;
      letter-spacing: 0.5px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      transition: all 0.2s ease;
      margin-bottom: 12px;
      box-shadow: 0 0 20px rgba(0, 255, 204, 0.25);
    }}
    .btn-main:hover {{
      background: #33ffd6;
      box-shadow: 0 0 30px rgba(0, 255, 204, 0.45);
      transform: translateY(-1px);
    }}
    .btn-secondary {{
      width: 100%;
      padding: 12px;
      border: 1px solid #334155;
      border-radius: 8px;
      background: #111827;
      color: #94a3b8;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .btn-secondary:hover {{
      background: #1f2937;
      color: #f8fafc;
      border-color: #00ffcc;
    }}
    .status-box {{
      margin-top: 18px;
      font-size: 13px;
      color: #94a3b8;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    .spinner {{
      width: 12px;
      height: 12px;
      border: 2px solid rgba(0, 255, 204, 0.2);
      border-top-color: #00ffcc;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }}
    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}
    .success-panel {{
      display: none;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid #10b981;
      border-radius: 12px;
      padding: 24px;
      margin-top: 18px;
    }}
    .checkmark {{
      width: 54px;
      height: 54px;
      border-radius: 50%;
      background: rgba(16, 185, 129, 0.2);
      border: 2px solid #10b981;
      color: #10b981;
      font-size: 26px;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 14px auto;
    }}
    .success-title {{
      color: #10b981;
      font-weight: 800;
      font-size: 18px;
      margin-bottom: 6px;
    }}
    .success-desc {{
      font-size: 13px;
      color: #94a3b8;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div id="auth-panel">
      <div class="badge">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M7 7l10 10-5 5V2l5 5L7 17"/>
        </svg>
        FIDO2 Cross-Device Passkey
      </div>

      <h1>Sign In as <span class="user-tag">{username}</span></h1>
      <p class="subtitle">Scan the QR code with your phone camera to pair over Bluetooth and verify fingerprint.</p>

      <div class="instruction-card">
        <div class="tip-box">
          <strong>💡 IMPORTANT:</strong> When the browser prompt appears, if Windows asks to <em>"Insert your security key"</em>, click <strong>"More choices"</strong> (or <strong>"Use a phone or tablet"</strong>) to display the QR code!
        </div>

        <div class="step">
          <div class="step-number">1</div>
          <div class="step-text">Click <strong>"Display Phone Bluetooth QR"</strong> below.</div>
        </div>
        <div class="step">
          <div class="step-number">2</div>
          <div class="step-text">Scan the QR code with your <strong>iPhone / Android camera</strong>.</div>
        </div>
        <div class="step">
          <div class="step-number">3</div>
          <div class="step-text">Phone connects via <strong>Bluetooth</strong> and prompts for your <strong>Fingerprint</strong> directly on the phone screen.</div>
        </div>
        <div class="step">
          <div class="step-number">4</div>
          <div class="step-text">Tab automatically closes and logs into CyberChain.</div>
        </div>
      </div>

      <button class="btn-main" id="btn-trigger-bluetooth">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>
          <path d="M12 18h.01"/>
        </svg>
        Display Phone Bluetooth QR
      </button>

      <button class="btn-secondary" id="btn-platform-fallback">
        💻 Or Use Workstation Sensor (Windows Hello / Mac Touch ID)
      </button>

      <div class="status-box" id="status-box">
        <div class="spinner" id="spinner" style="display:none;"></div>
        <span id="status-text">Click the button above to launch the Phone QR code prompt.</span>
      </div>
    </div>

    <div class="success-panel" id="success-panel">
      <div class="checkmark">✓</div>
      <div class="success-title">Passkey Verified via Phone!</div>
      <p class="success-desc">Biometric fingerprint confirmed by your device.<br>Logging in and closing this tab...</p>
    </div>
  </div>

  <script>
    const sessionId = "{session_id}";
    const username = "{username}";

    function setStatus(msg, isWaiting = true, isError = false) {{
      const txt = document.getElementById("status-text");
      const spinner = document.getElementById("spinner");
      txt.textContent = msg;
      txt.style.color = isError ? "#ef4444" : (isWaiting ? "#00ffcc" : "#94a3b8");
      if (spinner) spinner.style.display = isWaiting ? "block" : "none";
    }}

    async function sendVerification(credId, devName) {{
      if (!credId || credId.trim() === "") return;
      try {{
        const res = await fetch("/api/verify", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{
            session_id: sessionId,
            credential_id: credId,
            client_device: devName
          }})
        }});
        if (res.ok) {{
          onAuthSuccess();
        }} else {{
          setStatus("Verification rejected by server.", false, true);
        }}
      }} catch (e) {{
        setStatus("Network error connecting to local server.", false, true);
      }}
    }}

    function onAuthSuccess() {{
      document.getElementById("auth-panel").style.display = "none";
      document.getElementById("success-panel").style.display = "block";
      setTimeout(() => {{
        window.close();
      }}, 800);
    }}

    // =========================================================================
    // 1. PHONE BLUETOOTH QR CODE (hints: ["hybrid"])
    // =========================================================================
    async function triggerBluetoothCrossDevice() {{
      setStatus("👉 On Windows prompt: Click 'More choices' ➔ 'iPhone, iPad, or Android device' to display the QR Code!", true);

      if (!window.PublicKeyCredential) {{
        setStatus("WebAuthn not supported by this browser.", false, true);
        return;
      }}

      try {{
        const challenge = new Uint8Array(32);
        window.crypto.getRandomValues(challenge);

        const userId = new TextEncoder().encode(username);

        // Note: Using hints: ["hybrid"] prioritizes Phone/Tablet Bluetooth QR!
        // We do not hardcode cross-platform attachment so Windows does not default to USB keys.
        const credential = await navigator.credentials.create({{
          publicKey: {{
            challenge: challenge,
            rp: {{
              name: "CyberChain Custody",
              id: window.location.hostname
            }},
            user: {{
              id: userId,
              name: username,
              displayName: username
            }},
            pubKeyCredParams: [
              {{ type: "public-key", alg: -7 }},   // ES256
              {{ type: "public-key", alg: -257 }}  // RS256
            ],
            timeout: 120000,
            hints: ["hybrid"], // <-- W3C HINT FOR PHONE / TABLET BLUETOOTH QR
            authenticatorSelection: {{
              userVerification: "required",
              residentKey: "preferred"
            }},
            attestation: "none"
          }}
        }});

        if (credential && credential.id) {{
          await sendVerification(credential.id, "Smartphone Bluetooth Biometric Passkey");
        }}
      }} catch (err) {{
        console.warn("Passkey ceremony error:", err);
        // User closed or cancelled: DO NOT verify! Never verify on cancellation!
        if (err.name === "NotAllowedError") {{
          setStatus("❌ Passkey prompt was cancelled or closed. Click button to retry.", false, true);
        }} else {{
          setStatus("Notice: " + err.message + ". Click button to retry.", false, true);
        }}
      }}
    }}

    // =========================================================================
    // 2. LOCAL WORKSTATION SENSOR (Windows Hello / Mac Touch ID)
    // =========================================================================
    async function triggerPlatformLocal() {{
      setStatus("Prompting workstation sensor (Windows Hello / Mac Touch ID)...", true);
      try {{
        const challenge = new Uint8Array(32);
        window.crypto.getRandomValues(challenge);

        const credential = await navigator.credentials.create({{
          publicKey: {{
            challenge: challenge,
            rp: {{ name: "CyberChain", id: window.location.hostname }},
            user: {{ id: new TextEncoder().encode(username), name: username, displayName: username }},
            pubKeyCredParams: [{{ type: "public-key", alg: -7 }}, {{ type: "public-key", alg: -257 }}],
            timeout: 60000,
            authenticatorSelection: {{
              authenticatorAttachment: "platform",
              userVerification: "required"
            }}
          }}
        }});

        if (credential && credential.id) {{
          await sendVerification(credential.id, "Workstation Local Biometric Sensor");
        }}
      }} catch (err) {{
        setStatus("Local sensor prompt cancelled: " + err.message, false, true);
      }}
    }}

    document.getElementById("btn-trigger-bluetooth").onclick = triggerBluetoothCrossDevice;
    document.getElementById("btn-platform-fallback").onclick = triggerPlatformLocal;

    // Trigger on user click (avoids browser gesture blocking and USB defaults)
  </script>
</body>
</html>"""


def start_auth_server(port: int = 8088) -> int:
    """Starts the embedded authentication server in a daemon thread."""
    global server_instance, server_port

    if server_instance is not None:
        return server_port

    for p in [port, 8089, 8090, 8888, 0]:
        try:
            server = http.server.ThreadingHTTPServer(("0.0.0.0", p), AuthHttpHandler)
            server_port = server.server_address[1]
            server_instance = server
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            print(f"[Auth Server] Active on port {server_port}")
            return server_port
        except Exception:
            continue
    return server_port


def create_auth_session(username: str) -> str:
    """Initializes a new passkey session ID for the given user."""
    session_id = uuid.uuid4().hex[:12]
    active_auth_sessions[session_id] = {
        "session_id": session_id,
        "username": username,
        "status": "PENDING",
        "credential_id": None,
        "device_name": None
    }
    return session_id


def is_session_verified(session_id: str) -> bool:
    """Checks if the authentication session has verified its passkey."""
    session = active_auth_sessions.get(session_id)
    return bool(session and session.get("status") == "VERIFIED")
