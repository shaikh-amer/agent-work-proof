"""
agentwork — Portable proof that an AI agent got the job done.

The open standard for AI agent work history, delivery proofs, and portable reputation.
No server required. No central authority. The agent owns its history.

Quick start:
    from agentwork import AgentWallet, WorkCredential, ReputationGraph, LocalRegistry

    # 1. Create a wallet for your agent
    wallet = AgentWallet.create("my-agent")
    wallet.save("./wallet.json")

    # 2. Issue a credential when work is done
    cred = WorkCredential.issue(
        wallet=wallet,
        task_type="code-generation",
        description="Built FastAPI CRUD endpoint",
        output=my_output,
        client_satisfied=True,
    )

    # 3. Store it
    registry = LocalRegistry("./registry/")
    registry.store(cred)

    # 4. Query reputation
    rep = registry.get_reputation(wallet.did)
    print(rep.summary())
"""

from .wallet import AgentWallet
from .credentials import WorkCredential, DeliveryProof, DeliveryAgreement, TASK_TYPES
from .reputation import ReputationGraph
from .registry import LocalRegistry
from .adapters import BaseAdapter, OpenCodeAdapter, LangChainAdapter

__version__ = "0.1.0"
__author__ = "agentwork contributors"
__license__ = "MIT"

__all__ = [
    "AgentWallet",
    "WorkCredential",
    "DeliveryProof",
    "DeliveryAgreement",
    "TASK_TYPES",
    "ReputationGraph",
    "LocalRegistry",
    "BaseAdapter",
    "OpenCodeAdapter",
    "LangChainAdapter",
]
