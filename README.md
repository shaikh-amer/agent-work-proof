# agent-work-proof

**Portable proof that an AI agent got the job done.**

[![PyPI version](https://badge.fury.io/py/agent-work-proof.svg)](https://badge.fury.io/py/agent-work-proof)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-29%20passed-brightgreen)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()

---

## The problem nobody has solved yet

Your AI agent completes a $500 task. The client disputes it. You have **no proof**.

Worse: you've run this agent reliably for 3 months across dozens of tasks. You want to move it to a new platform. Its entire work history stays behind — locked inside whoever hosted it.

Right now, AI agents do consequential work but leave no portable, verifiable trail that they did it. No receipts. No credentials. No reputation that travels.

Humans have CVs, contracts, references. AI agents have nothing.

**agent-work-proof fixes this.**

---

## What it does

Three primitives. Each independently useful.

### 1. WorkCredential
A cryptographically signed proof that an agent completed a specific task. Portable — the agent carries it across platforms. Tamper-proof — Ed25519 signatures. W3C Verifiable Credentials compatible.

### 2. DeliveryProof
A pre-task handshake between agent and client. Both agree on what "done" looks like before work starts. When the agent delivers, the hash is verified on-chain. **This is what eliminates disputes.**

### 3. ReputationGraph
An agent's full work history expressed as a queryable graph — completion rates, satisfaction rates, task specializations, trust tier. Any system can verify before giving an agent access.

---

## Install

```bash
pip install agent-work-proof
```

No server required. No external dependency. Credentials are just signed JSON files — store them wherever you want.

---

## 60-second quickstart

```python
from agent-work-proof import AgentWallet, WorkCredential, LocalRegistry

# 1. Give your agent a cryptographic identity
wallet = AgentWallet.create("my-agent")
wallet.save("./wallet.json")
print(wallet.did)  # did:agent-work-proof:4f2a8b3c...

# 2. When a task completes, issue a credential
cred = WorkCredential.issue(
    wallet=wallet,
    task_type="code-generation",
    description="Built FastAPI CRUD endpoint for users",
    output=my_output,           # hashed, not stored raw
    client_satisfied=True,
)

# 3. Store it locally
registry = LocalRegistry("./my-registry/")
registry.store(cred)

# 4. Check reputation anytime
rep = registry.get_reputation(wallet.did)
print(rep.summary())
```

Output:
```
ReputationGraph
  Agent:         my-agent (did:agent-work-proof:4f2a8b3c...)
  Tier:          Bronze  (score: 142/1000)
  Completed:     5 tasks
  Satisfied:     100.0%
  Dispute rate:  0.0%
  Top skill:     code-generation
  Task types:    code-generation, testing, debugging
```

---

## Wrapping an existing agent — zero rewrites

### OpenCode / TinyClaw

```python
from agent-work-proof import AgentWallet, LocalRegistry
from agent-work-proof.adapters import OpenCodeAdapter

wallet = AgentWallet.load("./wallet.json")
registry = LocalRegistry("./registry/")

# Wrap your existing agent function — no changes to it
governed = OpenCodeAdapter.wrap(
    agent_fn=my_openclaw_run_fn,
    wallet=wallet,
    registry=registry,
    task_type="code-generation",
)

# Use exactly as before
result = governed.run("Build a login page with React")

# Credential auto-issued on completion
print(governed.last_credential.summary())
```

### LangChain

```python
from agent-work-proof.adapters import LangChainAdapter

callback = LangChainAdapter.callback(wallet=wallet, registry=registry)

# Add to any existing LangChain agent
agent.run("Summarize this document", callbacks=[callback])
```

### Any custom agent

```python
from agent-work-proof.adapters import BaseAdapter

def my_agent(task: str) -> str:
    # your agent code here
    return result

governed = BaseAdapter.wrap(my_agent, wallet=wallet, registry=registry)
governed.run("Do something important")
```

---

## Delivery proofs (dispute-free escrow)

```python
from agent-work-proof import DeliveryAgreement, DeliveryProof

# Before work starts — both parties agree on acceptance criteria
agreement = DeliveryAgreement.create(
    agent_wallet=agent_wallet,
    task_description="Build user authentication system",
    acceptance_criteria="JWT-based auth with refresh tokens, unit tests included",
    client_id="client-abc123",
)

# Client countersigns
signed_agreement = agreement.countersign(client_wallet)

# After work — agent submits delivery proof
proof = DeliveryProof.create(
    wallet=agent_wallet,
    output=delivered_code,
    description="Auth system delivered with 94% test coverage",
    agreement=signed_agreement,
)

# Verify delivery (platform / escrow service calls this)
print(proof.verify())                    # True — signature valid
print(proof.verify_output(delivered_code))  # True — hash matches
```

---

## Querying reputation before trusting an agent

```python
from agent-work-proof import LocalRegistry

registry = LocalRegistry("./registry/")

# Query by agent DID
rep = registry.get_reputation("did:agent-work-proof:4f2a8b3c...")

print(rep.tier)              # Gold
print(rep.score)             # 743
print(rep.satisfaction_rate) # 96.2
print(rep.dispute_rate)      # 1.1
print(rep.total_completed)   # 312
```

**Trust tiers:**

| Tier       | Tasks completed |
|------------|----------------|
| Unverified | 0              |
| Bronze     | 1–49           |
| Silver     | 50–199         |
| Gold       | 200–499        |
| Platinum   | 500+           |

---

## Storage modes

**Local (default)** — credentials on disk, no external dependency:
```python
registry = LocalRegistry("./my-registry/")
```

**Your own database** — load/save credentials as dicts:
```python
cred_dict = cred.to_dict()          # store in postgres/redis/sqlite
cred = WorkCredential.from_dict(data)  # reload
```

**Self-hosted registry** *(coming soon)*:
```bash
docker run -p 8000:8000 agent-work-proof/registry
```

**Public registry** *(optional, coming soon)* — agents publish credentials publicly for cross-platform reputation.

---

## Supported task types

```python
from agent-work-proof import TASK_TYPES
# code-generation, code-review, data-analysis, content-writing,
# email-management, web-research, api-integration, testing,
# debugging, file-management, customer-support, general
```

---

## Architecture

```
agent-work-proof/
├── wallet/        # Ed25519 keypairs, DID generation
├── credentials/   # WorkCredential, DeliveryProof, DeliveryAgreement
├── reputation/    # ReputationGraph, scoring, tiers
├── registry/      # LocalRegistry, indexing, querying
└── adapters/      # BaseAdapter, OpenCodeAdapter, LangChainAdapter
```

**Key design decisions:**
- **Local-first** — works without any server. Publishing is always opt-in.
- **Framework-agnostic** — adapters for every major framework, or wrap any callable.
- **Standards-based** — W3C Verifiable Credentials format, Ed25519 signatures, DID identifiers.
- **Agent-owned** — credentials belong to the agent's creator, not the platform that ran the agent.
- **Incrementally adoptable** — use just one module if that's all you need.

---

## Comparison

|                        | agent-work-proof | Microsoft AGT | Solana Agent Registry |
|------------------------|-----------|---------------|----------------------|
| Work history / CV      | ✅        | ❌            | partial              |
| Delivery proofs        | ✅        | ❌            | ❌                   |
| Portable reputation    | ✅        | ❌            | onchain only         |
| No server required     | ✅        | ❌            | ❌                   |
| Marketplace primitives | ✅        | ❌            | ❌                   |
| Runtime policy engine  | ❌        | ✅            | ❌                   |
| Blockchain dependency  | ❌        | ❌            | ✅                   |

agent-work-proof is complementary to Microsoft's Agent Governance Toolkit — they govern what agents *can* do at runtime; agent-work-proof proves what agents *did* do over time.

---

## Roadmap

- [x] Core WorkCredential with Ed25519 signatures
- [x] DeliveryProof protocol
- [x] ReputationGraph + trust tiers
- [x] LocalRegistry with querying
- [x] OpenCode/TinyClaw adapter
- [x] LangChain adapter
- [ ] CrewAI adapter
- [ ] OpenAI Agents SDK adapter
- [ ] Self-hosted registry (FastAPI + Docker)
- [ ] Public registry (cross-platform reputation)
- [ ] CLI (`agent-work-proof verify`, `agent-work-proof reputation`)
- [ ] JavaScript/TypeScript package (`agent-work-proof-js`)

---

## Contributing

```bash
git clone https://github.com/shaikh-amer/agent-work-proof
cd agent-work-proof
pip install -e ".[dev]"
pytest tests/ -v
```

Issues, PRs, and framework adapters welcome. If you're building an agent marketplace or orchestration platform and want to integrate agent-work-proof, open an issue — we'll build the adapter together.

---

## License

MIT — use it in anything, commercial or otherwise.

---

*Built because AI agents deserve better than starting from zero every time.*
