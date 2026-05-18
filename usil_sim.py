"""
usil_sim.py — USIL Transaction Simulation on Kaspa
Simulates Ghost → Shadow → Live settlement
using real Kaspa blockchain data as host transactions
"""
import requests, hashlib, json, time, uuid
from datetime import datetime
from pathlib import Path

KASPA_API = "https://api.kaspa.org"
SOMPI_PER_KAS = 1e8
USIL_BYTES = 512
MIN_FEERATE = 100  # post-Toccata

class USILCommitment:
    """Simulated USIL Ghost → Shadow → Live commitment"""
    
    def __init__(self, commitment_type, data, amount_kas=0.0):
        self.id = uuid.uuid4().hex[:16]
        self.type = commitment_type
        self.data = data
        self.amount_kas = amount_kas
        self.created_at = datetime.now().isoformat()
        
        # Ghost phase — superposition
        self.ghost_hash = hashlib.sha256(
            f"{self.id}{data}{self.created_at}".encode()
        ).hexdigest()
        
        self.phase = "GHOST"
        self.host_tx = None
        self.shadow_proof = None
        self.settled = False
        self.gas_paid_sompi = 0

    def shadow(self, host_tx_id, block_hash):
        """Shadow phase — entangle with host transaction"""
        self.phase = "SHADOW"
        self.host_tx = host_tx_id
        self.shadow_proof = hashlib.sha256(
            f"{self.ghost_hash}{host_tx_id}{block_hash}".encode()
        ).hexdigest()
        
        # Calculate gas owed (split fee)
        self.gas_paid_sompi = int(USIL_BYTES * MIN_FEERATE)
        return self.shadow_proof

    def live(self):
        """Live phase — collapse superposition, settle"""
        self.phase = "LIVE"
        self.settled = True
        self.settled_at = datetime.now().isoformat()
        
        # Final Merkle root
        self.merkle_root = hashlib.sha256(
            f"{self.shadow_proof}{self.settled_at}".encode()
        ).hexdigest()
        return self.merkle_root

    def summary(self):
        return {
            "id": self.id,
            "type": self.type,
            "phase": self.phase,
            "ghost_hash": self.ghost_hash[:16] + "...",
            "host_tx": self.host_tx[:16] + "..." if self.host_tx else None,
            "shadow_proof": self.shadow_proof[:16] + "..." if self.shadow_proof else None,
            "merkle_root": self.merkle_root[:16] + "..." if self.settled else None,
            "gas_paid_kas": round(self.gas_paid_sompi / SOMPI_PER_KAS, 8),
            "standalone_kas": 0.5,
            "savings_kas": round(0.5 - self.gas_paid_sompi/SOMPI_PER_KAS, 8),
            "settled": self.settled,
        }

def run_usil_simulation():
    print(f"\n  USIL TRANSACTION SIMULATION")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ─────────────────────────────────────")

    # Create sample USIL commitments
    # These represent real GIDLdata operations
    commitments = [
        USILCommitment("C.I_REPORT",
            "Pothole reported MLK+5th Chicago", 0.0),
        USILCommitment("WRAITH_EVIDENCE",
            "WR-ABC123 phishing domain merkle", 0.0),
        USILCommitment("CID_BRIDGE",
            "Rider pays USDC driver gets KAS", 1.50),
        USILCommitment("CODEX_JOB",
            "Zipcryption benchmark completed", 0.10),
        USILCommitment("GIDL_DATAPOINT",
            "FRED economic indicator batch 8432pts", 0.0),
    ]

    print(f"\n  [1/3] GHOST PHASE — {len(commitments)} commitments in superposition")
    for c in commitments:
        print(f"  ◌ {c.type:<20} ghost: {c.ghost_hash[:24]}...")

    # Pull real Kaspa block for host transactions
    print(f"\n  [2/3] SHADOW PHASE — attaching to real Kaspa txs")
    dag = requests.get(f"{KASPA_API}/info/blockdag", timeout=15).json()
    tip = dag["tipHashes"][0]
    block = requests.get(
        f"{KASPA_API}/blocks/{tip}?includeTransactions=true",
        timeout=15
    ).json()
    txs = block.get("transactions", [])

    print(f"  Real block: {tip[:24]}...")
    print(f"  Available host txs: {len(txs)}")

    # Attach each commitment to a real tx
    total_gas = 0
    for i, commitment in enumerate(commitments):
        if i < len(txs):
            tx = txs[i]
            tx_id = tx.get("verboseData", {}).get("transactionId", uuid.uuid4().hex)
            proof = commitment.shadow(tx_id, tip)
            total_gas += commitment.gas_paid_sompi
            print(f"  ⊕ {commitment.type:<20} → tx:{tx_id[:16]}... proof:{proof[:16]}...")
        else:
            print(f"  ⚠ {commitment.type:<20} → no host tx, queuing for next block")

    # Settle all
    print(f"\n  [3/3] LIVE PHASE — collapsing superposition")
    total_savings = 0
    for c in commitments:
        if c.phase == "SHADOW":
            merkle = c.live()
            savings = 0.5 - c.gas_paid_sompi/SOMPI_PER_KAS
            total_savings += savings
            print(f"  ✅ {c.type:<20} merkle:{merkle[:16]}... saved:{savings:.6f} KAS")

    # Summary
    standalone_total = len(commitments) * 0.5
    parasitic_total = total_gas / SOMPI_PER_KAS
    
    print(f"\n  ─────────────────────────────────────")
    print(f"  SETTLEMENT SUMMARY:")
    print(f"  Commitments:      {len(commitments)}")
    print(f"  Settled:          {sum(1 for c in commitments if c.settled)}")
    print(f"  Standalone cost:  {standalone_total:.4f} KAS")
    print(f"  Parasitic cost:   {parasitic_total:.8f} KAS")
    print(f"  Total savings:    {total_savings:.6f} KAS")
    print(f"  Efficiency:       {(total_savings/standalone_total*100):.1f}%")

    # Show full commitment details
    print(f"\n  COMMITMENT DETAILS:")
    for c in commitments:
        s = c.summary()
        print(f"\n  [{s['type']}]")
        print(f"    ID:       {s['id']}")
        print(f"    Phase:    {s['phase']}")
        print(f"    Ghost:    {s['ghost_hash']}")
        print(f"    Host tx:  {s['host_tx']}")
        print(f"    Shadow:   {s['shadow_proof']}")
        print(f"    Merkle:   {s['merkle_root']}")
        print(f"    Gas paid: {s['gas_paid_kas']} KAS")
        print(f"    Savings:  {s['savings_kas']} KAS")
        print(f"    Settled:  {s['settled']}")

    print(f"\n  ✅ USIL simulation complete")
    return commitments

if __name__ == "__main__":
    commitments = run_usil_simulation()
