#!/usr/bin/env python3
"""
CyberChain Anvil Blockchain & Smart Contract Manager.
Responsibilities:
- Starts local Anvil EVM node upon user login
- Deploys SessionAuditLedger.sol smart contract
- Registers full session lifecycle (entry time, exit time, username, changes) on logout
- Stops Anvil node cleanly upon session completion
"""
import os
import sys
import time
import socket
import json
import shutil
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

CYBERCHAIN_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = CYBERCHAIN_DIR / "contracts"
CONTRACT_JSON_PATH = CONTRACTS_DIR / "SessionAuditLedger.json"

# Process handle for Anvil
anvil_process: Optional[subprocess.Popen] = None


def find_anvil_binary() -> Optional[str]:
    """Locates the anvil or ganache executable in native Windows environments."""
    is_win = sys.platform == "win32"

    # Check foundry bin path
    candidate_paths = [
        "C:\\Users\\ASUS\\.foundry\\bin\\anvil.exe",
        os.path.expanduser("~/.foundry/bin/anvil.exe"),
        os.path.expanduser("~/.cargo/bin/anvil.exe"),
    ]

    for p in candidate_paths:
        if os.path.exists(p):
            return p

    # Check PATH for anvil
    which_anvil = shutil.which("anvil.exe") or shutil.which("anvil")
    if which_anvil:
        return which_anvil

    # Check ganache fallback if anvil is missing
    which_ganache = shutil.which("ganache.cmd") or shutil.which("ganache")
    if which_ganache:
        return which_ganache

    return None


def is_port_open(port: int = 8545, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Checks if an EVM node is actively listening on the target port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def wait_for_rpc(port: int = 8545, timeout: float = 15.0) -> bool:
    """Waits until the Anvil node responds to JSON-RPC calls."""
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(port):
            return True
        time.sleep(0.3)
    return False


def start_anvil(port: int = 8545) -> bool:
    """
    Spawns an Anvil / EVM blockchain node on port 8545.
    Called automatically when the user successfully authenticates.
    """
    global anvil_process

    if is_port_open(port):
        print(f"[Blockchain] EVM Node already running on 127.0.0.1:{port}")
        return True

    anvil_bin = find_anvil_binary()
    if not anvil_bin:
        print("[Blockchain] Warning: 'anvil' or 'ganache' executable not found.")
        return False

    is_win = sys.platform == "win32"

    if "ganache" in str(anvil_bin).lower():
        print(f"[Blockchain] Starting EVM node using Ganache ({anvil_bin}) on port {port}...")
        cmd = [anvil_bin, "-p", str(port), "-q"]
        use_shell = is_win
    else:
        print(f"[Blockchain] Starting Anvil node using: {anvil_bin} on port {port}...")
        cmd = [anvil_bin, "--port", str(port), "--silent"]
        use_shell = is_win and (str(anvil_bin).lower().endswith(".cmd") or str(anvil_bin).lower().endswith(".bat"))

    creation_flags = 0
    if is_win:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    try:
        anvil_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=use_shell,
            creationflags=creation_flags
        )
        ready = wait_for_rpc(port, timeout=12.0)
        if ready:
            print(f"[Blockchain] Anvil EVM node is active at http://127.0.0.1:{port}")
            return True
        else:
            print("[Blockchain] Node started but port did not open in time.")
            return False
    except Exception as e:
        print(f"[Blockchain] Failed to start blockchain node: {e}")
        return False


def stop_anvil():
    """Stops the Anvil subprocess gracefully."""
    global anvil_process
    if anvil_process:
        print("[Blockchain] Stopping Anvil EVM node...")
        try:
            anvil_process.terminate()
            anvil_process.wait(timeout=3)
        except Exception:
            try:
                anvil_process.kill()
            except Exception:
                pass
        anvil_process = None
        print("[Blockchain] Anvil node stopped.")


def load_contract_artifact() -> Dict[str, Any]:
    """Loads ABI and bytecode from SessionAuditLedger.json."""
    if not CONTRACT_JSON_PATH.exists():
        raise FileNotFoundError(f"Contract artifact missing at {CONTRACT_JSON_PATH}")
    with open(CONTRACT_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def deploy_contract(rpc_url: str = "http://127.0.0.1:8545") -> Dict[str, Any]:
    """Deploys SessionAuditLedger.sol to the running Anvil EVM node."""
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to EVM RPC node at {rpc_url}")

    deployer = w3.eth.accounts[0]
    artifact = load_contract_artifact()
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]
    if not bytecode.startswith("0x"):
        bytecode = "0x" + bytecode

    contract_factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = contract_factory.constructor().transact({"from": deployer})
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    contract_address = tx_receipt.contractAddress
    return {
        "contract_address": contract_address,
        "deployer": deployer,
        "abi": abi,
        "bytecode": bytecode,
        "deployment_tx": tx_receipt.transactionHash.hex(),
        "block_number": tx_receipt.blockNumber,
        "gas_used": tx_receipt.gasUsed
    }


def record_session_logout(
    username: str,
    session_id: str,
    entry_time_str: str,
    exit_time_str: str,
    changes_list: List[Dict[str, Any]],
    user_id: Optional[str] = None,
    contract_address: Optional[str] = None,
    rpc_url: str = "http://127.0.0.1:8545"
) -> Dict[str, Any]:
    """
    Registers a completed user session and all modifications made
    into the SessionAuditLedger smart contract on Anvil.
    """
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Anvil EVM node on {rpc_url} is not connected.")

    artifact = load_contract_artifact()
    abi = artifact["abi"]

    # Deploy contract if address is not specified or contract does not exist
    deployer = w3.eth.accounts[0]
    if not contract_address:
        deployment = deploy_contract(rpc_url)
        contract_address = deployment["contract_address"]

    contract = w3.eth.contract(address=contract_address, abi=abi)

    # Convert timestamps to unix seconds
    def to_unix(time_str: str) -> int:
        try:
            dt = datetime.fromisoformat(time_str)
            return int(dt.timestamp())
        except Exception:
            return int(time.time())

    entry_ts = to_unix(entry_time_str)
    exit_ts = to_unix(exit_time_str)

    changes_json = json.dumps(changes_list, indent=2)
    changes_hash = "0x" + hashlib.sha256(changes_json.encode()).hexdigest()
    uid = user_id or f"usr_{username}"

    # Call recordSessionLogout
    tx_hash = contract.functions.recordSessionLogout(
        uid,
        username,
        session_id,
        entry_ts,
        exit_ts,
        len(changes_list),
        changes_hash,
        changes_json
    ).transact({"from": deployer})

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    # Verify on-chain data
    on_chain_session = contract.functions.getSession(session_id).call()

    return {
        "status": "COMMITTED_ON_CHAIN",
        "contract_address": contract_address,
        "tx_hash": receipt.transactionHash.hex(),
        "block_number": receipt.blockNumber,
        "gas_used": receipt.gasUsed,
        "deployer_address": deployer,
        "changes_count": len(changes_list),
        "changes_hash": changes_hash,
        "on_chain_entry_time": on_chain_session[3],
        "on_chain_exit_time": on_chain_session[4],
        "abi_json": json.dumps(abi)
    }
