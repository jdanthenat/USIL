"""
usil/ledger.py — USIL SQLite MintLedger

Append-only record of every mint and commitment.
Enforces: no double-mint, no stale commitment reuse.

Mirrors the Kasplex MintLedger smart contract:
    mapping(commitment_id => mapping(utxo_id => minted)) MintLedger;
"""

import sqlite3
import time
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "usil.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize all USIL ledger tables."""
    conn = get_conn()
    c = conn.cursor()

    # Commitment registry — every commitment ever submitted
    c.execute("""
        CREATE TABLE IF NOT EXISTS commitment_registry (
            commitment_id    TEXT PRIMARY KEY,
            chain_id         INTEGER NOT NULL,
            block_height     INTEGER NOT NULL,
            state_root       TEXT NOT NULL,
            commitment_hash  TEXT NOT NULL UNIQUE,
            full_commitment  TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'GHOST',
            trust_mode       TEXT NOT NULL,
            created_at       REAL NOT NULL,
            verified_at      REAL,
            settled_at       REAL,
            expires_at       REAL,
            proof_type       TEXT,
            kaspa_tx_hash    TEXT,
            attack_flag      TEXT
        )
    """)

    # MintLedger — append-only, commitment_id + utxo_id pair
    c.execute("""
        CREATE TABLE IF NOT EXISTS mint_ledger (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            commitment_id   TEXT NOT NULL,
            utxo_id         TEXT NOT NULL,
            mint_asset      TEXT NOT NULL,
            mint_amount     REAL NOT NULL,
            kaspa_address   TEXT NOT NULL,
            minted_at       REAL NOT NULL,
            kaspa_tx_hash   TEXT NOT NULL,
            UNIQUE(commitment_id, utxo_id)
        )
    """)

    # Attack log — every attack attempt and outcome
    c.execute("""
        CREATE TABLE IF NOT EXISTS attack_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            attack_type     TEXT NOT NULL,
            description     TEXT NOT NULL,
            commitment_id   TEXT,
            utxo_id         TEXT,
            attack_at       REAL NOT NULL,
            caught          INTEGER NOT NULL DEFAULT 1,
            catch_reason    TEXT
        )
    """)

    # Pipeline events — every state transition
    c.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            commitment_id   TEXT NOT NULL,
            from_status     TEXT,
            to_status       TEXT NOT NULL,
            event_at        REAL NOT NULL,
            note            TEXT
        )
    """)

    conn.commit()
    conn.close()


def register_commitment(c) -> bool:
    """Insert a new commitment into the registry. Returns False if duplicate."""
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO commitment_registry
            (commitment_id, chain_id, block_height, state_root,
             commitment_hash, full_commitment, status, trust_mode,
             created_at, expires_at, kaspa_tx_hash, attack_flag)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            c.commitment_id, c.chain_id, c.block_height, c.state_root,
            c.commitment_hash, c.full_commitment, c.status.value, c.trust_mode.value,
            c.created_at, c.expires_at, c.kaspa_tx_hash, c.attack_flag
        ))
        conn.commit()
        log_event(c.commitment_id, None, c.status.value, "Commitment registered")
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_status(commitment_id: str, new_status: str, note: str = ""):
    conn = get_conn()
    old = conn.execute(
        "SELECT status FROM commitment_registry WHERE commitment_id=?",
        (commitment_id,)
    ).fetchone()
    old_status = old["status"] if old else None

    now = time.time()
    updates = {"status": new_status}
    if new_status == "VERIFIED":
        updates["verified_at"] = now
    elif new_status == "LIVE":
        updates["settled_at"] = now

    set_clause = ", ".join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE commitment_registry SET {set_clause} WHERE commitment_id=?",
        list(updates.values()) + [commitment_id]
    )
    conn.commit()
    conn.close()
    log_event(commitment_id, old_status, new_status, note)


def mint(
    commitment_id: str,
    utxo_id:       str,
    mint_asset:    str,
    mint_amount:   float,
    kaspa_address: str,
    kaspa_tx_hash: str,
) -> tuple[bool, str]:
    """
    Attempt to mint a synthetic asset.
    Returns (success, reason).
    Enforces: no double-mint (ALREADY_MINTED).
    """
    conn = get_conn()

    # Check commitment exists and is VERIFIED
    row = conn.execute(
        "SELECT status, expires_at FROM commitment_registry WHERE commitment_id=?",
        (commitment_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False, "COMMITMENT_NOT_FOUND"

    if row["status"] not in ("VERIFIED", "LIVE"):
        conn.close()
        return False, f"COMMITMENT_NOT_VERIFIED (status={row['status']})"

    if time.time() > row["expires_at"]:
        conn.close()
        return False, "COMMITMENT_EXPIRED — stale commitment rejected (T5 protection)"

    # THE CRITICAL CHECK: double-mint prevention
    existing = conn.execute(
        "SELECT id FROM mint_ledger WHERE commitment_id=? AND utxo_id=?",
        (commitment_id, utxo_id)
    ).fetchone()

    if existing:
        conn.close()
        log_attack("T3_DOUBLE_MINT",
                   f"Double mint attempt: commitment={commitment_id} utxo={utxo_id}",
                   commitment_id, utxo_id,
                   catch_reason="ALREADY_MINTED — MintLedger entry found")
        return False, "ALREADY_MINTED — double-mint attempt caught (T3 protection)"

    # All checks passed — record the mint
    try:
        conn.execute("""
            INSERT INTO mint_ledger
            (commitment_id, utxo_id, mint_asset, mint_amount,
             kaspa_address, minted_at, kaspa_tx_hash)
            VALUES (?,?,?,?,?,?,?)
        """, (commitment_id, utxo_id, mint_asset, mint_amount,
              kaspa_address, time.time(), kaspa_tx_hash))
        conn.commit()
        conn.close()
        return True, f"MINTED: {mint_amount} {mint_asset} → {kaspa_address}"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "ALREADY_MINTED (race condition)"


def log_attack(
    attack_type:  str,
    description:  str,
    commitment_id:Optional[str] = None,
    utxo_id:      Optional[str] = None,
    caught:       bool = True,
    catch_reason: Optional[str] = None,
):
    conn = get_conn()
    conn.execute("""
        INSERT INTO attack_log
        (attack_type, description, commitment_id, utxo_id, attack_at, caught, catch_reason)
        VALUES (?,?,?,?,?,?,?)
    """, (attack_type, description, commitment_id, utxo_id,
          time.time(), 1 if caught else 0, catch_reason))
    conn.commit()
    conn.close()


def log_event(commitment_id: str, from_status: Optional[str],
              to_status: str, note: str = ""):
    conn = get_conn()
    conn.execute("""
        INSERT INTO pipeline_events (commitment_id, from_status, to_status, event_at, note)
        VALUES (?,?,?,?,?)
    """, (commitment_id, from_status, to_status, time.time(), note))
    conn.commit()
    conn.close()


def get_all_commitments(limit: int = 20) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM commitment_registry ORDER BY created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_mints(limit: int = 20) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM mint_ledger ORDER BY minted_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attack_log(limit: int = 20) -> list:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM attack_log ORDER BY attack_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    conn = get_conn()
    total   = conn.execute("SELECT COUNT(*) FROM commitment_registry").fetchone()[0]
    by_status = dict(conn.execute(
        "SELECT status, COUNT(*) FROM commitment_registry GROUP BY status"
    ).fetchall())
    total_mints = conn.execute("SELECT COUNT(*) FROM mint_ledger").fetchone()[0]
    total_attacks = conn.execute("SELECT COUNT(*) FROM attack_log").fetchone()[0]
    caught = conn.execute(
        "SELECT COUNT(*) FROM attack_log WHERE caught=1"
    ).fetchone()[0]
    conn.close()
    return {
        "total_commitments": total,
        "by_status":         by_status,
        "total_mints":       total_mints,
        "total_attacks":     total_attacks,
        "attacks_caught":    caught,
    }
