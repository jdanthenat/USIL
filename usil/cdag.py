"""
usil/cdag.py — CDAG Settlement Layer Simulation

Simulates Kaspa's Computational DAG (CDAG) for pre-Toccata development.
Post-Toccata: replace with actual Kaspa vProg SDK calls.

The CDAG tracks:
  - Execution commitments (per vProg submission)
  - Blue score finality anchors
  - Dependency chains between commitments
  - Resource usage per commitment

USIL commitments form a sub-DAG within the global CDAG.
Every commitment is traceable to a Kaspa blue score.
"""

import hashlib
import time
import sqlite3
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "usil.db")

# CDAG constants
FINALITY_THRESHOLD  = 100    # blue score units (~10 seconds at 10 BPS)
BLUE_SCORE_PER_SEC  = 10     # Kaspa runs at 10 BPS
BASE_BLUE_SCORE     = 50_000_000  # approximate current Kaspa blue score

# Simulated vProg identity
USIL_VPROG_ID = hashlib.sha256(b"USIL_VPROG_V1").hexdigest()[:16].upper()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_cdag_tables():
    """Add CDAG tables to the existing USIL database."""
    conn = get_conn()
    c = conn.cursor()

    # CDAG execution commitments
    c.execute("""
        CREATE TABLE IF NOT EXISTS cdag_commitments (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            usil_commitment_id   TEXT NOT NULL,
            program_id           TEXT NOT NULL DEFAULT 'USIL_VPROG',
            blue_score_ref       INTEGER NOT NULL,
            blue_score_final     INTEGER,
            dependency_hash      TEXT,
            groth16_proof_hash   TEXT NOT NULL,
            resource_compute     INTEGER DEFAULT 0,
            resource_storage     INTEGER DEFAULT 0,
            submitted_at         REAL NOT NULL,
            finalized_at         REAL,
            status               TEXT DEFAULT 'PENDING',
            zk_verified          INTEGER DEFAULT 0,
            chain_id             INTEGER,
            block_height         INTEGER
        )
    """)

    # CDAG MintLedger — L1 consensus level (replaces SQLite post-Toccata)
    c.execute("""
        CREATE TABLE IF NOT EXISTS cdag_mint_ledger (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            commitment_id     TEXT NOT NULL,
            utxo_id           TEXT NOT NULL,
            blue_score_mint   INTEGER NOT NULL,
            mint_asset        TEXT NOT NULL,
            mint_amount       REAL NOT NULL,
            kaspa_address     TEXT NOT NULL,
            covenant_tx_hash  TEXT NOT NULL,
            minted_at         REAL NOT NULL,
            UNIQUE(commitment_id, utxo_id)
        )
    """)

    conn.commit()
    conn.close()


def current_blue_score() -> int:
    """Simulate current Kaspa blue score (increments in real time)."""
    elapsed_secs = time.time() - 1_746_000_000
    return BASE_BLUE_SCORE + int(elapsed_secs * BLUE_SCORE_PER_SEC)


def is_final(blue_score_ref: int) -> bool:
    """Check if a CDAG entry has reached Kaspa finality."""
    return current_blue_score() >= blue_score_ref + FINALITY_THRESHOLD


def simulate_groth16_verify(commitment_hash: str, chain_id: int,
                             block_height: int) -> tuple[bool, str]:
    """
    Simulate Groth16 L1 opcode verification.
    Post-Toccata: replace with actual kaspa_node.groth16_verify() call.

    Returns (is_valid, proof_hash).
    """
    # Simulate proof generation
    proof_input = f"groth16_{commitment_hash}_{chain_id}_{block_height}".encode()
    proof_hash  = hashlib.sha256(proof_input).hexdigest()

    # In simulation: all honest commitments pass. Tampered ones fail.
    # The attack simulator sets attack_flag to test failure paths.
    is_valid = True  # Real: groth16_verify(circuit, proof, public_inputs)

    return is_valid, proof_hash


def submit_to_cdag(
    usil_commitment_id: str,
    commitment_hash:    str,
    chain_id:           int,
    block_height:       int,
    prev_commitment_id: Optional[str] = None,
    is_tampered:        bool = False,
) -> dict:
    """
    Submit a USIL commitment to the simulated CDAG.
    Post-Toccata: this becomes a vProg submission to Kaspa L1.

    Returns CDAG entry dict with blue_score_ref, proof_hash, status.
    """
    blue_ref = current_blue_score()

    # Groth16 verification (simulated L1 opcode)
    zk_ok, proof_hash = simulate_groth16_verify(
        commitment_hash, chain_id, block_height
    )

    # Tampered commitments fail ZK verification
    if is_tampered:
        zk_ok = False
        proof_hash = "INVALID_" + proof_hash[:24]

    # Compute dependency hash (chain continuity)
    dep_input = f"{prev_commitment_id or 'genesis'}_{commitment_hash}".encode()
    dep_hash  = hashlib.sha256(dep_input).hexdigest()

    # Resource accounting
    resource_compute = len(commitment_hash) * 100   # simulated compute units
    resource_storage = 33 + 200 + 64               # commitment + proof + exec_commit

    # Covenant tx hash (SilverScript mint covenant)
    covenant_tx = hashlib.sha256(
        f"covenant_{commitment_hash}_{blue_ref}".encode()
    ).hexdigest()

    status = "VERIFIED" if zk_ok else "REJECTED"

    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO cdag_commitments
            (usil_commitment_id, program_id, blue_score_ref, dependency_hash,
             groth16_proof_hash, resource_compute, resource_storage,
             submitted_at, status, zk_verified, chain_id, block_height)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            usil_commitment_id, USIL_VPROG_ID, blue_ref, dep_hash,
            proof_hash, resource_compute, resource_storage,
            time.time(), status, 1 if zk_ok else 0,
            chain_id, block_height
        ))
        conn.commit()
    except Exception as e:
        pass
    finally:
        conn.close()

    return {
        "usil_commitment_id": usil_commitment_id,
        "blue_score_ref":     blue_ref,
        "blue_score_final":   blue_ref + FINALITY_THRESHOLD,
        "groth16_proof_hash": proof_hash,
        "dependency_hash":    dep_hash,
        "zk_verified":        zk_ok,
        "status":             status,
        "covenant_tx":        covenant_tx,
        "resource_compute":   resource_compute,
        "resource_storage":   resource_storage,
        "finality_eta_secs":  FINALITY_THRESHOLD / BLUE_SCORE_PER_SEC,
        "vprog_id":           USIL_VPROG_ID,
    }


def finalize_cdag_entry(usil_commitment_id: str) -> bool:
    """Mark a CDAG entry as finalized once blue score threshold is reached."""
    conn = get_conn()
    row = conn.execute(
        "SELECT blue_score_ref, status FROM cdag_commitments WHERE usil_commitment_id=?",
        (usil_commitment_id,)
    ).fetchone()

    if not row or row["status"] != "VERIFIED":
        conn.close()
        return False

    if is_final(row["blue_score_ref"]):
        conn.execute("""
            UPDATE cdag_commitments
            SET status='FINAL', blue_score_final=?, finalized_at=?
            WHERE usil_commitment_id=?
        """, (current_blue_score(), time.time(), usil_commitment_id))
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False


def cdag_mint(
    commitment_id:  str,
    utxo_id:        str,
    mint_asset:     str,
    mint_amount:    float,
    kaspa_address:  str,
    blue_score_ref: int,
) -> tuple[bool, str]:
    """
    SilverScript covenant mint — CDAG level.
    Post-Toccata: actual covenant execution on Kaspa L1.
    """
    conn = get_conn()

    # Check CDAG finality
    if not is_final(blue_score_ref):
        remaining = (blue_score_ref + FINALITY_THRESHOLD - current_blue_score()) / BLUE_SCORE_PER_SEC
        conn.close()
        return False, f"NOT_FINAL — {remaining:.1f}s until Kaspa finality"

    # Check MintLedger (CDAG state — consensus enforced)
    existing = conn.execute(
        "SELECT id FROM cdag_mint_ledger WHERE commitment_id=? AND utxo_id=?",
        (commitment_id, utxo_id)
    ).fetchone()

    if existing:
        conn.close()
        return False, "CDAG_ALREADY_MINTED — consensus-level double-mint protection"

    covenant_tx = hashlib.sha256(
        f"silverscript_mint_{commitment_id}_{utxo_id}_{blue_score_ref}".encode()
    ).hexdigest()

    try:
        conn.execute("""
            INSERT INTO cdag_mint_ledger
            (commitment_id, utxo_id, blue_score_mint, mint_asset,
             mint_amount, kaspa_address, covenant_tx_hash, minted_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (commitment_id, utxo_id, current_blue_score(), mint_asset,
              mint_amount, kaspa_address, covenant_tx, time.time()))
        conn.commit()
        conn.close()
        return True, (f"CDAG_MINTED: {mint_amount} {mint_asset} → {kaspa_address} "
                     f"| covenant_tx={covenant_tx[:16]}... "
                     f"| blue_score={current_blue_score():,}")
    except sqlite3.IntegrityError:
        conn.close()
        return False, "CDAG_ALREADY_MINTED (race condition)"


def get_cdag_stats() -> dict:
    conn = get_conn()
    try:
        total    = conn.execute("SELECT COUNT(*) FROM cdag_commitments").fetchone()[0]
        verified = conn.execute(
            "SELECT COUNT(*) FROM cdag_commitments WHERE zk_verified=1"
        ).fetchone()[0]
        final    = conn.execute(
            "SELECT COUNT(*) FROM cdag_commitments WHERE status='FINAL'"
        ).fetchone()[0]
        mints    = conn.execute("SELECT COUNT(*) FROM cdag_mint_ledger").fetchone()[0]
        avg_bs   = conn.execute(
            "SELECT AVG(blue_score_ref) FROM cdag_commitments"
        ).fetchone()[0]
        conn.close()
        return {
            "total_cdag_entries": total,
            "zk_verified":        verified,
            "finalized":          final,
            "cdag_mints":         mints,
            "avg_blue_score":     int(avg_bs) if avg_bs else 0,
            "current_blue_score": current_blue_score(),
            "vprog_id":           USIL_VPROG_ID,
        }
    except Exception:
        conn.close()
        return {"total_cdag_entries": 0, "current_blue_score": current_blue_score()}


def get_cdag_entries(limit: int = 10) -> list:
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM cdag_commitments ORDER BY submitted_at DESC LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []
