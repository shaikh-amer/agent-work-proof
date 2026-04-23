import argparse
from agent_work_proof import AgentWallet, WorkCredential, LocalRegistry

parser = argparse.ArgumentParser()
parser.add_argument('--task', default='completed task')
parser.add_argument('--output', default='')
args = parser.parse_args()

try:
    wallet = AgentWallet.load('/home/hydra/agent-work-proof/awp_wallet.json')
except:
    wallet = AgentWallet.create('AWP-agent')
    wallet.save('/home/hydra/agent-work-proof/awp_wallet.json')

registry = LocalRegistry('/home/hydra/agent-work-proof/awp-registry/')
cred = WorkCredential.issue(
    wallet=wallet,
    task_type='general',
    description=args.task[:200],
    output=args.output,
    client_satisfied=True
)
registry.store(cred)
print(f"✓ WorkCredential issued: {cred.id}")