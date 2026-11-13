#!/usr/bin/env python3
"""
CyberChain Secondary SQL Database Manager.
Stores:
- Users (ONLY 'username' / Name is compulsory - No email, No password)
- Hardware and Biometric Passkeys (FIDO2 / WebAuthn)
- Smart Contract transaction records & session lifecycle audit logs
Zero placeholder users: starts 100% clean.
"""
import os
import json
import sqlite3
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

CYBERCHAIN_DIR = Path(__file__).resolve().parent
STORAGE_DIR = CYBERCHAIN_DIR / "storage"
DB_PATH = STORAGE_DIR / "cyberchain.db"


def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with row factory enabled."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes clean database schema with zero placeholder users."""
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Users Table (Name / Username compulsory, Role strictly 'user' or 'admin')
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    """)

    # 2. Passkey Credentials Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS passkeys (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            credential_id TEXT UNIQUE NOT NULL,
            device_name TEXT DEFAULT 'Smartphone Biometric Passkey',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # 3. Smart Contract Records (Secondary SQL persistence for Anvil sessions)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS smart_contract_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            entry_time TEXT NOT NULL,
            exit_time TEXT NOT NULL,
            duration_seconds REAL DEFAULT 0,
            changes_count INTEGER DEFAULT 0,
            changes_hash TEXT NOT NULL,
            changes_json TEXT NOT NULL,
            contract_address TEXT NOT NULL,
            tx_hash TEXT NOT NULL,
            block_number INTEGER DEFAULT 0,
            deployer_address TEXT,
            status TEXT DEFAULT 'COMMITTED_ON_CHAIN',
            recorded_at TEXT NOT NULL,
            abi_json TEXT
        )
    """)

    # Migrations for existing DB if needed
    try:
        cur.execute("PRAGMA table_info(users)")
        cols = [c[1] for c in cur.fetchall()]
        if "role" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    except Exception:
        pass

    try:
        cur.execute("PRAGMA table_info(smart_contract_records)")
        cols = [c[1] for c in cur.fetchall()]
        if "role" not in cols:
            cur.execute("ALTER TABLE smart_contract_records ADD COLUMN role TEXT DEFAULT 'user'")
    except Exception:
        pass

    conn.commit()
    conn.close()


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Retrieves a user by username."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_user_passkeys(username: str) -> List[Dict[str, Any]]:
    """Retrieves all enrolled passkeys for a user."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM passkeys WHERE username = ?", (username.strip(),))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def register_user(
    username: str,
    role: str = "user",
    credential_id: Optional[str] = None,
    device_name: str = "Smartphone Biometric Passkey"
) -> Dict[str, Any]:
    """
    Registers or retrieves a user by Name and role ('user' or 'admin').
    Associates their enrolled passkey.
    """
    username = username.strip()
    if not username:
        raise ValueError("Username / Name is compulsory.")

    # Strictly enforce only two roles: 'admin' and 'user'
    normalized_role = "admin" if str(role).strip().lower() == "admin" else "user"

    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    cur.execute("SELECT id, role FROM users WHERE username = ?", (username,))
    row = cur.fetchone()

    if row:
        uid = row["id"]
        # Update role if explicitly provided
        if role:
            cur.execute("UPDATE users SET role = ? WHERE id = ?", (normalized_role, uid))
    else:
        uid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO users (id, username, role, created_at) VALUES (?, ?, ?, ?)",
            (uid, username, normalized_role, now)
        )

    if credential_id:
        cur.execute("SELECT id FROM passkeys WHERE credential_id = ?", (credential_id,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO passkeys (id, user_id, username, credential_id, device_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), uid, username, credential_id, device_name, now))

    conn.commit()
    conn.close()

    return {
        "user_id": uid,
        "username": username,
        "role": normalized_role,
        "credential_id": credential_id,
        "device_name": device_name
    }


def record_smart_contract_session(
    session_id: str,
    username: str,
    entry_time: str,
    exit_time: str,
    changes_list: List[Dict[str, Any]],
    contract_address: str,
    tx_hash: str,
    block_number: int,
    deployer_address: str,
    role: str = "user",
    abi_json: Optional[str] = None
) -> int:
    """Stores full smart contract deployment and session audit into secondary SQL DB."""
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    try:
        t_in = datetime.fromisoformat(entry_time)
        t_out = datetime.fromisoformat(exit_time)
        duration = (t_out - t_in).total_seconds()
    except Exception:
        duration = 0.0

    changes_json = json.dumps(changes_list, indent=2)
    changes_hash = hashlib.sha256(changes_json.encode()).hexdigest()
    normalized_role = "admin" if str(role).strip().lower() == "admin" else "user"

    cur.execute("""
        INSERT OR REPLACE INTO smart_contract_records (
            session_id, username, role, entry_time, exit_time,
            duration_seconds, changes_count, changes_hash, changes_json,
            contract_address, tx_hash, block_number, deployer_address,
            status, recorded_at, abi_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMMITTED_ON_CHAIN', ?, ?)
    """, (
        session_id, username, normalized_role, entry_time, exit_time,
        duration, len(changes_list), changes_hash, changes_json,
        contract_address, tx_hash, block_number, deployer_address,
        now, abi_json
    ))

    record_id = cur.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_all_smart_contract_records() -> List[Dict[str, Any]]:
    """Retrieves all session records from the secondary SQL DB."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM smart_contract_records ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_users() -> List[Dict[str, Any]]:
    """Retrieves all registered users with their role and passkey counts."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.username, u.role, u.created_at,
               COUNT(p.id) as passkey_count
        FROM users u
        LEFT JOIN passkeys p ON p.user_id = u.id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Auto-initialize clean schema on import
init_db()
