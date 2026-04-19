"""
AgentWallet — keypair management and DID generation for AI agents.
Every agent gets a cryptographic identity: a private key (kept secret)
and a DID (shared publicly to identify the agent).
"""
import json
import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    PrivateFormat,
    NoEncryption,
)
import base64


class AgentWallet:
    """
    A cryptographic wallet for an AI agent.
    
    Usage:
        # Create a new wallet
        wallet = AgentWallet.create("my-agent")
        print(wallet.did)  # did:agentwork:abc123...
        
        # Save and reload
        wallet.save("./wallet.json")
        wallet = AgentWallet.load("./wallet.json")
    """

    def __init__(self, name: str, private_key: Ed25519PrivateKey, created_at: str = None):
        self.name = name
        self._private_key = private_key
        self._public_key = private_key.public_key()
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.did = self._derive_did()

    @classmethod
    def create(cls, name: str) -> "AgentWallet":
        """Create a brand new wallet with a fresh keypair."""
        private_key = Ed25519PrivateKey.generate()
        return cls(name, private_key)

    @classmethod
    def load(cls, path: str) -> "AgentWallet":
        """Load a wallet from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        private_bytes = base64.b64decode(data["private_key"])
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
        wallet = cls(data["name"], private_key, data["created_at"])
        return wallet

    def save(self, path: str) -> None:
        """Save wallet to a JSON file. Keep this file secret."""
        private_bytes = self._private_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )
        data = {
            "name": self.name,
            "did": self.did,
            "private_key": base64.b64encode(private_bytes).decode(),
            "public_key": self._public_key_b64(),
            "created_at": self.created_at,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def sign(self, data: bytes) -> str:
        """Sign arbitrary bytes. Returns base64-encoded signature."""
        signature = self._private_key.sign(data)
        return base64.b64encode(signature).decode()

    def verify(self, data: bytes, signature: str) -> bool:
        """Verify a signature against this wallet's public key."""
        try:
            sig_bytes = base64.b64decode(signature)
            self._public_key.verify(sig_bytes, data)
            return True
        except Exception:
            return False

    def public_key_b64(self) -> str:
        return self._public_key_b64()

    def _public_key_b64(self) -> str:
        pub_bytes = self._public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return base64.b64encode(pub_bytes).decode()

    def _derive_did(self) -> str:
        """Derive a stable DID from the public key."""
        pub_bytes = self._public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        fingerprint = hashlib.sha256(pub_bytes).hexdigest()[:32]
        return f"did:agentwork:{fingerprint}"

    def __repr__(self):
        return f"AgentWallet(name={self.name!r}, did={self.did!r})"
