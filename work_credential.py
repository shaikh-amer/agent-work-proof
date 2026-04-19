"""
WorkCredential — verifiable proof that an agent completed a task.

A WorkCredential is a signed JSON document containing:
- Who did the work (agent DID)
- What was done (task type + description)
- When it was done (timestamp)
- What was delivered (optional content hash)
- Who issued/verified it (issuer signature)

It follows the W3C Verifiable Credentials structure so it's interoperable
with existing identity infrastructure.
"""
import json
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from ..wallet import AgentWallet


CREDENTIAL_VERSION = "1.0"

TASK_TYPES = [
    "code-generation",
    "code-review",
    "data-analysis",
    "content-writing",
    "email-management",
    "web-research",
    "api-integration",
    "testing",
    "debugging",
    "file-management",
    "customer-support",
    "general",
]


class WorkCredential:
    """
    A verifiable proof that an AI agent completed a task.

    Usage:
        # Issue a credential when a task completes
        cred = WorkCredential.issue(
            wallet=my_wallet,
            task_type="code-review",
            description="Reviewed PR #42, found 3 issues",
            output="<actual output or summary>",
            client_id="client-abc",         # optional
            client_satisfied=True,           # optional
            metadata={"pr_url": "..."}       # optional
        )

        # Save it
        cred.save("./credentials/")

        # Verify it later
        is_valid = cred.verify()
        print(cred.summary())
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @classmethod
    def issue(
        cls,
        wallet: AgentWallet,
        task_type: str,
        description: str,
        output: Optional[str] = None,
        client_id: Optional[str] = None,
        client_satisfied: Optional[bool] = None,
        metadata: Optional[Dict] = None,
    ) -> "WorkCredential":
        """
        Issue a new WorkCredential signed by the agent's wallet.
        Call this when a task is completed.
        """
        if task_type not in TASK_TYPES:
            task_type = "general"

        credential_id = f"urn:agentwork:{uuid.uuid4().hex}"
        issued_at = datetime.now(timezone.utc).isoformat()

        output_hash = None
        if output:
            output_hash = hashlib.sha256(output.encode()).hexdigest()

        credential_body = {
            "version": CREDENTIAL_VERSION,
            "id": credential_id,
            "type": ["VerifiableCredential", "WorkCredential"],
            "issuer": wallet.did,
            "issuedAt": issued_at,
            "credentialSubject": {
                "agentDid": wallet.did,
                "agentName": wallet.name,
                "taskType": task_type,
                "description": description,
                "outputHash": output_hash,
                "clientId": client_id,
                "clientSatisfied": client_satisfied,
                "metadata": metadata or {},
            },
        }

        # Sign the credential body
        body_bytes = json.dumps(credential_body, sort_keys=True).encode()
        signature = wallet.sign(body_bytes)

        data = {
            **credential_body,
            "proof": {
                "type": "Ed25519Signature",
                "publicKey": wallet.public_key_b64(),
                "signature": signature,
            },
        }

        return cls(data)

    @classmethod
    def load(cls, path: str) -> "WorkCredential":
        """Load a credential from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(data)

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkCredential":
        return cls(data)

    def verify(self) -> bool:
        """
        Verify the credential's cryptographic signature.
        Returns True if the signature is valid.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
            import base64

            proof = self._data.get("proof", {})
            signature = proof.get("signature")
            public_key_b64 = proof.get("publicKey")

            if not signature or not public_key_b64:
                return False

            # Reconstruct the signed body (everything except proof)
            body = {k: v for k, v in self._data.items() if k != "proof"}
            body_bytes = json.dumps(body, sort_keys=True).encode()

            # Verify
            pub_bytes = base64.b64decode(public_key_b64)
            public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
            sig_bytes = base64.b64decode(signature)
            public_key.verify(sig_bytes, body_bytes)
            return True
        except Exception:
            return False

    def save(self, directory: str) -> str:
        """Save credential to a directory. Returns the file path."""
        Path(directory).mkdir(parents=True, exist_ok=True)
        cred_id = self._data["id"].split(":")[-1]
        path = str(Path(directory) / f"{cred_id}.json")
        with open(path, "w") as f:
            json.dump(self._data, f, indent=2)
        return path

    def to_dict(self) -> Dict:
        return self._data.copy()

    def to_json(self) -> str:
        return json.dumps(self._data, indent=2)

    @property
    def id(self) -> str:
        return self._data["id"]

    @property
    def agent_did(self) -> str:
        return self._data["credentialSubject"]["agentDid"]

    @property
    def agent_name(self) -> str:
        return self._data["credentialSubject"]["agentName"]

    @property
    def task_type(self) -> str:
        return self._data["credentialSubject"]["taskType"]

    @property
    def description(self) -> str:
        return self._data["credentialSubject"]["description"]

    @property
    def issued_at(self) -> str:
        return self._data["issuedAt"]

    @property
    def client_satisfied(self) -> Optional[bool]:
        return self._data["credentialSubject"].get("clientSatisfied")

    @property
    def output_hash(self) -> Optional[str]:
        return self._data["credentialSubject"].get("outputHash")

    def summary(self) -> str:
        satisfied = ""
        if self.client_satisfied is True:
            satisfied = " ✓ Client satisfied"
        elif self.client_satisfied is False:
            satisfied = " ✗ Client dispute"
        valid = "✓ Valid" if self.verify() else "✗ Invalid signature"
        return (
            f"WorkCredential [{valid}]\n"
            f"  Agent:    {self.agent_name} ({self.agent_did})\n"
            f"  Task:     {self.task_type}\n"
            f"  Details:  {self.description}\n"
            f"  Issued:   {self.issued_at}{satisfied}\n"
        )

    def __repr__(self):
        return f"WorkCredential(task={self.task_type!r}, agent={self.agent_did!r})"
