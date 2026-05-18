"""
parasitic_sim.py — Parasitic Transaction Simulation
Uses real Kaspa blockchain data to model USIL attachment efficiency
"""
import requests, json, time, hashlib
from datetime import datetime
from pathlib import Path

KASPA_API = "https://api.kaspa.org"

# USIL commitment size in bytes (typical)
USIL_COMMIT_BYTES = 512

def get_recent_blocks(limit=10):
    """Pull recent Kaspa blocks"""
    try:
        r = requests.get(f"{KASPA_API}/blocks?lowHash=&includeTransactions=true&limit={limit}", timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  Error: {e}")
    return []

def get_block_transactions(block_hash):
    """Get transactions for a specific block"""
    try:
        r = requests.get(f"{KASPA_API}/blocks/{block_hash}?includeTransactions=true", timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  Error: {e}")
    return {}

def get_fee_estimate():
    """Get current Kaspa fee estimate"""
    try:
        r = requests.get(f"{KASPA_API}/info/fee-estimate", timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {"priorityBucket": {"feerate": 100}}

def analyze_transaction(tx):
    """
    Analyze a transaction for parasitic attachment potential
    Returns opportunity score and estimated savings
    """
    if not tx:
        return None

    # Get payload size if present
    payload = tx.get("payload", "")
    payload_bytes = len(payload) // 2 if payload else 0

    # Mass = compute cost
    mass = tx.get("mass", 0) or tx.get("computeMass", 0)

    # Estimate available payload headroom
    # Kaspa max tx size ~250kb post-Toccata
    MAX_PAYLOAD = 250000
    available = MAX_PAYLOAD - payload_bytes - mass

    # Can we attach USIL commitment?
    can_attach = available >= USIL_COMMIT_BYTES

    # Gas savings calculation
    # Standalone STARK proof: ~0.5 KAS
    # Parasitic attachment: pay only for bytes added
    STANDALONE_COST_SOMPI = 500000000  # 0.5 KAS in sompi
    SOMPI_PER_GRAM = 100  # post-Toccata minimum

    if can_attach:
        parasitic_cost = USIL_COMMIT_BYTES * SOMPI_PER_GRAM
        savings_sompi = STANDALONE_COST_SOMPI - parasitic_cost
        savings_kas = savings_sompi / 1e8
        savings_pct = (savings_sompi / STANDALONE_COST_SOMPI) * 100
    else:
        parasitic_cost = 0
        savings_sompi = 0
        savings_kas = 0
        savings_pct = 0

    return {
        "tx_id": tx.get("verboseData", {}).get("transactionId", "unknown")[:16],
        "payload_bytes": payload_bytes,
        "available_bytes": max(0, available),
        "can_attach": can_attach,
        "parasitic_cost_sompi": parasitic_cost,
        "standalone_cost_sompi": STANDALONE_COST_SOMPI,
        "savings_sompi": savings_sompi,
        "savings_kas": round(savings_kas, 8),
        "savings_pct": round(savings_pct, 2),
    }

def run_simulation(blocks_to_analyze=5):
    print(f"\n  PARASITIC TRANSACTION SIMULATION")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ─────────────────────────────────────")

    # Get fee estimate
    fees = get_fee_estimate()
    feerate = fees.get("priorityBucket", {}).get("feerate", 100)
    print(f"\n  Current feerate: {feerate} sompi/gram")

    # Pull real block data
    print(f"\n  Pulling {blocks_to_analyze} recent blocks...")
    dag_info = requests.get(f"{KASPA_API}/info/blockdag", timeout=15).json()
    tip_hash = dag_info.get("tipHashes", [""])[0]

    print(f"  DAG tip: {tip_hash[:24]}...")
    print(f"  Total blocks: {dag_info.get('blockCount', 'unknown')}")

    # Get transactions from tip block
    print(f"\n  Analyzing transactions...")
    block_data = get_block_transactions(tip_hash)

    transactions = block_data.get("transactions", [])
    print(f"  Transactions in block: {len(transactions)}")

    # Analyze each transaction
    opportunities = []
    total_txs = 0
    attachable = 0

    for tx in transactions[:50]:  # analyze up to 50 txs
        result = analyze_transaction(tx)
        if result:
            total_txs += 1
            if result["can_attach"]:
                attachable += 1
                opportunities.append(result)

    # Summary stats
    attach_rate = (attachable/total_txs*100) if total_txs else 0

    total_savings_kas = sum(o["savings_kas"] for o in opportunities)
    avg_savings_pct = sum(o["savings_pct"] for o in opportunities) / len(opportunities) if opportunities else 0

    print(f"\n  ─────────────────────────────────────")
    print(f"  SIMULATION RESULTS:")
    print(f"  Total txs analyzed:   {total_txs}")
    print(f"  Attachable:           {attachable} ({attach_rate:.1f}%)")
    print(f"  Total savings:        {total_savings_kas:.6f} KAS")
    print(f"  Avg savings:          {avg_savings_pct:.1f}% vs standalone")

    # Project long term
    print(f"\n  LONG TERM PROJECTIONS:")
    print(f"  (assuming {attach_rate:.0f}% attach rate)")
    for daily_commits in [10, 100, 1000, 10000]:
        attached = int(daily_commits * attach_rate / 100)
        standalone = daily_commits - attached
        daily_cost_kas = (attached * (USIL_COMMIT_BYTES * 100 / 1e8) +
                          standalone * 0.5)
        full_cost_kas = daily_commits * 0.5
        daily_saving = full_cost_kas - daily_cost_kas
        print(f"  {daily_commits:>6} commits/day: "
              f"{daily_cost_kas:.4f} KAS "
              f"(save {daily_saving:.4f} KAS/day "
              f"vs {full_cost_kas:.1f} KAS standalone)")

    # Show sample opportunities
    if opportunities:
        print(f"\n  SAMPLE OPPORTUNITIES (first 5):")
        for o in opportunities[:5]:
            print(f"  TX {o['tx_id']}:")
            print(f"    Available: {o['available_bytes']:,} bytes")
            print(f"    Savings:   {o['savings_kas']:.8f} KAS ({o['savings_pct']:.1f}%)")

    print(f"\n  ✅ Simulation complete")
    return opportunities

if __name__ == "__main__":
    run_simulation()
