"""
LocalRegistry — local credential storage and query engine.

Stores credentials on disk (or in memory) and lets you query them
by agent DID, task type, date range, etc.

No server required. No external dependency. Just files.
"""
import json
import os
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timezone

from ..credentials import WorkCredential
from ..reputation import ReputationGraph


class LocalRegistry:
    """
    A local registry of WorkCredentials for one or more agents.
    
    Usage:
        registry = LocalRegistry("./my-registry/")
        
        # Store a credential
        registry.store(credential)
        
        # Query credentials
        creds = registry.query(agent_did="did:agentwork:abc...")
        creds = registry.query(task_type="code-review")
        
        # Get reputation
        rep = registry.get_reputation("did:agentwork:abc...")
        print(rep.summary())
    """

    def __init__(self, directory: str = "./agentwork-registry"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._index_path = self.directory / "index.json"
        self._index = self._load_index()

    def store(self, credential: WorkCredential) -> str:
        """Store a credential. Returns the file path."""
        if not credential.verify():
            raise ValueError("Cannot store credential with invalid signature")

        agent_dir = self.directory / credential.agent_did.replace(":", "_")
        agent_dir.mkdir(parents=True, exist_ok=True)

        path = credential.save(str(agent_dir))

        # Update index
        cred_id = credential.id
        self._index[cred_id] = {
            "path": path,
            "agent_did": credential.agent_did,
            "agent_name": credential.agent_name,
            "task_type": credential.task_type,
            "issued_at": credential.issued_at,
            "client_satisfied": credential.client_satisfied,
        }
        self._save_index()
        return path

    def query(
        self,
        agent_did: Optional[str] = None,
        task_type: Optional[str] = None,
        client_satisfied: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> List[WorkCredential]:
        """Query credentials with optional filters."""
        results = []

        for cred_id, meta in self._index.items():
            if agent_did and meta["agent_did"] != agent_did:
                continue
            if task_type and meta["task_type"] != task_type:
                continue
            if client_satisfied is not None and meta["client_satisfied"] != client_satisfied:
                continue
            try:
                cred = WorkCredential.load(meta["path"])
                results.append(cred)
            except Exception:
                continue

        # Sort by issued_at descending
        results.sort(key=lambda c: c.issued_at, reverse=True)

        if limit:
            results = results[:limit]

        return results

    def get_reputation(self, agent_did: str) -> ReputationGraph:
        """Get reputation graph for an agent."""
        creds = self.query(agent_did=agent_did)
        if not creds:
            raise ValueError(f"No credentials found for {agent_did}")
        return ReputationGraph.from_credentials(creds)

    def list_agents(self) -> List[Dict]:
        """List all agents in the registry with their stats."""
        agents = {}
        for meta in self._index.values():
            did = meta["agent_did"]
            if did not in agents:
                agents[did] = {
                    "agent_did": did,
                    "agent_name": meta["agent_name"],
                    "total_credentials": 0,
                }
            agents[did]["total_credentials"] += 1
        return list(agents.values())

    def stats(self) -> Dict:
        """Registry-wide statistics."""
        total = len(self._index)
        agents = len({m["agent_did"] for m in self._index.values()})
        task_types = {}
        for m in self._index.values():
            tt = m["task_type"]
            task_types[tt] = task_types.get(tt, 0) + 1
        return {
            "total_credentials": total,
            "total_agents": agents,
            "task_type_breakdown": task_types,
        }

    def _load_index(self) -> Dict:
        if self._index_path.exists():
            with open(self._index_path) as f:
                return json.load(f)
        return {}

    def _save_index(self):
        with open(self._index_path, "w") as f:
            json.dump(self._index, f, indent=2)

    def __repr__(self):
        return f"LocalRegistry(directory={str(self.directory)!r}, credentials={len(self._index)})"
