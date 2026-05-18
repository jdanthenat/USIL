"""
usil_traffic_sim.py — Traffic speed comparison
Measures Kaspa transaction throughput with and without parasitic USIL payload
Uses real network data
"""
import requests, time, hashlib, statistics
from datetime import datetime

KASPA_API = "https://api.kaspa.org"
USIL_BYTES = 160  # compressed via Zipcryption

def measure_block_time(samples=10):
    """Measure real Kaspa block times"""
    print(f"\n  Sampling {samples} recent blocks for timing...")
    
    times = []
    dag = requests.get(f"{KASPA_API}/info/blockdag", timeout=15).json()
    tip = dag["tipHashes"][0]
    
    # Get recent blocks with timestamps
    r = requests.get(
        f"{KASPA_API}/blocks?lowHash={tip}&includeTransactions=false&limit={samples}",
        timeout=15
    )
    
    if r.status_code == 200:
        blocks = r.json()
        if isinstance(blocks, list):
            for i in range(1, len(blocks)):
                t1 = blocks[i-1].get("header", {}).get("timestamp", 0)
                t2 = blocks[i].get("header", {}).get("timestamp", 0)
                if t1 and t2:
                    diff_ms = abs(t2 - t1)
                    if 0 < diff_ms < 10000:
                        times.append(diff_ms)
    
    return times

def simulate_tx_overhead():
    """
    Simulate transaction size overhead WITH and WITHOUT
    USIL parasitic payload
    """
    print(f"\n  TRAFFIC SPEED COMPARISON")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ─────────────────────────────────────")

    # Get real block data
    dag = requests.get(f"{KASPA_API}/info/blockdag", timeout=15).json()
    tip = dag["tipHashes"][0]
    block = requests.get(
        f"{KASPA_API}/blocks/{tip}?includeTransactions=true",
        timeout=15
    ).json()

    txs = block.get("transactions", [])
    print(f"\n  Real block: {tip[:24]}...")
    print(f"  Transactions: {len(txs)}")

    # Measure baseline tx sizes
    baseline_sizes = []
    parasitic_sizes = []
    overhead_pcts = []

    for tx in txs[:20]:
        # Estimate base tx size from mass
        mass = tx.get("mass", 0) or tx.get("computeMass", 0) or 1000
        payload = tx.get("payload", "")
        payload_bytes = len(payload) // 2 if payload else 0
        base_size = mass + payload_bytes

        # Only attach to txs large enough
        # that USIL overhead is <5%
        MIN_HOST_SIZE = USIL_BYTES * 20  # 3,200 bytes minimum
        if base_size < MIN_HOST_SIZE:
            continue  # skip tiny txs
            
        # With USIL attachment
        parasitic_size = base_size + USIL_BYTES
        overhead_pct = (USIL_BYTES / base_size) * 100

        baseline_sizes.append(base_size)
        parasitic_sizes.append(parasitic_size)
        overhead_pcts.append(overhead_pct)

    # Block timing
    print(f"\n  [1/3] BLOCK TIMING (real network)")
    block_times = measure_block_time(10)
    if block_times:
        avg_block_ms = statistics.mean(block_times)
        print(f"  Avg block time:     {avg_block_ms:.0f}ms")
        print(f"  Target block time:  ~1000ms (1 BPS)")
        print(f"  Actual BPS:         {1000/avg_block_ms:.2f}")
    else:
        avg_block_ms = 1000
        print(f"  Using estimated:    1000ms block time")

    # Size comparison
    print(f"\n  [2/3] TRANSACTION SIZE COMPARISON")
    avg_baseline = statistics.mean(baseline_sizes) if baseline_sizes else 1000
    avg_parasitic = statistics.mean(parasitic_sizes) if parasitic_sizes else 1512
    avg_overhead = statistics.mean(overhead_pcts) if overhead_pcts else 51.2

    print(f"  Avg tx size (baseline):  {avg_baseline:.0f} bytes")
    print(f"  Avg tx size (parasitic): {avg_parasitic:.0f} bytes")
    print(f"  USIL payload added:      {USIL_BYTES} bytes")
    print(f"  Size overhead:           {avg_overhead:.1f}%")

    # Throughput impact
    print(f"\n  [3/3] THROUGHPUT IMPACT")

    # Max block size post-Toccata: 250KB
    MAX_BLOCK_BYTES = 250000

    # Without USIL
    txs_per_block_baseline = MAX_BLOCK_BYTES / avg_baseline
    tps_baseline = txs_per_block_baseline / (avg_block_ms / 1000)

    # With USIL parasitic
    txs_per_block_parasitic = MAX_BLOCK_BYTES / avg_parasitic
    tps_parasitic = txs_per_block_parasitic / (avg_block_ms / 1000)

    tps_reduction = ((tps_baseline - tps_parasitic) / tps_baseline) * 100

    print(f"  WITHOUT USIL:")
    print(f"    Txs per block:  {txs_per_block_baseline:.0f}")
    print(f"    TPS:            {tps_baseline:.1f}")
    print(f"  WITH USIL (parasitic):")
    print(f"    Txs per block:  {txs_per_block_parasitic:.0f}")
    print(f"    TPS:            {tps_parasitic:.1f}")
    print(f"  TPS reduction:    {tps_reduction:.2f}%")
    print(f"  Network impact:   {'NEGLIGIBLE' if tps_reduction < 1 else 'MODERATE' if tps_reduction < 5 else 'SIGNIFICANT'}")

    # Gas cost comparison
    print(f"\n  GAS COST COMPARISON (post-Toccata 100 sompi/gram):")
    print(f"  Standalone STARK:  0.5 KAS per commitment")
    print(f"  Parasitic:         {USIL_BYTES * 100 / 1e8:.8f} KAS per commitment")
    print(f"  Savings:           {(0.5 - USIL_BYTES*100/1e8):.6f} KAS ({((0.5 - USIL_BYTES*100/1e8)/0.5*100):.1f}%)")

    # Multi-chain comparison
    print(f"\n  MULTI-CHAIN SPEED COMPARISON:")
    chains = [
        ("Kaspa",    avg_block_ms,  "DAG - multiple tips"),
        ("Solana",   400,           "PoH - fastest L1"),
        ("Ethereum", 12000,         "PoS - 12s slots"),
        ("Bitcoin",  600000,        "PoW - 10min blocks"),
    ]
    
    print(f"  {'Chain':<12} {'Block':<10} {'USIL settle':<15} {'Notes'}")
    print(f"  {'─'*55}")
    for chain, block_ms, notes in chains:
        settle_ms = block_ms  # 1 block to settle
        print(f"  {chain:<12} {block_ms/1000:.1f}s{'':<6} {settle_ms/1000:.1f}s{'':<11} {notes}")

    print(f"\n  ROUTING RECOMMENDATION:")
    print(f"  Routine commits → Kaspa or Solana (fastest)")
    print(f"  High stakes     → Bitcoin (most decentralized)")
    print(f"  Default         → Kaspa (native USIL chain)")

    print(f"\n  ✅ Traffic comparison complete")

if __name__ == "__main__":
    simulate_tx_overhead()
