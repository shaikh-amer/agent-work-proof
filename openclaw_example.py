"""
Example: Wrapping an OpenCode / TinyClaw agent with agentwork.

This shows the simplest possible integration — 10 lines of code,
zero changes to your existing agent.
"""
from agentwork import AgentWallet, LocalRegistry
from agentwork.adapters import OpenCodeAdapter


# ─── Step 1: Create or load your agent's wallet ──────────────────────────────

# First time: create and save
wallet = AgentWallet.create("my-openclaw-agent")
wallet.save("./wallet.json")
print(f"Agent DID: {wallet.did}")

# Next time: just load
# wallet = AgentWallet.load("./wallet.json")


# ─── Step 2: Set up local registry ──────────────────────────────────────────

registry = LocalRegistry("./registry/")


# ─── Step 3: Wrap your existing agent function ───────────────────────────────

# This simulates your actual OpenCode/TinyClaw agent function
def my_openclaw_agent(task: str) -> str:
    """Your real agent code goes here. agentwork doesn't care what's inside."""
    # In reality this would call OpenCode/TinyClaw's run() method
    return f"Completed task: {task}\n\n```python\ndef solution(): pass\n```"


# Wrap it — zero changes to my_openclaw_agent
governed_agent = OpenCodeAdapter.wrap(
    agent_fn=my_openclaw_agent,
    wallet=wallet,
    task_type="code-generation",
    registry=registry,
)


# ─── Step 4: Run tasks as normal ────────────────────────────────────────────

result = governed_agent.run("Build a FastAPI CRUD endpoint for users")
print("\nAgent output:")
print(result)

print("\nCredential issued:")
print(governed_agent.last_credential.summary())


# ─── Step 5: Check reputation after several tasks ───────────────────────────

# Simulate a few more tasks
governed_agent.run("Write unit tests for auth module")
governed_agent.run("Debug memory leak in websocket handler")
governed_agent.run("Refactor database connection pooling")

rep = registry.get_reputation(wallet.did)
print("\nReputation after 4 tasks:")
print(rep.summary())
print(f"Score: {rep.score}/1000")
print(f"Tier:  {rep.tier}")
