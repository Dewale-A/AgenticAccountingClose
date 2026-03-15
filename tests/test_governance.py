"""
Tests for the GovernanceEngine in src/governance/engine.py.

Validates materiality-based approval routing, segregation of duties
enforcement, and the full evaluate_entry pipeline. These are the most
critical tests because the governance engine is the policy enforcement
layer for SOX compliance.
"""

import pytest
from src.models.schemas import (
    JournalEntry,
    JournalEntryLine,
    ApprovalLevel,
    EntryStatus,
    GovernancePolicy,
)
from src.governance.engine import GovernanceEngine


# ----------------------------------------------------------------
# Approval level routing
# ----------------------------------------------------------------

class TestGetApprovalLevel:
    """
    Verify that get_approval_level returns the correct tier at each
    materiality boundary. Thresholds: $10K (L1), $50K (L2), $250K (L3).
    """

    def test_below_l1_returns_auto(self, governance_engine):
        """$9,999 is below L1 and should auto-approve."""
        assert governance_engine.get_approval_level(9_999) == ApprovalLevel.AUTO

    def test_at_l1_returns_l1(self, governance_engine):
        """$10,000 is the L1 boundary and should require manager approval."""
        assert governance_engine.get_approval_level(10_000) == ApprovalLevel.L1_MANAGER

    def test_between_l1_l2(self, governance_engine):
        """$25,000 falls between L1 and L2, so L1 applies."""
        assert governance_engine.get_approval_level(25_000) == ApprovalLevel.L1_MANAGER

    def test_at_l2_returns_l2(self, governance_engine):
        """$50,000 is the L2 boundary and should require controller approval."""
        assert governance_engine.get_approval_level(50_000) == ApprovalLevel.L2_CONTROLLER

    def test_between_l2_l3(self, governance_engine):
        """$100,000 falls between L2 and L3, so L2 applies."""
        assert governance_engine.get_approval_level(100_000) == ApprovalLevel.L2_CONTROLLER

    def test_at_l3_returns_l3(self, governance_engine):
        """$250,000 is the L3 boundary and should require CFO approval."""
        assert governance_engine.get_approval_level(250_000) == ApprovalLevel.L3_CFO

    def test_above_l3(self, governance_engine):
        """$1,000,000 is well above L3 and should require CFO approval."""
        assert governance_engine.get_approval_level(1_000_000) == ApprovalLevel.L3_CFO

    def test_negative_amount_uses_absolute_value(self, governance_engine):
        """Negative amounts should use absolute value for threshold comparison."""
        assert governance_engine.get_approval_level(-50_000) == ApprovalLevel.L2_CONTROLLER


# ----------------------------------------------------------------
# Segregation of duties
# ----------------------------------------------------------------

class TestValidateSegregation:
    """
    Verify that the same person cannot both prepare and approve an entry.
    This is a core SOX control (SOX-JE-002).
    """

    def test_same_person_rejected(self, governance_engine):
        """Identical preparer and approver should be rejected."""
        assert governance_engine.validate_segregation("Alice", "Alice") is False

    def test_same_person_case_insensitive(self, governance_engine):
        """Check is case-insensitive: 'alice' == 'Alice'."""
        assert governance_engine.validate_segregation("alice", "ALICE") is False

    def test_different_people_allowed(self, governance_engine):
        """Different preparer and approver should pass."""
        assert governance_engine.validate_segregation("Alice", "Bob") is True

    def test_disabled_policy_allows_same_person(self, seeded_db):
        """When segregation is disabled in policy, same person is allowed."""
        policy = GovernancePolicy(enforce_segregation_of_duties=False)
        engine = GovernanceEngine(policy=policy)
        assert engine.validate_segregation("Alice", "Alice") is True


# ----------------------------------------------------------------
# Full entry evaluation
# ----------------------------------------------------------------

def _make_entry(
    amount=5000.0,
    balanced=True,
    confidence=0.9,
    preparer="JE Agent",
):
    """Helper: build a JournalEntry for testing evaluate_entry."""
    debit = amount
    credit = amount if balanced else amount - 1.0
    return JournalEntry(
        entry_id="JE-TEST-0001",
        entry_type="adjusting",
        description="Test entry",
        period="2026-02",
        lines=[
            JournalEntryLine(line_number=1, account_number="6000-100",
                             debit=debit, description="DR"),
            JournalEntryLine(line_number=2, account_number="2100-100",
                             credit=credit, description="CR"),
        ],
        total_debits=debit,
        total_credits=credit,
        is_balanced=abs(debit - credit) < 0.01,
        materiality_amount=amount,
        approval_level_required=ApprovalLevel.AUTO,
        prepared_by=preparer,
        confidence_score=confidence,
    )


class TestEvaluateEntry:
    """
    Verify the full evaluate_entry pipeline: balance check, approval
    routing, auto-approval, and confidence-based escalation.
    """

    def test_auto_approves_below_l1(self, governance_engine):
        """A balanced entry under $10K with high confidence should auto-approve."""
        entry = _make_entry(amount=5000.0)
        result = governance_engine.evaluate_entry(entry)
        assert result.status == EntryStatus.APPROVED
        assert "Auto-Approved" in (result.approved_by or "")

    def test_routes_to_pending_review_above_l1(self, governance_engine):
        """A balanced entry at $25K should route to pending_review (L1)."""
        entry = _make_entry(amount=25_000.0)
        result = governance_engine.evaluate_entry(entry)
        assert result.status == EntryStatus.PENDING_REVIEW

    def test_routes_to_l2_review(self, governance_engine):
        """A balanced entry at $75K should route to pending_l2_review."""
        entry = _make_entry(amount=75_000.0)
        result = governance_engine.evaluate_entry(entry)
        assert result.status == EntryStatus.PENDING_L2_REVIEW

    def test_routes_to_l3_review(self, governance_engine):
        """A balanced entry at $300K should route to pending_l3_review."""
        entry = _make_entry(amount=300_000.0)
        result = governance_engine.evaluate_entry(entry)
        assert result.status == EntryStatus.PENDING_L3_REVIEW

    def test_rejects_unbalanced_entry(self, governance_engine):
        """An unbalanced entry should be immediately rejected."""
        entry = _make_entry(amount=5000.0, balanced=False)
        result = governance_engine.evaluate_entry(entry)
        assert result.status == EntryStatus.REJECTED
        assert "not balanced" in (result.rejection_reason or "").lower()

    def test_low_confidence_escalation(self, governance_engine):
        """An entry below L1 but with low confidence should NOT auto-approve."""
        entry = _make_entry(amount=5000.0, confidence=0.3)
        result = governance_engine.evaluate_entry(entry)
        # Low confidence prevents auto-approval; entry routes to review
        assert result.status != EntryStatus.APPROVED
