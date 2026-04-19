"""
DeliveryProof — cryptographic handshake proving what was delivered.

Before a job starts, both agent and client agree on what "done" looks like.
When the agent delivers, the hash is verified. This is what unlocks escrow
and eliminates disputes.

Flow:
    1. Agent creates a DeliveryAgreement (with expected deliverable hash or description)
    2. Client countersigns the agreement
    3. Agent does the work, produces output
    4. Agent submits DeliveryProof (output hash matches agreement)
    5. Proof is verified — escrow releases
"""
import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from ..wallet import AgentWallet


class DeliveryAgreement:
    """
    Pre-task agreement between agent and client on what constitutes completion.
    Both parties sign this before work begins.
    """

    def __init__(self, data: Dict):
        self._data = data

    @classmethod
    def create(
        cls,
        agent_wallet: AgentWallet,
        task_description: str,
        acceptance_criteria: str,
        client_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> "DeliveryAgreement":
        """Agent creates the agreement before starting work."""
        agreement_id = f"urn:agentwork:agreement:{uuid.uuid4().hex}"
        created_at = datetime.now(timezone.utc).isoformat()

        body = {
            "id": agreement_id,
            "type": "DeliveryAgreement",
            "agentDid": agent_wallet.did,
            "agentName": agent_wallet.name,
            "clientId": client_id,
            "taskDescription": task_description,
            "acceptanceCriteria": acceptance_criteria,
            "createdAt": created_at,
            "metadata": metadata or {},
            "status": "pending_client",
        }

        body_bytes = json.dumps(body, sort_keys=True).encode()
        agent_signature = agent_wallet.sign(body_bytes)

        data = {
            **body,
            "agentSignature": agent_signature,
            "agentPublicKey": agent_wallet.public_key_b64(),
            "clientSignature": None,
        }

        return cls(data)

    def countersign(self, client_wallet: AgentWallet) -> "DeliveryAgreement":
        """Client countersigns to confirm the agreement."""
        # Sign the full agreement including agent signature
        body_bytes = json.dumps(
            {k: v for k, v in self._data.items() if k != "clientSignature"},
            sort_keys=True
        ).encode()
        client_sig = client_wallet.sign(body_bytes)

        new_data = {
            **self._data,
            "clientSignature": client_sig,
            "clientPublicKey": client_wallet.public_key_b64(),
            "status": "active",
        }
        return DeliveryAgreement(new_data)

    @property
    def id(self) -> str:
        return self._data["id"]

    @property
    def is_countersigned(self) -> bool:
        return self._data.get("clientSignature") is not None

    def to_dict(self) -> Dict:
        return self._data.copy()

    def __repr__(self):
        return f"DeliveryAgreement(id={self.id!r}, status={self._data['status']!r})"


class DeliveryProof:
    """
    Cryptographic proof that an agent delivered what was agreed.
    
    Usage:
        # When task is complete
        proof = DeliveryProof.create(
            wallet=agent_wallet,
            output="<actual output content>",
            agreement=agreement,       # optional, links to pre-task agreement
            description="Delivered X"
        )
        
        # Verify the proof
        print(proof.verify())          # True/False
        print(proof.output_hash)       # SHA-256 of the output
    """

    def __init__(self, data: Dict):
        self._data = data

    @classmethod
    def create(
        cls,
        wallet: AgentWallet,
        output: str,
        description: str,
        agreement: Optional[DeliveryAgreement] = None,
        metadata: Optional[Dict] = None,
    ) -> "DeliveryProof":
        """Create a delivery proof for completed work."""
        proof_id = f"urn:agentwork:delivery:{uuid.uuid4().hex}"
        delivered_at = datetime.now(timezone.utc).isoformat()

        # Hash the actual output
        output_hash = hashlib.sha256(output.encode()).hexdigest()

        body = {
            "id": proof_id,
            "type": "DeliveryProof",
            "agentDid": wallet.did,
            "agentName": wallet.name,
            "agreementId": agreement.id if agreement else None,
            "description": description,
            "outputHash": output_hash,
            "deliveredAt": delivered_at,
            "metadata": metadata or {},
        }

        body_bytes = json.dumps(body, sort_keys=True).encode()
        signature = wallet.sign(body_bytes)

        data = {
            **body,
            "proof": {
                "type": "Ed25519Signature",
                "publicKey": wallet.public_key_b64(),
                "signature": signature,
            },
        }

        return cls(data)

    def verify(self) -> bool:
        """Verify the delivery proof signature."""
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            import base64

            proof = self._data.get("proof", {})
            signature = proof.get("signature")
            public_key_b64 = proof.get("publicKey")

            if not signature or not public_key_b64:
                return False

            body = {k: v for k, v in self._data.items() if k != "proof"}
            body_bytes = json.dumps(body, sort_keys=True).encode()

            pub_bytes = base64.b64decode(public_key_b64)
            public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig_bytes = base64.b64decode(signature)
            public_key.verify(sig_bytes, body_bytes)
            return True
        except Exception:
            return False

    def verify_output(self, output: str) -> bool:
        """Verify that given output matches the proof's hash."""
        computed = hashlib.sha256(output.encode()).hexdigest()
        return computed == self._data.get("outputHash")

    @property
    def output_hash(self) -> str:
        return self._data["outputHash"]

    @property
    def agent_did(self) -> str:
        return self._data["agentDid"]

    @property
    def delivered_at(self) -> str:
        return self._data["deliveredAt"]

    def to_dict(self) -> Dict:
        return self._data.copy()

    def summary(self) -> str:
        valid = "✓ Valid" if self.verify() else "✗ Invalid"
        return (
            f"DeliveryProof [{valid}]\n"
            f"  Agent:      {self._data['agentName']} ({self.agent_did})\n"
            f"  Description:{self._data['description']}\n"
            f"  Output hash:{self.output_hash[:16]}...\n"
            f"  Delivered:  {self.delivered_at}\n"
        )

    def __repr__(self):
        return f"DeliveryProof(agent={self.agent_did!r}, valid={self.verify()})"
