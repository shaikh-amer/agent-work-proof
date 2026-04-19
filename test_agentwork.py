"""
Tests for agentwork core functionality.
"""
import pytest
import tempfile
import os
from pathlib import Path

from agentwork import (
    AgentWallet,
    WorkCredential,
    DeliveryProof,
    DeliveryAgreement,
    ReputationGraph,
    LocalRegistry,
    BaseAdapter,
    OpenCodeAdapter,
)


# ─── Wallet Tests ────────────────────────────────────────────────────────────

class TestAgentWallet:
    def test_create(self):
        wallet = AgentWallet.create("test-agent")
        assert wallet.name == "test-agent"
        assert wallet.did.startswith("did:agentwork:")
        assert len(wallet.did) > 20

    def test_did_is_stable(self):
        wallet = AgentWallet.create("test")
        did1 = wallet.did
        did2 = wallet.did
        assert did1 == did2

    def test_different_wallets_have_different_dids(self):
        w1 = AgentWallet.create("agent-1")
        w2 = AgentWallet.create("agent-2")
        assert w1.did != w2.did

    def test_sign_and_verify(self):
        wallet = AgentWallet.create("test")
        data = b"hello agentwork"
        signature = wallet.sign(data)
        assert wallet.verify(data, signature)

    def test_verify_fails_with_wrong_data(self):
        wallet = AgentWallet.create("test")
        signature = wallet.sign(b"original")
        assert not wallet.verify(b"tampered", signature)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wallet = AgentWallet.create("saved-agent")
            path = os.path.join(tmpdir, "wallet.json")
            wallet.save(path)

            loaded = AgentWallet.load(path)
            assert loaded.name == wallet.name
            assert loaded.did == wallet.did

    def test_loaded_wallet_can_verify_original_signatures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wallet = AgentWallet.create("test")
            data = b"important data"
            signature = wallet.sign(data)

            path = os.path.join(tmpdir, "wallet.json")
            wallet.save(path)
            loaded = AgentWallet.load(path)
            assert loaded.verify(data, signature)


# ─── WorkCredential Tests ────────────────────────────────────────────────────

class TestWorkCredential:
    def setup_method(self):
        self.wallet = AgentWallet.create("test-agent")

    def test_issue(self):
        cred = WorkCredential.issue(
            wallet=self.wallet,
            task_type="code-generation",
            description="Built a FastAPI endpoint",
            output="def hello(): return 'world'",
        )
        assert cred.task_type == "code-generation"
        assert cred.agent_did == self.wallet.did
        assert cred.agent_name == "test-agent"
        assert cred.output_hash is not None

    def test_verify_valid_credential(self):
        cred = WorkCredential.issue(
            wallet=self.wallet,
            task_type="code-review",
            description="Reviewed PR #42",
        )
        assert cred.verify()

    def test_verify_fails_if_tampered(self):
        cred = WorkCredential.issue(
            wallet=self.wallet,
            task_type="code-review",
            description="Reviewed PR #42",
        )
        # Tamper with the credential
        cred._data["credentialSubject"]["description"] = "TAMPERED"
        assert not cred.verify()

    def test_unknown_task_type_defaults_to_general(self):
        cred = WorkCredential.issue(
            wallet=self.wallet,
            task_type="definitely-not-a-real-type",
            description="Some task",
        )
        assert cred.task_type == "general"

    def test_client_satisfaction(self):
        cred = WorkCredential.issue(
            wallet=self.wallet,
            task_type="general",
            description="Task",
            client_satisfied=True,
        )
        assert cred.client_satisfied is True

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cred = WorkCredential.issue(
                wallet=self.wallet,
                task_type="testing",
                description="Ran test suite",
            )
            path = cred.save(tmpdir)
            loaded = WorkCredential.load(path)
            assert loaded.id == cred.id
            assert loaded.verify()

    def test_summary(self):
        cred = WorkCredential.issue(
            wallet=self.wallet,
            task_type="code-generation",
            description="Built something",
            client_satisfied=True,
        )
        summary = cred.summary()
        assert "Valid" in summary
        assert "test-agent" in summary


# ─── DeliveryProof Tests ─────────────────────────────────────────────────────

class TestDeliveryProof:
    def setup_method(self):
        self.wallet = AgentWallet.create("delivery-agent")

    def test_create_proof(self):
        output = "Here is the completed code: ..."
        proof = DeliveryProof.create(
            wallet=self.wallet,
            output=output,
            description="Delivered login page",
        )
        assert proof.verify()
        assert proof.verify_output(output)

    def test_wrong_output_fails_verification(self):
        proof = DeliveryProof.create(
            wallet=self.wallet,
            output="real output",
            description="Task",
        )
        assert not proof.verify_output("wrong output")

    def test_delivery_agreement_flow(self):
        agent_wallet = AgentWallet.create("agent")
        client_wallet = AgentWallet.create("client")

        # Agent creates agreement
        agreement = DeliveryAgreement.create(
            agent_wallet=agent_wallet,
            task_description="Build login page",
            acceptance_criteria="React component with email/password fields",
            client_id="client-123",
        )
        assert not agreement.is_countersigned

        # Client countersigns
        signed = agreement.countersign(client_wallet)
        assert signed.is_countersigned

        # Agent delivers
        proof = DeliveryProof.create(
            wallet=agent_wallet,
            output="<LoginPage component>",
            description="Login page delivered",
            agreement=signed,
        )
        assert proof.verify()
        assert proof._data["agreementId"] == agreement.id


# ─── ReputationGraph Tests ───────────────────────────────────────────────────

class TestReputationGraph:
    def setup_method(self):
        self.wallet = AgentWallet.create("rep-agent")

    def _make_creds(self, n, task_type="code-generation", satisfied=True):
        return [
            WorkCredential.issue(
                wallet=self.wallet,
                task_type=task_type,
                description=f"Task {i}",
                client_satisfied=satisfied,
            )
            for i in range(n)
        ]

    def test_basic_reputation(self):
        creds = self._make_creds(10, satisfied=True)
        rep = ReputationGraph.from_credentials(creds)
        assert rep.total_completed == 10
        assert rep.satisfaction_rate == 100.0
        assert rep.dispute_rate == 0.0

    def test_tiers(self):
        assert ReputationGraph.from_credentials(self._make_creds(1)).tier == "Bronze"
        assert ReputationGraph.from_credentials(self._make_creds(50)).tier == "Silver"
        assert ReputationGraph.from_credentials(self._make_creds(200)).tier == "Gold"
        assert ReputationGraph.from_credentials(self._make_creds(500)).tier == "Platinum"

    def test_score_increases_with_more_satisfied_work(self):
        low = ReputationGraph.from_credentials(self._make_creds(5, satisfied=True))
        high = ReputationGraph.from_credentials(self._make_creds(50, satisfied=True))
        assert high.score > low.score

    def test_disputes_lower_score(self):
        clean = ReputationGraph.from_credentials(self._make_creds(20, satisfied=True))
        disputed = ReputationGraph.from_credentials(
            self._make_creds(10, satisfied=True) + self._make_creds(10, satisfied=False)
        )
        assert clean.score > disputed.score

    def test_summary(self):
        creds = self._make_creds(5)
        rep = ReputationGraph.from_credentials(creds)
        summary = rep.summary()
        assert "rep-agent" in summary
        assert "Completed" in summary


# ─── LocalRegistry Tests ────────────────────────────────────────────────────

class TestLocalRegistry:
    def setup_method(self):
        self.wallet = AgentWallet.create("registry-agent")
        self.tmpdir = tempfile.mkdtemp()
        self.registry = LocalRegistry(self.tmpdir)

    def _issue(self, task_type="general", satisfied=None):
        return WorkCredential.issue(
            wallet=self.wallet,
            task_type=task_type,
            description="Test task",
            client_satisfied=satisfied,
        )

    def test_store_and_query(self):
        cred = self._issue()
        self.registry.store(cred)
        results = self.registry.query(agent_did=self.wallet.did)
        assert len(results) == 1
        assert results[0].id == cred.id

    def test_query_by_task_type(self):
        self.registry.store(self._issue("code-generation"))
        self.registry.store(self._issue("testing"))
        self.registry.store(self._issue("code-generation"))

        code_creds = self.registry.query(task_type="code-generation")
        assert len(code_creds) == 2

    def test_get_reputation(self):
        for _ in range(5):
            self.registry.store(self._issue(satisfied=True))
        rep = self.registry.get_reputation(self.wallet.did)
        assert rep.total_completed == 5
        assert rep.tier == "Bronze"

    def test_stats(self):
        self.registry.store(self._issue("code-generation"))
        self.registry.store(self._issue("testing"))
        stats = self.registry.stats()
        assert stats["total_credentials"] == 2
        assert stats["total_agents"] == 1


# ─── Adapter Tests ───────────────────────────────────────────────────────────

class TestAdapters:
    def setup_method(self):
        self.wallet = AgentWallet.create("adapter-agent")
        self.tmpdir = tempfile.mkdtemp()
        self.registry = LocalRegistry(self.tmpdir)

    def test_base_adapter(self):
        def my_agent(task):
            return f"Done: {task}"

        adapter = BaseAdapter(
            agent_fn=my_agent,
            wallet=self.wallet,
            task_type="general",
            registry=self.registry,
        )
        result = adapter.run("write a function")
        assert result == "Done: write a function"
        assert adapter.last_credential is not None
        assert adapter.last_credential.verify()

    def test_openclaw_adapter(self):
        def openclaw_fn(task):
            return f"OpenClaw output: {task}"

        adapter = OpenCodeAdapter.wrap(
            agent_fn=openclaw_fn,
            wallet=self.wallet,
            registry=self.registry,
        )
        result = adapter.run("build an API")
        assert adapter.last_credential is not None
        assert adapter.last_credential._data["credentialSubject"]["metadata"]["framework"] == "openclaw"

    def test_credentials_accumulate(self):
        def agent(task):
            return "done"

        adapter = BaseAdapter(agent_fn=agent, wallet=self.wallet)
        adapter.run("task 1")
        adapter.run("task 2")
        adapter.run("task 3")
        assert len(adapter.credentials) == 3
