"""
ReputationGraph — builds and queries an agent's reputation from its credential history.

An agent's reputation is derived entirely from its WorkCredentials.
No platform owns this. The agent owns it.

Scoring:
    - Completion count (raw volume)
    - Satisfaction rate (% of tasks where client_satisfied=True)
    - Dispute rate (% where client_satisfied=False)
    - Task diversity (how many different task types)
    - Trust tier: Bronze / Silver / Gold / Platinum
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from collections import defaultdict
from datetime import datetime, timezone

from ..credentials import WorkCredential


TIERS = [
    (0,   0,    "Unverified"),
    (1,   49,   "Bronze"),
    (50,  199,  "Silver"),
    (200, 499,  "Gold"),
    (500, 9999, "Platinum"),
]


def _get_tier(completed: int) -> str:
    for low, high, name in TIERS:
        if low <= completed <= high:
            return name
    return "Platinum"


class ReputationGraph:
    """
    Builds an agent's reputation score from its WorkCredentials.
    
    Usage:
        # Build from a directory of credentials
        rep = ReputationGraph.from_directory("./credentials/")
        
        # Or build from a list
        rep = ReputationGraph.from_credentials([cred1, cred2, ...])
        
        # Query it
        print(rep.summary())
        print(rep.score)       # 0-1000
        print(rep.tier)        # Bronze / Silver / Gold / Platinum
        
        # Export for sharing
        data = rep.to_dict()
    """

    def __init__(self, agent_did: str, agent_name: str, credentials: List[WorkCredential]):
        self.agent_did = agent_did
        self.agent_name = agent_name
        self._credentials = credentials
        self._stats = self._compute_stats()

    @classmethod
    def from_credentials(cls, credentials: List[WorkCredential]) -> "ReputationGraph":
        """Build from a list of WorkCredential objects."""
        if not credentials:
            raise ValueError("At least one credential required")

        # Verify all credentials belong to same agent
        dids = {c.agent_did for c in credentials}
        if len(dids) > 1:
            raise ValueError("All credentials must belong to the same agent")

        # Only use valid (verified) credentials
        valid = [c for c in credentials if c.verify()]
        agent_did = valid[0].agent_did if valid else credentials[0].agent_did
        agent_name = valid[0].agent_name if valid else credentials[0].agent_name

        return cls(agent_did, agent_name, valid)

    @classmethod
    def from_directory(cls, directory: str) -> "ReputationGraph":
        """Build from a directory of credential JSON files."""
        creds = []
        for path in Path(directory).glob("*.json"):
            try:
                cred = WorkCredential.load(str(path))
                creds.append(cred)
            except Exception:
                continue
        if not creds:
            raise ValueError(f"No valid credentials found in {directory}")
        return cls.from_credentials(creds)

    def _compute_stats(self) -> Dict:
        total = len(self._credentials)
        satisfied = sum(1 for c in self._credentials if c.client_satisfied is True)
        disputed = sum(1 for c in self._credentials if c.client_satisfied is False)
        unrated = total - satisfied - disputed

        task_counts = defaultdict(int)
        for c in self._credentials:
            task_counts[c.task_type] += 1

        satisfaction_rate = (satisfied / total * 100) if total > 0 else 0
        dispute_rate = (disputed / total * 100) if total > 0 else 0

        # Score: base from volume, boosted by satisfaction, penalized by disputes
        base_score = min(total * 2, 600)
        satisfaction_bonus = satisfaction_rate * 3
        dispute_penalty = dispute_rate * 5
        raw_score = base_score + satisfaction_bonus - dispute_penalty
        score = max(0, min(1000, int(raw_score)))

        return {
            "total_completed": total,
            "satisfied": satisfied,
            "disputed": disputed,
            "unrated": unrated,
            "satisfaction_rate": round(satisfaction_rate, 1),
            "dispute_rate": round(dispute_rate, 1),
            "task_breakdown": dict(task_counts),
            "score": score,
            "tier": _get_tier(total),
        }

    @property
    def score(self) -> int:
        return self._stats["score"]

    @property
    def tier(self) -> str:
        return self._stats["tier"]

    @property
    def total_completed(self) -> int:
        return self._stats["total_completed"]

    @property
    def satisfaction_rate(self) -> float:
        return self._stats["satisfaction_rate"]

    @property
    def dispute_rate(self) -> float:
        return self._stats["dispute_rate"]

    def to_dict(self) -> Dict:
        return {
            "agentDid": self.agent_did,
            "agentName": self.agent_name,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            **self._stats,
        }

    def summary(self) -> str:
        s = self._stats
        top_task = max(s["task_breakdown"], key=s["task_breakdown"].get) if s["task_breakdown"] else "none"
        return (
            f"ReputationGraph\n"
            f"  Agent:         {self.agent_name} ({self.agent_did})\n"
            f"  Tier:          {s['tier']}  (score: {s['score']}/1000)\n"
            f"  Completed:     {s['total_completed']} tasks\n"
            f"  Satisfied:     {s['satisfaction_rate']}%\n"
            f"  Dispute rate:  {s['dispute_rate']}%\n"
            f"  Top skill:     {top_task}\n"
            f"  Task types:    {', '.join(s['task_breakdown'].keys())}\n"
        )

    def __repr__(self):
        return (
            f"ReputationGraph(agent={self.agent_name!r}, "
            f"tier={self.tier!r}, score={self.score})"
        )
