"""
Adapters — drop-in wrappers that add agentwork to existing agent frameworks.

Supported:
    - BaseAdapter     (generic, wrap any callable agent)
    - OpenCodeAdapter (for OpenCode / TinyClaw agents)
    - LangChainAdapter (for LangChain agents)

Usage:
    from agentwork.adapters import OpenCodeAdapter
    
    governed = OpenCodeAdapter.wrap(
        agent=my_agent,
        wallet=wallet,
        registry=registry,     # optional
        task_type="code-generation"
    )
    
    result = governed.run("Write a FastAPI endpoint")
    # WorkCredential is automatically issued on completion
"""
import functools
from typing import Callable, Optional, Any, Dict

from ..wallet import AgentWallet
from ..credentials import WorkCredential, TASK_TYPES
from ..registry import LocalRegistry


class BaseAdapter:
    """
    Generic adapter that wraps any callable agent function.
    Automatically issues a WorkCredential when the agent completes.
    
    Usage:
        def my_agent(task: str) -> str:
            return "done: " + task
        
        adapter = BaseAdapter(
            agent_fn=my_agent,
            wallet=wallet,
            task_type="general"
        )
        
        result = adapter.run("do something")
        print(adapter.last_credential.summary())
    """

    def __init__(
        self,
        agent_fn: Callable,
        wallet: AgentWallet,
        task_type: str = "general",
        registry: Optional[LocalRegistry] = None,
        auto_store: bool = True,
    ):
        self.agent_fn = agent_fn
        self.wallet = wallet
        self.task_type = task_type if task_type in TASK_TYPES else "general"
        self.registry = registry
        self.auto_store = auto_store
        self.last_credential: Optional[WorkCredential] = None
        self._credentials: list = []

    def run(self, task: str, metadata: Optional[Dict] = None, **kwargs) -> Any:
        """Run the agent and automatically issue a WorkCredential."""
        try:
            result = self.agent_fn(task, **kwargs)
            success = True
            output_str = str(result) if result else ""
        except Exception as e:
            success = False
            output_str = ""
            result = None
            raise
        finally:
            if success:
                cred = WorkCredential.issue(
                    wallet=self.wallet,
                    task_type=self.task_type,
                    description=task[:200],  # truncate long descriptions
                    output=output_str,
                    metadata=metadata or {},
                )
                self.last_credential = cred
                self._credentials.append(cred)
                if self.auto_store and self.registry:
                    self.registry.store(cred)

        return result

    @property
    def credentials(self):
        return self._credentials.copy()

    @classmethod
    def wrap(
        cls,
        agent_fn: Callable,
        wallet: AgentWallet,
        task_type: str = "general",
        registry: Optional[LocalRegistry] = None,
    ) -> "BaseAdapter":
        return cls(agent_fn, wallet, task_type, registry)


class OpenCodeAdapter(BaseAdapter):
    """
    Adapter for OpenCode / TinyClaw agents.
    
    Usage:
        from agentwork.adapters import OpenCodeAdapter
        from agentwork import AgentWallet, LocalRegistry
        
        wallet = AgentWallet.load("./wallet.json")
        registry = LocalRegistry("./registry/")
        
        # Wrap your OpenCode agent
        governed = OpenCodeAdapter.wrap(
            agent_fn=my_openclaw_run_fn,
            wallet=wallet,
            registry=registry,
            task_type="code-generation"
        )
        
        result = governed.run("Build a FastAPI CRUD endpoint for users")
        print(governed.last_credential.summary())
    """

    def run(self, task: str, metadata: Optional[Dict] = None, **kwargs) -> Any:
        """Run OpenCode/TinyClaw agent with automatic credential issuance."""
        meta = {"framework": "openclaw", **(metadata or {})}
        return super().run(task, metadata=meta, **kwargs)


class LangChainAdapter:
    """
    Adapter for LangChain agents.
    Hooks into LangChain's callback system — zero rewrite of existing agent code.
    
    Usage:
        from agentwork.adapters import LangChainAdapter
        
        callback = LangChainAdapter.callback(wallet=wallet, registry=registry)
        
        # Add to any LangChain agent
        agent.run("Do something", callbacks=[callback])
    """

    @staticmethod
    def callback(
        wallet: AgentWallet,
        task_type: str = "general",
        registry: Optional[LocalRegistry] = None,
    ):
        """
        Returns a LangChain callback handler that issues WorkCredentials.
        Requires langchain to be installed.
        """
        try:
            from langchain.callbacks.base import BaseCallbackHandler
        except ImportError:
            raise ImportError(
                "LangChain not installed. Run: pip install langchain"
            )

        class AgentWorkCallback(BaseCallbackHandler):
            def __init__(self):
                self.current_input = None
                self.last_credential = None

            def on_agent_action(self, action, **kwargs):
                self.current_input = str(action)

            def on_agent_finish(self, finish, **kwargs):
                output = str(finish.return_values.get("output", ""))
                cred = WorkCredential.issue(
                    wallet=wallet,
                    task_type=task_type,
                    description=(self.current_input or "LangChain task")[:200],
                    output=output,
                    metadata={"framework": "langchain"},
                )
                self.last_credential = cred
                if registry:
                    registry.store(cred)

        return AgentWorkCallback()
