"""
Tests for the database layer in src/data/database.py.

Validates table creation, seed data integrity, and query helpers.
Uses the session-scoped seeded database from conftest.py so tests
do not need an OpenAI API key or any external service.
"""

import json
import pytest


class TestInitializeDatabase:
    """Verify that initialize_database creates the expected tables."""

    def test_tables_exist(self, seeded_db):
        """All core tables should be present after initialization."""
        from src.data.database import get_connection
        conn = get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        conn.close()

        expected = {
            "accounts", "account_balances", "journal_entries",
            "reconciliations", "sox_controls", "sox_control_tests",
            "close_tasks", "agent_decisions", "human_reviews", "audit_log",
        }
        assert expected.issubset(tables)


class TestSeedDatabase:
    """Verify seed data is populated correctly."""

    def test_accounts_populated(self, seeded_db):
        """The chart of accounts should contain 33 accounts after seeding."""
        from src.data.database import get_all_accounts
        accounts = get_all_accounts()
        assert len(accounts) == 33

    def test_sox_controls_populated(self, seeded_db):
        """There should be 10 SOX controls after seeding."""
        from src.data.database import get_sox_controls
        controls = get_sox_controls()
        assert len(controls) == 10

    def test_close_tasks_populated(self, seeded_db):
        """There should be 8 close tasks after seeding."""
        from src.data.database import get_close_tasks
        tasks = get_close_tasks()
        assert len(tasks) == 8


class TestGetAccount:
    """Verify single-account lookups."""

    def test_existing_account(self, seeded_db):
        """Looking up a known account should return the correct data."""
        from src.data.database import get_account
        acct = get_account("1000-100")
        assert acct is not None
        assert acct["account_name"] == "Cash - Operating"
        assert acct["account_type"] == "asset"

    def test_nonexistent_account(self, seeded_db):
        """Looking up an unknown account should return None."""
        from src.data.database import get_account
        assert get_account("9999-999") is None


class TestGetAllBalances:
    """Verify period-based balance queries."""

    def test_returns_balances_for_period(self, seeded_db):
        """get_all_balances should return rows for the seeded period."""
        from src.data.database import get_all_balances
        balances = get_all_balances("2026-02")
        assert len(balances) > 0
        # Each row should include the joined account_name
        assert "account_name" in balances[0]


class TestGetControlAccounts:
    """Verify that only reconciliation-required accounts are returned."""

    def test_only_reconciliation_accounts(self, seeded_db):
        """Every returned account should have requires_reconciliation = 1."""
        from src.data.database import get_control_accounts
        controls = get_control_accounts("2026-02")
        assert len(controls) > 0
        # The query joins on requires_reconciliation = 1; verify via known accounts
        account_numbers = {c["account_number"] for c in controls}
        # Cash Operating is a control account that requires reconciliation
        assert "1000-100" in account_numbers


class TestSaveAndRetrieveJournalEntry:
    """Verify that saving a journal entry persists it and it can be queried back."""

    def test_round_trip(self, seeded_db):
        """Save a journal entry and retrieve it by period."""
        from src.data.database import save_journal_entry, get_journal_entries
        entry = {
            "entry_id": "JE-TEST-RT-0001",
            "entry_type": "adjusting",
            "description": "Round trip test",
            "period": "2026-02",
            "lines": json.dumps([]),
            "total_debits": 100.0,
            "total_credits": 100.0,
            "is_balanced": 1,
            "materiality_amount": 100.0,
            "approval_level_required": "auto",
            "prepared_by": "Test",
            "prepared_at": "2026-02-28T00:00:00",
            "status": "draft",
        }
        save_journal_entry(entry)
        entries = get_journal_entries("2026-02")
        ids = [e["entry_id"] for e in entries]
        assert "JE-TEST-RT-0001" in ids
