# USIL Simulation Engine
## Universal SHA-256 Interoperability Layer — v2.0

---

## Order of Operations

### Windows (Quickstart)
Double-click `start.bat` — it handles everything automatically.

### Manual (Windows / Mac / Linux)

**Step 1 — Install dependencies**
```bash
pip install rich requests
```

**Step 2 — Run the simulation**
```bash
python usil_sim.py
```
This populates `usil.db` with:
- Ghost commitments (track record)
- Shadow commitments (challenge window)
- Live settlement (sBTC minted)
- Attack log (all 6 attacks caught)

**Step 3 — Start the dashboard server**
```bash
python server.py
```
Serves the visual dashboard at `http://localhost:8765`

**Step 4 — Open the dashboard**
Browser opens automatically. If not: `http://localhost:8765`

---

## Command Reference

| Command | What it does |
|---------|-------------|
| `python usil_sim.py` | Full simulation — Ghost→Shadow→Live + attacks |
| `python usil_sim.py --fast` | Speed run (no delays) |
| `python usil_sim.py --attacks` | Attack simulator only |
| `python server.py` | Start dashboard server (port 8765) |
| `python server.py --port 9000` | Custom port |
| `python server.py --no-browser` | Server only, no auto-open |

---

## Project Structure

```
usil_sim/
├── start.bat          ← Windows launcher (run this first)
├── usil_sim.py        ← Main simulation runner + terminal dashboard
├── server.py          ← Web dashboard HTTP server
├── dashboard.html     ← Visual web dashboard (auto-polled)
├── usil.db            ← SQLite ledger (auto-created on first run)
│
└── usil/              ← Core protocol modules
    ├── commitment.py  ← SHA-256 commitment engine
    ├── bitcoin.py     ← Block header fetcher (sim + live API)
    ├── pipeline.py    ← Ghost→Shadow→Live state machine
    ├── ledger.py      ← SQLite MintLedger + audit trail
    └── attacks.py     ← Threat model attack simulator
```

---

## Live Bitcoin API (Production Switch)

In `usil/bitcoin.py`, replace `get_block_header()` with:

```python
import requests

def get_block_header(height: int) -> dict:
    hash_url  = f"https://blockstream.info/api/block-height/{height}"
    block_hash = requests.get(hash_url).text.strip()
    block_url  = f"https://blockstream.info/api/block/{block_hash}"
    data       = requests.get(block_url).json()
    tip        = int(requests.get("https://blockstream.info/api/blocks/tip/height").text)
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

## What the simulation proves

| Component | Status |
|-----------|--------|
| SHA-256 commitment math | Real — deterministic, versioned |
| Ghost→Shadow→Live pipeline | Real — flip switch enforced |
| SPV Merkle proof verification | Real — branch traversal |
| MintLedger double-mint protection | Real — SQLite UNIQUE constraint |
| Stale commitment expiry | Real — 2,016-block window |
| T1 Invalid state root | Caught — Merkle mismatch |
| T2 Oracle collusion | Caught — quorum not met |
| T3 Double mint | Caught — ALREADY_MINTED |
| T4 Replay / reorg | Caught — confirmation requirement |
| T5 Stale commitment | Caught — expiry window |
| T6 Proof system bug | Caught — corrupted branch rejected |

---

## Kaspa Toccata Hardfork

**Activation: June 5–20, 2026**

The hardfork delivers exactly what USIL needs at the execution layer:
- Native KRC-20 tokens on L1 → synthetic sBTC minting
- Groth16 ZK verification at base layer → Phase 5 zk adapter
- Covenants++ programmability → commitment registry contracts
- SilverScript → USIL contract language
- vProgs → sovereign program settlement (USIL execution model)

USIL is designed to deploy the week Toccata activates.

---

*USIL v2.0 — MIT License — github.com/usil-protocol*
