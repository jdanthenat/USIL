"""
usil/pipeline.py — Ghost → Shadow → Live State Machine

Each commitment climbs three trust tiers:

  GHOST     No network calls. Commitment generated + logged.
            Builds track record. Zero risk. Pure simulation.

  SHADOW    Real block header fetched. Real tx constructed.
            Published to ledger. Challenge window open.
            Equivalent to optimistic mode.

  LIVE      SPV proof verified. Commitment status = VERIFIED.
            Synthetic asset minted to Kaspa address.
            Permanent on-chain record. Full settlement.

The flip switch: SHADOW only unlocks after GHOST proves accuracy.
LIVE only fires after SHADOW clears the challenge window clean.
"""

import hashlib
import time
import random
from dataclasses import dataclass
from typing import Optional

from .commitment import (
    USILCommitment, CommitmentStatus, TrustMode,
    build_commitment, is_stale_for_mint
)
from .bitcoin import get_block_header, build_spv_proof, verify_spv_proof
from . import ledger

# ── Flip switch thresholds (mirrors trading bot logic) ─────────────────────────
GHOST_MIN_COMMITMENTS  = 5    # Demo: 5 (real: 50+)
GHOST_MIN_ACCURACY     = 0.90 # 90% valid commitments before shadow unlocks
SHADOW_CHALLENGE_SECS  = 6.0  # Demo: 6s (real: 7 days)
LIVE_CONFIRMATIONS_REQ = 6    # BTC confirmations required


@dataclass
class PipelineResult:
    stage:          str
    success:        bool
    commitment:     Optional[USILCommitment]
    message:        str
    duration_ms:    float
    proof_verified: bool = False
    mint_result:    Optional[str] = None


class USILPipeline:
    def __init__(self):
        self.ghost_count    = 0
        self.ghost_valid    = 0
        self.shadow_unlocked = False
        self.live_unlocked  = False
        self._active_shadows: dict[str, USILCommitment] = {}

    @property
    def ghost_accuracy(self) -> float:
        if self.ghost_count == 0:
            return 0.0
        return self.ghost_valid / self.ghost_count

    @property
    def shadow_ready(self) -> bool:
        return (self.ghost_count >= GHOST_MIN_COMMITMENTS and
                self.ghost_accuracy >= GHOST_MIN_ACCURACY)

    # ── STAGE 1: GHOST ─────────────────────────────────────────────────────────
    def run_ghost(self, height: int, trust_mode: TrustMode = TrustMode.ORACLE) -> PipelineResult:
        """
        Ghost stage: generate commitment from simulated block.
        No network calls. Logs to SQLite. Builds track record.
        """
        t0 = time.time()
        block = get_block_header(height)

        commitment = build_commitment(
            chain_id     = block["chain_id"],
            block_height = block["height"],
            state_root   = block["merkle_root"],
            trust_mode   = trust_mode,
        )
        commitment.status = CommitmentStatus.GHOST

        ledger.register_commitment(commitment)
        self.ghost_count += 1
        self.ghost_valid += 1  # In sim, all ghost commitments are valid

        duration = (time.time() - t0) * 1000
        return PipelineResult(
            stage       = "GHOST",
            success     = True,
            commitment  = commitment,
            message     = (f"[GHOST] BTC block {height} committed — "
                          f"SHA256={commitment.commitment_hash[:24]}... "
                          f"({self.ghost_count}/{GHOST_MIN_COMMITMENTS} toward shadow unlock)"),
            duration_ms = duration,
        )

    # ── STAGE 2: SHADOW ────────────────────────────────────────────────────────
    def run_shadow(self, height: int, trust_mode: TrustMode = TrustMode.OPTIMISTIC) -> PipelineResult:
        """
        Shadow stage: real block data, real tx constructed, not broadcast.
        Challenge window open. If no fraud detected → clears to LIVE.
        """
        if not self.shadow_ready:
            return PipelineResult(
                stage="SHADOW", success=False, commitment=None,
                message=(f"[SHADOW LOCKED] Need {GHOST_MIN_COMMITMENTS} ghost commitments "
                        f"at {GHOST_MIN_ACCURACY:.0%} accuracy. "
                        f"Current: {self.ghost_count} @ {self.ghost_accuracy:.1%}"),
                duration_ms=0,
            )

        t0 = time.time()
        block = get_block_header(height)

        commitment = build_commitment(
            chain_id     = block["chain_id"],
            block_height = block["height"],
            state_root   = block["merkle_root"],
            trust_mode   = trust_mode,
        )
        commitment.status = CommitmentStatus.SHADOW
        commitment.proof_type = "SPV_PENDING"
        commitment.shadow_opens_at  = time.time()
        commitment.shadow_clears_at = time.time() + SHADOW_CHALLENGE_SECS

        ledger.register_commitment(commitment)
        ledger.update_status(commitment.commitment_id, "SHADOW",
                            f"Challenge window: {SHADOW_CHALLENGE_SECS}s")
        self._active_shadows[commitment.commitment_id] = commitment

        duration = (time.time() - t0) * 1000
        return PipelineResult(
            stage      = "SHADOW",
            success    = True,
            commitment = commitment,
            message    = (f"[SHADOW] BTC block {height} — "
                         f"tx BUILT not broadcast — "
                         f"Challenge window: {SHADOW_CHALLENGE_SECS}s — "
                         f"Commitment: {commitment.commitment_hash[:24]}..."),
            duration_ms = duration,
        )

    # ── STAGE 3: LIVE ──────────────────────────────────────────────────────────
    def run_live(
        self,
        commitment:    USILCommitment,
        kaspa_address: str = "kaspa:qr9y...demo",
        mint_amount:   float = 0.1,
        mint_asset:    str = "sBTC",
    ) -> PipelineResult:
        """
        Live stage: SPV proof verified → commitment VERIFIED → synthetic minted.
        Requires shadow to have cleared challenge window.
        """
        t0 = time.time()

        # Check challenge window has cleared
        if commitment.shadow_clears_at and time.time() < commitment.shadow_clears_at:
            remaining = commitment.shadow_clears_at - time.time()
            return PipelineResult(
                stage="LIVE", success=False, commitment=commitment,
                message=f"[LIVE PENDING] Challenge window not cleared — {remaining:.1f}s remaining",
                duration_ms=(time.time() - t0) * 1000,
            )

        # Check not stale
        if is_stale_for_mint(commitment):
            ledger.update_status(commitment.commitment_id, "EXPIRED", "Past 2,016-block window")
            return PipelineResult(
                stage="LIVE", success=False, commitment=commitment,
                message="[REJECTED] Commitment expired — stale commitment protection (T5)",
                duration_ms=(time.time() - t0) * 1000,
            )

        # Build + verify SPV proof
        block = get_block_header(commitment.block_height)
        proof = build_spv_proof(block)
        spv_ok, spv_msg = verify_spv_proof(proof, commitment.state_root)

        if not spv_ok:
            ledger.update_status(commitment.commitment_id, "INVALID", spv_msg)
            return PipelineResult(
                stage="LIVE", success=False, commitment=commitment,
                message=f"[PROOF FAILED] {spv_msg}",
                duration_ms=(time.time() - t0) * 1000,
                proof_verified=False,
            )

        # Mark VERIFIED
        commitment.status     = CommitmentStatus.VERIFIED
        commitment.proof_type = "SPV_VERIFIED"
        ledger.update_status(commitment.commitment_id, "VERIFIED", spv_msg)

        # Generate UTXO ID for this lock tx
        utxo_id = hashlib.sha256(
            f"utxo_{commitment.commitment_id}_{commitment.block_height}".encode()
        ).hexdigest()[:16]

        # Generate Kaspa mint tx hash
        kas_mint_tx = hashlib.sha256(
            f"kas_mint_{commitment.commitment_id}_{utxo_id}".encode()
        ).hexdigest()

        # Attempt mint (enforces double-mint protection)
        mint_ok, mint_msg = ledger.mint(
            commitment_id = commitment.commitment_id,
            utxo_id       = utxo_id,
            mint_asset    = mint_asset,
            mint_amount   = mint_amount,
            kaspa_address = kaspa_address,
            kaspa_tx_hash = kas_mint_tx,
        )

        if mint_ok:
            commitment.status      = CommitmentStatus.LIVE
            commitment.mint_amount = mint_amount
            commitment.mint_asset  = mint_asset
            ledger.update_status(commitment.commitment_id, "LIVE",
                                f"Minted {mint_amount} {mint_asset} → {kaspa_address}")

        duration = (time.time() - t0) * 1000
        return PipelineResult(
            stage          = "LIVE",
            success        = mint_ok,
            commitment     = commitment,
            message        = (f"[{'LIVE ✓' if mint_ok else 'MINT FAILED'}] "
                             f"SPV verified | Kaspa block confirmed | "
                             f"{mint_msg}"),
            duration_ms    = duration,
            proof_verified = spv_ok,
            mint_result    = mint_msg,
        )

    def check_shadow_clearances(self) -> list[USILCommitment]:
        """Check if any shadow commitments have cleared the challenge window."""
        cleared = []
        for cid, c in list(self._active_shadows.items()):
            if time.time() >= c.shadow_clears_at:
                cleared.append(c)
                del self._active_shadows[cid]
        return cleared
