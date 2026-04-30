"""
usil/commitment.py — USIL SHA-256 Commitment Engine

The core invention: standardized cross-chain state serialization.

commitment := VERSION (1 byte)
           || SHA256( chain_id (4 bytes, big-endian)
                   || block_height (8 bytes, big-endian)
                   || state_root (32 bytes) )

Properties: deterministic, chain-agnostic, compact (33 bytes), non-repudiable.
"""

import hashlib
import struct
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


VERSION = b'\x01'  # Commitment format version


class CommitmentStatus(Enum):
    GHOST    = "GHOST"     # Simulated — no network calls
    SHADOW   = "SHADOW"    # Built, not broadcast — challenge window open
    VERIFIED = "VERIFIED"  # Proof verified on-chain
    LIVE     = "LIVE"      # Settlement complete — synthetic minted
    EXPIRED  = "EXPIRED"   # Past 2,016-block expiry window
    INVALID  = "INVALID"   # Fraud detected or proof failed


class TrustMode(Enum):
    ORACLE     = "ORACLE"      # Validator-based, fast
    OPTIMISTIC = "OPTIMISTIC"  # Challenge window
    TRUSTLESS  = "TRUSTLESS"   # SPV or zk-proof required


@dataclass
class USILCommitment:
    commitment_id:   str
    chain_id:        int
    block_height:    int
    state_root:      str          # Merkle root from source block
    commitment_hash: str          # The actual SHA-256 output
    full_commitment: str          # VERSION || commitment_hash
    status:          CommitmentStatus
    trust_mode:      TrustMode
    created_at:      float
    verified_at:     Optional[float] = None
    settled_at:      Optional[float] = None
    expires_at:      Optional[float] = None  # 2,016 blocks ~ 2 weeks
    shadow_opens_at: Optional[float] = None
    shadow_clears_at:Optional[float] = None
    proof_type:      Optional[str]  = None
    kaspa_tx_hash:   Optional[str]  = None
    mint_amount:     Optional[float]= None
    mint_asset:      Optional[str]  = None
    error:           Optional[str]  = None
    attack_flag:     Optional[str]  = None  # Set by attack simulator


def build_commitment(
    chain_id:     int,
    block_height: int,
    state_root:   str,
    trust_mode:   TrustMode = TrustMode.TRUSTLESS,
) -> USILCommitment:
    """
    Generate a USIL commitment from source chain state.
    This is the core cryptographic operation of the protocol.
    """
    # Pack fields into bytes — deterministic encoding
    chain_id_bytes    = struct.pack(">I", chain_id)       # 4 bytes big-endian
    height_bytes      = struct.pack(">Q", block_height)   # 8 bytes big-endian
    state_root_bytes  = bytes.fromhex(state_root)         # 32 bytes

    # Concatenate: chain_id || block_height || state_root
    preimage = chain_id_bytes + height_bytes + state_root_bytes

    # SHA-256 commitment
    commitment_hash = hashlib.sha256(preimage).hexdigest()

    # Versioned full commitment: 0x01 || commitment_hash
    full_commitment = VERSION.hex() + commitment_hash

    now = time.time()

    # Simulate Kaspa tx hash for published commitment
    kaspa_seed = f"kas_tx_{commitment_hash[:16]}".encode()
    kaspa_tx   = hashlib.sha256(kaspa_seed).hexdigest()

    return USILCommitment(
        commitment_id    = str(uuid.uuid4())[:8].upper(),
        chain_id         = chain_id,
        block_height     = block_height,
        state_root       = state_root,
        commitment_hash  = commitment_hash,
        full_commitment  = full_commitment,
        status           = CommitmentStatus.GHOST,
        trust_mode       = trust_mode,
        created_at       = now,
        expires_at       = now + (2016 * 600),  # 2,016 blocks × 10 min
        shadow_opens_at  = now + 2.0,            # 2s for demo (real: confirmations)
        shadow_clears_at = now + 6.0,            # 6s challenge window (real: 7 days)
        kaspa_tx_hash    = kaspa_tx,
    )


def build_tampered_commitment(
    chain_id:     int,
    block_height: int,
    state_root:   str,
    fake_root:    str,
    trust_mode:   TrustMode = TrustMode.ORACLE,
) -> USILCommitment:
    """
    Build a commitment with a TAMPERED state_root.
    Used by the attack simulator to test T1 (invalid state root submission).
    """
    c = build_commitment(chain_id, block_height, fake_root, trust_mode)
    c.attack_flag = f"TAMPERED_ROOT: real={state_root[:12]}... fake={fake_root[:12]}..."
    return c


def commitment_preimage_hex(chain_id: int, block_height: int, state_root: str) -> str:
    """Return the hex-encoded preimage for audit/display purposes."""
    chain_id_bytes   = struct.pack(">I", chain_id)
    height_bytes     = struct.pack(">Q", block_height)
    state_root_bytes = bytes.fromhex(state_root)
    preimage = chain_id_bytes + height_bytes + state_root_bytes
    return preimage.hex()


def is_expired(commitment: USILCommitment) -> bool:
    return time.time() > commitment.expires_at


def is_stale_for_mint(commitment: USILCommitment) -> bool:
    """Commitments older than 2,016 blocks cannot mint."""
    return is_expired(commitment)
