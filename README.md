# USIL — Universal SHA-256 Interoperability Layer
### Kaspa L1 Native Protocol Primitive | Whitepaper v3.0 | vProg Spec v1.0

> **Built for the Kaspa Toccata Hardfork (June 5–20, 2026)**  
> SHA-256 commitment engine · Ghost→Shadow→Live pipeline · CDAG settlement layer · 6-attack threat model validator

---

## ⚠️ Required Folder Structure

The files **must** be organized exactly like this or the simulation will not run.  
If you cloned from GitHub and everything is flat in the root — fix it first.

```
USIL/
├── usil_sim.py          ← run this
├── server.py            ← run this second
├── start.bat            ← Windows: double-click this instead
├── dashboard.html       ← served automatically by server.py
├── README.md
├── USIL_Whitepaper_v3.pdf
├── USIL_vProg_Spec_v1.md
│
└── usil/                ← THIS FOLDER MUST EXIST
    ├── __init__.py      ← must be here (can be empty)
    ├── attacks.py
    ├── bitcoin.py
    ├── cdag.py
    ├── commitment.py
    ├── ledger.py
    └── pipeline.py
```

**If your files are all in root (no usil/ subfolder), fix it:**

```bash
# Windows Command Prompt — run from inside the USIL folder
mkdir usil
move attacks.py usil\
move bitcoin.py usil\
move cdag.py usil\
move commitment.py usil\
move ledger.py usil\
move pipeline.py usil\
move __init__.py usil\
```

```bash
# Mac / Linux
mkdir usil
mv attacks.py bitcoin.py cdag.py commitment.py ledger.py pipeline.py __init__.py usil/
```

---

## Quickstart

**Windows — one click:**
```
double-click start.bat
```

**Manual (Windows / Mac / Linux):**
```bash
pip install rich requests
python usil_sim.py        # runs Ghost→Shadow→Live + all 6 attacks
python server.py          # starts dashboard at http://localhost:8765
```

---

## What This Is

USIL is a cross-chain state commitment protocol implemented as a **Kaspa native vProg**.

Instead of a contract sitting on top of Kaspa, USIL settles SHA-256 commitments directly into Kaspa L1 consensus via the Toccata hardfork's Groth16 ZK opcode — giving synthetic sBTC the same security level as native KAS.

```
commitment := SHA256( chain_id || block_height || state_root )
```

The three-way SHA-256 alignment:
```
Bitcoin PoW   →  SHA-256  (consensus level)
Kaspa PoW     →  SHA-256  (consensus level)
USIL          →  SHA-256  (commitment level)
```

---

## What the Simulation Proves

| Component | Status |
|---|---|
| SHA-256 commitment math | Real — deterministic, versioned |
| Ghost→Shadow→Live pipeline | Real — flip switch enforced |
| SPV Merkle proof verification | Real — branch traversal |
| CDAG blue score finality | Real — simulated Kaspa L1 state |
| Groth16 ZK verification | Simulated — maps to Toccata L1 opcode |
| MintLedger double-mint protection | Real — SQLite UNIQUE + CDAG layer |
| T1 — Invalid state root | Caught — Merkle mismatch |
| T2 — Oracle collusion | Caught — quorum not met |
| T3 — Double mint | Caught — ALREADY_MINTED |
| T4 — Replay / reorg | Caught — confirmation requirement |
| T5 — Stale commitment | Caught — 2,016-block expiry window |
| T6 — Proof system bug | Caught — corrupted branch rejected |

---

## Ghost → Shadow → Live

The pipeline mirrors the optimistic → trustless trust model progression:

```
GHOST    No network calls. Commitment generated, logged to SQLite.
         Builds track record. Flip switch locked until threshold met.

SHADOW   Real block data. Transaction built but not broadcast.
         Challenge window open. Maps to optimistic mode.

LIVE     SPV proof verified → CDAG submission → Groth16 ZK check →
         SilverScript covenant → native sBTC minted at Kaspa L1.
```

Flip switch logic: Shadow unlocks after 5 Ghost commitments at 90%+ accuracy.  
Live only fires after Shadow clears the challenge window clean.

---

## CDAG Layer

The simulation includes a full CDAG settlement layer that mirrors the Toccata vProg model:

- Every Live commitment is submitted to the CDAG with a blue score anchor
- Groth16 ZK verification is simulated (maps directly to the Toccata L1 opcode)
- CDAG MintLedger enforces double-mint protection at consensus level
- SilverScript covenant logic enforces all mint conditions

Post-Toccata: swap `usil/cdag.py` simulation calls for actual Kaspa vProg SDK calls.

---

## Command Reference

| Command | What it does |
|---|---|
| `python usil_sim.py` | Full simulation — Ghost→Shadow→Live + attacks |
| `python usil_sim.py --fast` | Speed run (no delays) |
| `python usil_sim.py --attacks` | Attack simulator only |
| `python server.py` | Dashboard at http://localhost:8765 |
| `python server.py --port 9000` | Custom port |

---

## Live Bitcoin API Switch

In `usil/bitcoin.py`, swap `get_block_header()` for live data:

```python
import requests

def get_block_header(height: int) -> dict:
    hash_url   = f"https://blockstream.info/api/block-height/{height}"
    block_hash = requests.get(hash_url).text.strip()
    block_url  = f"https://blockstream.info/api/block/{block_hash}"
    data       = requests.get(block_url).json()
    tip        = int(requests.get(
                   "https://blockstream.info/api/blocks/tip/height").text)
    return {
        "height":        data["height"],
        "hash":          data["id"],
        "prev_hash":     data["previousblockhash"],
        "merkle_root":   data["merkle_root"],
        "timestamp":     data["timestamp"],
        "bits":          hex(data["bits"]),
        "nonce":         data["nonce"],
        "tx_count":      data["tx_count"],
        "confirmations": tip - data["height"],
        "size_bytes":    data["size"],
        "chain_id":      CHAIN_ID_BITCOIN,
        "source":        "LIVE",
    }
```

---

## Open Questions (Seeking Kaspa Dev Input)

1. **CDAG storage pricing** — per-byte KAS fee vs flat fee per commitment?
2. **vProg canonical identity** — fixed ID in genesis state or permissionless deploy?
3. **Oracle validator staking** — KAS staking or separate USIL token? (preference: KAS)
4. **MEV resistance** — how should commitment submissions interact with reverse auction ordering?
5. **DAGKnight alignment** — recommended interface for vProgs to express finality dependencies?

---

## Documents

- `USIL_Whitepaper_v3.pdf` — full protocol spec, threat model, concrete BTC→Kaspa flow
- `USIL_vProg_Spec_v1.md` — technical vProg specification for Kaspa dev community review

---

## Kaspa Toccata Hardfork

**Activation: June 5–20, 2026**

| USIL Requirement | Toccata Primitive |
|---|---|
| Off-chain exec + L1 settlement | vProgs |
| ZK verification at consensus | Groth16 L1 opcode |
| L1 security for synthetics | Native KRC-20 on L1 |
| Execution dependency tracking | CDAG |
| Programmable mint conditions | SilverScript / Covenants++ |

USIL is designed to deploy the week Toccata activates.

---

*MIT License — github.com/jdanthenat/USIL*

---

## Related Protocol — ZNFP

**USIL handles settlement. ZNFP handles transmission.**

ZNFP (Zipcryption Neural Firing Protocol) is the companion protocol that carries USIL commitments across any physical transport layer — from internet to LoRa radio to acoustic coupling.

- ZNFP packet carries: intelligence signal / civic report / threat evidence
- USIL commitment anchors: the Merkle root on Kaspa L1
- CID token rewards: the node that generated and transmitted the signal

Every ZNFP packet carrying a USIL commitment becomes immutable on Kaspa L1, court-admissible by design, and rewarded in CID post-Toccata.

ZNFP GitHub: https://github.com/jdanthenat/ZNFP
Live spec: https://gidldata.com/znfp

---

## STARK Proof Integration — Toccata

USIL ZK proofs use the STARK verifier deployed on Kaspa mainnet as part of the Toccata hardfork (June 2026).

**Current parameters (per Michael Sutton commit, May 14 2026):**
- Block size limit: 250kb (doubled from 125kb)
- Minimum fee: 100 sompi/gram
- STARK proof cost: ~0.5 KAS per proof
- Classic transaction cost: ~0.002 KAS
- ZK backend: risc0 (Kaspa-deployed verifier)

**USIL Scaling Model:**

USIL commitment costs scale proportionally with user volume.

| Stage | Mode | Cost per commitment |
|-------|------|-------------------|
| Launch | Individual STARK proof | ~0.5 KAS |
| Growth | Batched (10x) | ~0.05 KAS |
| Scale | Batched (100x) | ~0.005 KAS |

The protocol supports both individual and batched proof modes without spec changes. Batching activates automatically when volume makes it economically efficient.

Ghost → Shadow → Live maps cleanly:
- **Ghost:** Individual commitment posted immediately (cheap, instant)
- **Shadow:** Batch ZK proof generated when volume justifies it
- **Live:** Settlement + CID release (identical regardless of batch size)

This design means early users get individual proofs and scale users get batched proofs — the same protocol handles both.

---

## USIL-ALGO — Zipcryption Hardware Benchmark

The USIL-ALGO hardware manifest standard includes a Zipcryption benchmark that measures compression, encryption, and sharding throughput on any device. This grades hardware for Codex marketplace job matching.

### Grade Table

| Grade | Pipeline MB/s | Example Hardware |
|-------|--------------|-----------------|
| PLATINUM | ≥ 100 | High-end GPU workstation |
| GOLD | ≥ 50 | Desktop CPU / cloud instance |
| SILVER | ≥ 20 | Laptop / mini PC |
| BRONZE | ≥ 5 | Raspberry Pi 5 / edge node |
| BASIC | < 5 | Microcontroller |

### Reference Benchmark — Raspberry Pi 5 (8GB)

```json
{
  "device_id": "f21c64651188c3b2",
  "hardware": { "platform": "aarch64", "processor": "ARM" },
  "zipcryption_bench": {
    "compress_mbps": 33.63,
    "compress_ratio": 1.00,
    "encrypt_mbps": 21.80,
    "shard_mbps": 1085.59,
    "pipeline_mbps": 13.06,
    "shards": 8,
    "algorithm": "LZ4+AES256+SHA256-Merkle"
  },
  "usil_algo_grade": "BRONZE",
  "pqc_attestation": {
    "algorithm": "ML-DSA-65",
    "quantum_resistant": true
  }
}
```

### PQC Attestation

Every hardware manifest is signed with ML-DSA-65 (NIST FIPS 204) — the post-quantum digital signature standard. Attestations are quantum-resistant and verifiable by any node in the USIL network.

### Compression Note

The benchmark uses random byte payloads (worst case). Real-world payloads (JSON, text, sensor telemetry) achieve 3-10x compression ratios, increasing effective pipeline throughput proportionally.

---

## CID Bridge — Ghost Superposition Batching

CID acts as the internal bridge currency for all GIDLdata ecosystem transactions. The Ghost phase of USIL enables a quantum-inspired batching optimization that dramatically reduces L1 gas costs.

### The Tollway Model
### Gas Efficiency

| Mode | STARK proofs | Cost per conversion |
|------|-------------|-------------------|
| Unbatched | 1 per conversion | ~0.5 KAS |
| Micro batch (10x) | 1 per 10 | ~0.05 KAS |
| Macro batch (100x) | 1 per 100 | ~0.005 KAS |
| Ghost superposition (1000x) | 1 per 1000 | ~0.0005 KAS |

### Ghost as Trajectory Intelligence

While in superposition the Ghost commitment actively monitors:
- Current Kaspa gas prices
- Batch fill rate
- Exchange rate movement  
- Network congestion

It collapses (fires) when trajectory is optimal — not on a fixed timer. This is the ZNFP neural firing model applied to settlement: nodes don't fire on every input, they fire when accumulated signal exceeds the action potential threshold.

### Throughput Reference (Pi 5)
The highway has capacity. The Ghost superposition optimizer makes it affordable at any scale.
