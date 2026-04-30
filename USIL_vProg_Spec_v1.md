# USIL vProg Specification
## Universal SHA-256 Interoperability Layer as a Kaspa Native Protocol Primitive

**Document Type:** Technical Specification  
**Version:** 1.0  
**Status:** Draft — Pre-Toccata Hardfork  
**Target:** Kaspa Developer Community / KIPs Process  
**Date:** 2026

---

## Abstract

This document specifies the implementation of USIL (Universal SHA-256 Interoperability Layer) as a native Kaspa vProg — a sovereign program that executes off-chain and settles cryptographic state commitments directly into Kaspa L1 consensus via the Toccata hardfork's ZK verification infrastructure.

USIL defines a standardized SHA-256 commitment format for representing any external blockchain's state, a pluggable proof adapter interface for validating that state, and a native KRC-20 minting protocol for issuing synthetic representations of cross-chain assets at the Kaspa L1 security level.

The result: sBTC and sETH that inherit Kaspa consensus-level security guarantees — not Kasplex contract-level guarantees.

---

## 1. Motivation

### 1.1 Why vProg, Not a Contract

A Kasplex smart contract executing USIL logic has its security bounded by the Kasplex VM. Any bug in the VM, any upgrade to the contract runtime, any governance decision about Kasplex affects USIL's security guarantees.

A vProg executing USIL logic settles into Kaspa L1 state. Its security is bounded by Kaspa consensus itself — the same guarantee that native KAS holds. There is no intermediate trust layer.

For a cross-chain bridge protocol, this distinction is the entire value proposition.

### 1.2 The SHA-256 Alignment

Three systems operating at L1 level share a common cryptographic primitive:

```
Bitcoin PoW      → SHA-256  (consensus-level)
Kaspa PoW        → SHA-256  (consensus-level)
USIL Commitment  → SHA-256  (commitment-level)
```

This is not incidental. It means:
- Bitcoin block headers can be natively represented in USIL commitments without hash format translation
- Bitcoin mining hardware is already economically aligned with Kaspa's security
- The commitment format is natively verifiable by any participant in either network
- USIL operates at the same cryptographic layer as both chains it bridges

### 1.3 Toccata Hardfork Enables This

The Toccata hardfork (June 5–20, 2026) delivers the three L1 primitives USIL requires:

| USIL Requirement | Toccata Primitive |
|---|---|
| Off-chain execution with on-chain settlement | vProgs |
| ZK proof verification at consensus level | Groth16 L1 opcode |
| Native asset minting at L1 security level | Native KRC-20 on L1 |
| Execution dependency tracking | CDAG (Computational DAG) |
| Programmable commitment rules | Covenants++ / SilverScript |

---

## 2. Architecture

### 2.1 Layer Map

```
┌─────────────────────────────────────────────────────┐
│  L0 — SOURCE CHAINS                                 │
│  Bitcoin · Ethereum · Litecoin · (any chain)        │
│  Unchanged. No modifications required.              │
└───────────────────┬─────────────────────────────────┘
                    │ block headers, state roots
                    ▼
┌─────────────────────────────────────────────────────┐
│  L1 — USIL EXTRACTION LAYER  (off-chain)            │
│  Python/Rust state readers                          │
│  RPC adapters, SPV provers, Merkle constructors     │
│  Pulls: block_height, merkle_root, confirmations    │
└───────────────────┬─────────────────────────────────┘
                    │ raw state fields
                    ▼
┌─────────────────────────────────────────────────────┐
│  L2 — USIL COMMITMENT ENGINE  (off-chain)           │
│  commitment := SHA256(chain_id ‖ block_height       │
│                       ‖ state_root)                 │
│  Produces: 33-byte versioned commitment             │
│  Also produces: ZK proof for L1 verification        │
└───────────────────┬─────────────────────────────────┘
                    │ commitment + ZK proof
                    ▼
┌─────────────────────────────────────────────────────┐
│  L3 — KASPA L1 SETTLEMENT  (on-chain)               │
│  vProg submits commitment to CDAG                   │
│  Groth16 opcode verifies ZK proof                   │
│  CDAG records execution commitment + dependencies   │
│  SilverScript covenant enforces mint conditions     │
└───────────────────┬─────────────────────────────────┘
                    │ verified commitment in L1 state
                    ▼
┌─────────────────────────────────────────────────────┐
│  L4 — NATIVE KRC-20 MINT  (L1 token)               │
│  sBTC minted as true native L1 token                │
│  Security: Kaspa consensus (not Kasplex VM)         │
│  MintLedger: CDAG state (not SQLite/contract)       │
└─────────────────────────────────────────────────────┘
```

### 2.2 vProg Execution Model

A USIL vProg instance is a sovereign program with the following lifecycle:

```
1. SPAWN
   vProg instantiated with source chain parameters
   chain_id, proof_adapter_id, trust_mode

2. EXECUTE  (off-chain)
   Fetch block header from source chain
   Construct SHA-256 commitment
   Generate ZK proof (Groth16) over commitment preimage

3. SUBMIT  (L1 boundary)
   Submit to CDAG:
     - commitment (33 bytes)
     - ZK proof   (Groth16, ~200 bytes)
     - execution_commitment (CDAG resource accounting)

4. VERIFY  (L1 — Groth16 opcode)
   Kaspa L1 executes: groth16_verify(proof, commitment)
   If valid: CDAG records commitment as L1 state
   If invalid: submission rejected at consensus level

5. SETTLE  (L1 — SilverScript covenant)
   Covenant checks all mint conditions
   Native KRC-20 minted to destination address
   CDAG MintLedger updated (append-only, consensus-enforced)
```

---

## 3. Commitment Specification

### 3.1 Format (unchanged from USIL v2)

```
commitment := VERSION (1 byte = 0x01)
           ‖  SHA256(
                chain_id     (4 bytes, big-endian uint32)
              ‖ block_height (8 bytes, big-endian uint64)
              ‖ state_root   (32 bytes)
              )
```

Total: 33 bytes. Deterministic. Chain-agnostic. L1-publishable.

### 3.2 ZK Proof Extension

For L1 settlement, the commitment is accompanied by a Groth16 proof:

```
zk_proof := Groth16.prove(
  circuit  = USIL_COMMITMENT_CIRCUIT,
  public   = [commitment, chain_id, block_height],
  witness  = [state_root, preimage_bytes]
)
```

The USIL_COMMITMENT_CIRCUIT encodes:
- SHA-256 preimage correctness
- chain_id is registered in the USIL chain registry
- block_height is within the 2,016-block validity window
- state_root format matches the registered chain's specification

**Proof size:** ~200 bytes (Groth16 constant size)  
**Verification cost:** Single Groth16 opcode call — O(1) regardless of source chain complexity  
**Prover hardware:** Standard CPU — no specialized hardware required (per Kaspa core dev confirmation)

### 3.3 CDAG Execution Commitment

Every vProg submission includes a CDAG execution commitment that tracks:

```
execution_commitment := {
  program_id:      USIL_VPROG_ID,
  dependencies:    [prev_commitment_hash],   // chain of commitments
  resource_usage:  { compute: N, storage: M },
  blue_score:      current_kaspa_blue_score, // finality reference
}
```

This makes USIL's commitment history a first-class DAG embedded within Kaspa's CDAG — every commitment traceable to a Kaspa blue score, every dependency explicit.

---

## 4. Chain Registry — L1 State

### 4.1 Registry Location

The USIL chain registry is stored as CDAG state — not in a contract, not off-chain. It is L1 consensus state.

```
registry[chain_id] := {
  name:             string,
  state_root_format: enum { UTXO_MERKLE, PATRICIA_TRIE, DAG_SNAPSHOT },
  proof_adapter:    enum { SPV, MERKLE_PATRICIA, GROTH16 },
  min_confirmations: uint32,
  registered_at:    blue_score,
  governance_hash:  bytes32   // hash of governance proposal that added this chain
}
```

### 4.2 Initial Registry

| Chain ID | Network | State Root | Proof Adapter | Confirmations |
|---|---|---|---|---|
| 0x00000001 | Bitcoin | UTXO Merkle | SPV → Groth16 | 6 |
| 0x00000002 | Ethereum | Patricia Trie | Merkle Patricia → Groth16 | 2 epochs |
| 0x00000003 | Kaspa | DAG Snapshot | GHOSTDAG score | 10s finality |
| 0x00000004 | Litecoin | UTXO Merkle | SPV → Groth16 | 12 |

### 4.3 Adding Chains

New chains are added via a SilverScript covenant governance transaction:

```silverscript
covenant AddChainProposal {
  require: quorum_signatures(MIN_VALIDATORS)
  require: chain_genesis_hash is valid
  require: state_root_format is supported
  effect:  registry.insert(chain_id, chain_spec)
}
```

---

## 5. Proof System Adapters

### 5.1 Phase 1 — SPV (Bitcoin, Litecoin)

Off-chain prover generates 80-byte block header + Merkle branch.  
ZK circuit wraps SPV verification into a Groth16 proof.  
L1 verifies: single Groth16 opcode call.

```
SPV → Groth16 wrapping:
  circuit input (public):  block_hash, merkle_root, difficulty_target
  circuit input (witness): block_header_bytes, merkle_branch
  circuit checks:
    - double-SHA256(header) < difficulty_target  (PoW valid)
    - merkle_branch leads from tx_hash to merkle_root  (inclusion valid)
  output: valid Groth16 proof
```

### 5.2 Phase 2 — Merkle Patricia (Ethereum)

Off-chain prover generates RLP-encoded Patricia proof.  
ZK circuit wraps trie traversal into a Groth16 proof.

### 5.3 Phase 3 — Native Groth16 (Any Chain)

Direct Groth16 proof of state validity — no intermediate wrapping.  
Target: any chain that natively supports ZK proving.

---

## 6. Native KRC-20 Mint Protocol

### 6.1 Mint Conditions (SilverScript Covenant)

```silverscript
covenant USILMint {
  // All conditions must be satisfied
  require: commitment is in CDAG state
  require: groth16_verify(commitment.proof) == true
  require: commitment.blue_score + FINALITY_THRESHOLD <= current_blue_score
  require: commitment.block_height within 2016_block_window
  require: NOT mint_ledger.contains(commitment_id, utxo_id)

  effect: {
    mint_ledger.insert(commitment_id, utxo_id, amount, destination)
    krc20_native.mint(asset=sBTC, amount=amount, to=destination)
  }
}
```

### 6.2 Security Level

Synthetic sBTC minted under this covenant has the following security properties:

- **Mint validity** guaranteed by Kaspa L1 consensus (Groth16 opcode)
- **Double-mint prevention** enforced by CDAG state (consensus-level, not contract-level)
- **Expiry enforcement** guaranteed by SilverScript covenant
- **Asset transferability** as native KRC-20 — same security as KAS itself

### 6.3 Redemption (BurnReceipt Protocol)

```
1. Holder burns sBTC on Kaspa L1
2. L1 emits BurnReceipt commitment into CDAG
3. vProg generates ZK proof of BurnReceipt
4. Relayer submits proof + BurnReceipt to source chain lock contract
5. Source chain releases original asset

Relayer is fully trustless — any party may relay a valid BurnReceipt.
BurnReceipt is a standard USIL commitment — same format, same verification.
```

---

## 7. CDAG Integration

### 7.1 USIL in the Computational DAG

The CDAG tracks program resource usage, dependencies, and execution commitments across all vProgs. USIL commitments form a sub-DAG within the CDAG:

```
CDAG (Kaspa global)
  └── USIL commitment sub-DAG
        ├── BTC commitment @ blue_score_N
        │     └── ZK proof verified by L1
        ├── ETH commitment @ blue_score_N+1
        │     └── ZK proof verified by L1
        └── BTC commitment @ blue_score_N+3
              ├── depends on: BTC commitment @ N (chain continuity)
              └── ZK proof verified by L1
```

Every commitment is anchored to a Kaspa blue score — providing a global, trustless timestamp for every cross-chain state observation USIL has ever made.

### 7.2 Blue Score Finality

USIL uses Kaspa's blue score as its finality reference:

```
FINALITY_THRESHOLD := 100 blue score units
  (~10 seconds at 10 BPS — Kaspa's near-instant confirmation)

A commitment is final when:
  current_blue_score >= commitment_blue_score + FINALITY_THRESHOLD
```

This means USIL commitments reach Kaspa-level finality in ~10 seconds regardless of the source chain's own finality time.

---

## 8. Trust Model at L1

### 8.1 Full Trust Hierarchy

```
TRUSTLESS MODE (recommended for all mints):
  Source chain state → ZK proof → Groth16 L1 opcode → CDAG state → native mint
  Trust assumption: Kaspa consensus + ZK proof system soundness
  No validators. No oracles. No multisig.

OPTIMISTIC MODE (high throughput, lower value):
  Source chain state → commitment → CDAG challenge window → native mint
  Trust assumption: at least 1 honest challenger exists during window
  Challenge window enforced by SilverScript covenant

ORACLE MODE (fast, low value only):
  Validator set signs commitment → quorum check → CDAG record → native mint
  Trust assumption: 2/3+ validators honest
  Validator staking enforced by SilverScript covenant (slash on fraud)
```

### 8.2 Why L1 Changes the Oracle Model

Even oracle mode benefits from L1 settlement. In a Kasplex contract, oracle fraud could potentially be covered up by a contract upgrade. In CDAG state, every oracle submission is permanently recorded at consensus level — immutable, publicly auditable, provably timestamped by blue score. Oracle fraud is permanently visible even if unpunished.

---

## 9. Roadmap (L1 Native)

| Phase | Timeline | Deliverable |
|---|---|---|
| Spec (this doc) | Now | vProg spec, CDAG integration design, ZK circuit definition |
| Pre-Toccata sim | Now | Python simulation with CDAG layer, Ghost→Shadow→Live |
| Toccata activation | Jun 5–20 2026 | Deploy USIL vProg on Kaspa mainnet |
| BTC bridge alpha | Jul–Aug 2026 | Live BTC→Kaspa sBTC, SPV→Groth16 prover, testnet |
| ETH bridge | Sep–Oct 2026 | ETH Merkle Patricia adapter, sETH |
| Multi-chain | Q1 2027 | Chain registry governance, additional assets |
| ZK native | Q2 2027 | Direct Groth16 proving (no SPV wrapper) |
| DAGKnight alignment | Q3 2027 | Upgrade commitment finality to DAGKnight consensus |

---

## 10. Open Questions for Kaspa Dev Community

The following design decisions require community input:

**Q1 — CDAG storage cost**  
How should USIL commitment storage in the CDAG be priced? Per-byte KAS fee vs. flat fee per commitment vs. fee proportional to source chain state size?

**Q2 — vProg identity**  
Should the USIL vProg have a fixed canonical ID registered in Kaspa genesis state, or should it be deployed permissionlessly like any other vProg?

**Q3 — Oracle validator set**  
Should oracle validators be required to hold/stake KAS, or should a separate USIL staking token be introduced? (Current preference: KAS staking — no new token for security.)

**Q4 — MEV resistance**  
Kaspa core devs have proposed reverse auctions for transaction ordering. How should USIL commitment submissions interact with this mechanism to prevent front-running of high-value bridge transactions?

**Q5 — DAGKnight alignment**  
The DagKnight upgrade is planned post-Toccata. USIL's finality model should align with DagKnight's improved convergence properties. Is there a recommended interface for vProgs to express finality dependencies relative to DagKnight ordering?

---

## 11. Reference Implementation

The USIL reference implementation is available at `github.com/usil-protocol`:

- `usil/commitment.py` — SHA-256 commitment engine
- `usil/bitcoin.py` — Bitcoin SPV prover (sim + live)
- `usil/pipeline.py` — Ghost→Shadow→Live state machine
- `usil/ledger.py` — MintLedger (SQLite pre-Toccata, CDAG post-Toccata)
- `usil/attacks.py` — Threat model validation

The simulation runs the complete protocol including CDAG settlement simulation, all 6 threat model attacks, and the Ghost→Shadow→Live pipeline. See `README.md` for setup.

---

## 12. Conclusion

USIL as a Kaspa vProg is not a bridge built on Kaspa. It is a bridge built into Kaspa — a native protocol primitive that inherits L1 consensus security for every synthetic asset it mints.

The combination of Kaspa's SHA-256 PoW, the Toccata hardfork's Groth16 L1 opcode, and USIL's standardized commitment format creates a cryptographic alignment between Bitcoin, Kaspa, and any chain that speaks SHA-256 — all operating at the L1 security level.

The reference implementation is running. The spec is defined. The hardfork is 5 weeks away.

---

*USIL vProg Spec v1.0 — MIT License*  
*Submitted to Kaspa developer community for review*  
*github.com/usil-protocol*
