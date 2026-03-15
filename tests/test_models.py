"""
Tests for Pydantic schemas defined in src/models/schemas.py.

Validates that data models enforce correct types, defaults, and enum
values. These tests ensure the contract between agents, API, and
database remains consistent.
"""

import pytest
from src.models.schemas import (
    JournalEntryLine,
    JournalEntryCreate,
    EntryStatus,
    ApprovalLevel,
    GovernancePolicy,
    AccountType,
)


class TestJournalEntryLine:
    """Verify JournalEntryLine field validation and defaults."""

    def test_valid_debit_line(self):
        """A line with a positive debit and zero credit should be accepted."""
        line = JournalEntryLine(
            line_number=1,
            account_number="1000-100",
            debit=500.0,
            credit=0.0,
            description="Test debit",
        )
        assert line.debit == 500.0
        assert line.credit == 0.0

    def test_valid_credit_line(self):
        """A line with a positive credit and zero debit should be accepted."""
        line = JournalEntryLine(
            line_number=1,
            account_number="2000-100",
            debit=0.0,
            credit=500.0,
            description="Test credit",
        )
        assert line.credit == 500.0

    def test_defaults_to_zero(self):
        """Debit and credit should default to 0.0 when not provided."""
        line = JournalEntryLine(
            line_number=1,
            account_number="1000-100",
            description="Defaults test",
        )
        assert line.debit == 0.0
        assert line.credit == 0.0

    def test_optional_fields(self):
        """account_name and department are optional and default to None."""
        line = JournalEntryLine(
            line_number=1,
            account_number="1000-100",
            description="Optional fields",
        )
        assert line.account_name is None
        assert line.department is None


class TestJournalEntryCreate:
    """Verify WorkOrderCreate (JournalEntryCreate) required fields."""

    def test_missing_required_field_raises(self):
        """Omitting a required field should raise a validation error."""
        with pytest.raises(Exception):
            JournalEntryCreate(
                # missing entry_type, description, period, lines
            )

    def test_valid_create(self):
        """A fully populated create model should succeed."""
        entry = JournalEntryCreate(
            entry_type="accrual",
            description="Test entry",
            period="2026-02",
            lines=[
                JournalEntryLine(
                    line_number=1,
                    account_number="6000-100",
                    debit=100.0,
                    description="Debit side",
                ),
                JournalEntryLine(
                    line_number=2,
                    account_number="2100-100",
                    credit=100.0,
                    description="Credit side",
                ),
            ],
        )
        assert entry.entry_type == "accrual"
        assert len(entry.lines) == 2


class TestEntryStatus:
    """Verify EntryStatus enum contains all expected lifecycle values."""

    def test_expected_values(self):
        """All documented status values should be present in the enum."""
        expected = {
            "draft", "pending_review", "pending_l2_review",
            "pending_l3_review", "approved", "posted",
            "rejected", "reversed",
        }
        actual = {s.value for s in EntryStatus}
        assert expected == actual


class TestApprovalLevel:
    """Verify ApprovalLevel enum values."""

    def test_expected_levels(self):
        """The four approval levels should exist with correct string values."""
        assert ApprovalLevel.AUTO.value == "auto"
        assert ApprovalLevel.L1_MANAGER.value == "l1"
        assert ApprovalLevel.L2_CONTROLLER.value == "l2"
        assert ApprovalLevel.L3_CFO.value == "l3"

    def test_count(self):
        """There should be exactly four approval levels."""
        assert len(ApprovalLevel) == 4


class TestGovernancePolicy:
    """Verify GovernancePolicy default values match documented thresholds."""

    def test_default_thresholds(self):
        """Default materiality thresholds should be $10K, $50K, $250K."""
        policy = GovernancePolicy()
        assert policy.materiality_l1 == 10000.0
        assert policy.materiality_l2 == 50000.0
        assert policy.materiality_l3 == 250000.0

    def test_default_confidence(self):
        """Default confidence threshold should be 0.7."""
        policy = GovernancePolicy()
        assert policy.confidence_threshold == 0.7

    def test_segregation_enabled_by_default(self):
        """Segregation of duties should be enforced by default."""
        policy = GovernancePolicy()
        assert policy.enforce_segregation_of_duties is True

    def test_auto_approve_enabled_by_default(self):
        """Auto-approval below L1 should be enabled by default."""
        policy = GovernancePolicy()
        assert policy.auto_approve_below_l1 is True
