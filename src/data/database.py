"""
============================================================
Database Layer (SQLite)
============================================================
Simulates an ERP/GL system (like NetSuite, SAP, or Snowflake).

In production, you'd connect to the actual ERP via API or
query Snowflake/data warehouse directly. SQLite keeps this
project self-contained and runnable without external systems.

The database stores:
  - Chart of accounts (GL accounts)
  - Account balances (current, prior, budget)
  - Journal entries with full approval chain
  - Reconciliations
  - SOX controls and test results
  - Agent decisions (audit trail)
  - Human reviews
  - Audit log

Every table includes audit columns because in a SOX
environment, you must track who changed what and when.
============================================================
"""

import sqlite3
import json
import os
from pathlib import Path

DB_PATH = os.environ.get(
    "DATABASE_PATH",
    str(Path(__file__).parent / "accounting.db")
)


def get_connection() -> sqlite3.Connection:
    """Create a database connection with row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # ---- Chart of Accounts ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account_number TEXT PRIMARY KEY,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            department TEXT NOT NULL,
            is_control_account INTEGER DEFAULT 0,
            requires_reconciliation INTEGER DEFAULT 0
        )
    """)

    # ---- Account Balances ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT NOT NULL,
            period TEXT NOT NULL,
            gl_balance REAL NOT NULL,
            subledger_balance REAL,
            prior_period_balance REAL,
            budget_amount REAL,
            FOREIGN KEY (account_number) REFERENCES accounts (account_number),
            UNIQUE(account_number, period)
        )
    """)

    # ---- Journal Entries ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            entry_id TEXT PRIMARY KEY,
            entry_type TEXT NOT NULL,
            description TEXT NOT NULL,
            period TEXT NOT NULL,
            lines TEXT NOT NULL,
            total_debits REAL NOT NULL,
            total_credits REAL NOT NULL,
            is_balanced INTEGER NOT NULL,
            materiality_amount REAL NOT NULL,
            approval_level_required TEXT NOT NULL,
            prepared_by TEXT NOT NULL,
            prepared_at TEXT NOT NULL,
            reviewed_by TEXT,
            reviewed_at TEXT,
            approved_by TEXT,
            approved_at TEXT,
            posted_by TEXT,
            posted_at TEXT,
            supporting_documentation TEXT,
            source_system TEXT,
            agent_reasoning TEXT,
            confidence_score REAL,
            status TEXT DEFAULT 'draft',
            rejection_reason TEXT
        )
    """)

    # ---- Reconciliations ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reconciliations (
            recon_id TEXT PRIMARY KEY,
            account_number TEXT NOT NULL,
            account_name TEXT NOT NULL,
            period TEXT NOT NULL,
            gl_balance REAL NOT NULL,
            subledger_balance REAL NOT NULL,
            difference REAL NOT NULL,
            difference_pct REAL NOT NULL,
            reconciling_items TEXT DEFAULT '[]',
            explained_amount REAL DEFAULT 0,
            unexplained_amount REAL DEFAULT 0,
            prepared_by TEXT NOT NULL,
            prepared_at TEXT NOT NULL,
            reviewed_by TEXT,
            reviewed_at TEXT,
            status TEXT DEFAULT 'not_started',
            agent_reasoning TEXT,
            confidence_score REAL
        )
    """)

    # ---- SOX Controls ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sox_controls (
            control_id TEXT PRIMARY KEY,
            control_name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            risk_addressed TEXT NOT NULL,
            control_type TEXT NOT NULL,
            frequency TEXT NOT NULL,
            owner TEXT NOT NULL,
            last_tested TEXT,
            test_result TEXT,
            test_evidence TEXT,
            deficiency_noted TEXT
        )
    """)

    # ---- SOX Control Tests ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sox_control_tests (
            test_id TEXT PRIMARY KEY,
            control_id TEXT NOT NULL,
            period TEXT NOT NULL,
            tested_by TEXT NOT NULL,
            tested_at TEXT NOT NULL,
            result TEXT NOT NULL,
            evidence TEXT NOT NULL,
            sample_size INTEGER,
            exceptions_found INTEGER DEFAULT 0,
            conclusion TEXT NOT NULL,
            FOREIGN KEY (control_id) REFERENCES sox_controls (control_id)
        )
    """)

    # ---- Close Tasks ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS close_tasks (
            task_id TEXT PRIMARY KEY,
            task_name TEXT NOT NULL,
            description TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            depends_on TEXT DEFAULT '[]',
            assigned_to TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            due_date TEXT,
            completed_at TEXT,
            notes TEXT
        )
    """)

    # ---- Agent Decisions (Audit Trail) ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_decisions (
            decision_id TEXT PRIMARY KEY,
            close_period TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            decision_value TEXT NOT NULL,
            reasoning TEXT NOT NULL,
            confidence REAL NOT NULL,
            data_sources TEXT DEFAULT '[]',
            affected_accounts TEXT DEFAULT '[]',
            dollar_impact REAL,
            timestamp TEXT NOT NULL
        )
    """)

    # ---- Human Reviews ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS human_reviews (
            review_id TEXT PRIMARY KEY,
            entry_id TEXT,
            recon_id TEXT,
            escalation_reason TEXT NOT NULL,
            approval_level TEXT NOT NULL,
            agent_recommendation TEXT NOT NULL,
            reviewer_name TEXT,
            reviewer_title TEXT,
            status TEXT DEFAULT 'pending',
            reviewer_notes TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # ---- Audit Log ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            entry_id TEXT PRIMARY KEY,
            close_period TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_detail TEXT NOT NULL,
            actor TEXT NOT NULL,
            actor_role TEXT,
            affected_entity TEXT,
            dollar_impact REAL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def seed_database():
    """
    Populate with realistic month-end close data.
    
    Creates a complete chart of accounts for a mid-size company
    with balances that have intentional discrepancies for the
    agents to find and reconcile.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # ============================================================
    # CHART OF ACCOUNTS
    # ============================================================
    accounts = [
        # Assets
        ("1000-100", "Cash - Operating", "asset", "Treasury", 1, 1),
        ("1000-200", "Cash - Payroll", "asset", "Treasury", 1, 1),
        ("1100-100", "Accounts Receivable", "asset", "Revenue", 1, 1),
        ("1200-100", "Prepaid Insurance", "asset", "Finance", 0, 1),
        ("1200-200", "Prepaid Rent", "asset", "Finance", 0, 1),
        ("1300-100", "Inventory", "asset", "Operations", 1, 1),
        ("1500-100", "Property and Equipment", "asset", "Finance", 0, 0),
        ("1500-200", "Accumulated Depreciation", "asset", "Finance", 0, 0),
        
        # Liabilities
        ("2000-100", "Accounts Payable", "liability", "Procurement", 1, 1),
        ("2100-100", "Accrued Salaries", "liability", "HR", 0, 1),
        ("2100-200", "Accrued Benefits", "liability", "HR", 0, 1),
        ("2200-100", "Deferred Revenue", "liability", "Revenue", 0, 1),
        ("2300-100", "Income Tax Payable", "liability", "Tax", 0, 1),
        ("2400-100", "Line of Credit", "liability", "Treasury", 0, 0),
        ("2500-100", "Long-Term Debt", "liability", "Treasury", 0, 0),
        
        # Equity
        ("3000-100", "Common Stock", "equity", "Finance", 0, 0),
        ("3100-100", "Retained Earnings", "equity", "Finance", 0, 0),
        
        # Revenue
        ("4000-100", "Product Revenue", "revenue", "Sales", 0, 0),
        ("4000-200", "Service Revenue", "revenue", "Sales", 0, 0),
        ("4100-100", "Other Revenue", "revenue", "Finance", 0, 0),
        
        # Expenses
        ("5000-100", "Cost of Goods Sold", "expense", "Operations", 0, 0),
        ("6000-100", "Salaries and Wages", "expense", "HR", 0, 0),
        ("6000-200", "Employee Benefits", "expense", "HR", 0, 0),
        ("6100-100", "Rent Expense", "expense", "Facilities", 0, 0),
        ("6200-100", "Utilities", "expense", "Facilities", 0, 0),
        ("6300-100", "Depreciation Expense", "expense", "Finance", 0, 0),
        ("6400-100", "Insurance Expense", "expense", "Finance", 0, 0),
        ("6500-100", "Professional Fees", "expense", "Finance", 0, 0),
        ("6600-100", "Marketing Expense", "expense", "Marketing", 0, 0),
        ("6700-100", "IT and Software", "expense", "IT", 0, 0),
        ("6800-100", "Travel and Entertainment", "expense", "Finance", 0, 0),
        ("7000-100", "Interest Expense", "expense", "Treasury", 0, 0),
        ("8000-100", "Income Tax Expense", "expense", "Tax", 0, 0),
    ]

    cursor.executemany("""
        INSERT INTO accounts (account_number, account_name, account_type,
                            department, is_control_account, requires_reconciliation)
        VALUES (?, ?, ?, ?, ?, ?)
    """, accounts)

    # ============================================================
    # ACCOUNT BALANCES (February 2026 close period)
    # ============================================================
    # Intentional discrepancies between GL and subledger for agents to find:
    # - Cash Operating: GL/bank difference of $3,245 (outstanding checks)
    # - Accounts Receivable: $12,500 variance (unapplied payment)
    # - Accounts Payable: $8,750 variance (unprocessed invoices)
    # - Inventory: $5,200 variance (count adjustment needed)
    
    balances = [
        # account_number, period, gl_balance, subledger, prior_period, budget
        # Assets
        ("1000-100", "2026-02", 2847500.00, 2844255.00, 2615000.00, 2800000.00),
        ("1000-200", "2026-02", 185000.00, 185000.00, 175000.00, 180000.00),
        ("1100-100", "2026-02", 1425000.00, 1412500.00, 1380000.00, 1400000.00),
        ("1200-100", "2026-02", 48000.00, None, 52000.00, 48000.00),
        ("1200-200", "2026-02", 75000.00, None, 75000.00, 75000.00),
        ("1300-100", "2026-02", 892000.00, 886800.00, 845000.00, 900000.00),
        ("1500-100", "2026-02", 3200000.00, None, 3200000.00, 3200000.00),
        ("1500-200", "2026-02", -1280000.00, None, -1253333.00, -1280000.00),
        
        # Liabilities (negative = credit balance)
        ("2000-100", "2026-02", -685000.00, -693750.00, -620000.00, -650000.00),
        ("2100-100", "2026-02", -245000.00, None, -238000.00, -240000.00),
        ("2100-200", "2026-02", -82000.00, None, -78000.00, -80000.00),
        ("2200-100", "2026-02", -320000.00, None, -285000.00, -300000.00),
        ("2300-100", "2026-02", -125000.00, None, -118000.00, -120000.00),
        ("2400-100", "2026-02", -500000.00, None, -500000.00, -500000.00),
        ("2500-100", "2026-02", -2000000.00, None, -2000000.00, -2000000.00),
        
        # Equity
        ("3000-100", "2026-02", -1000000.00, None, -1000000.00, -1000000.00),
        ("3100-100", "2026-02", -2850000.00, None, -2850000.00, -2850000.00),
        
        # Revenue (negative = credit)
        ("4000-100", "2026-02", -1850000.00, None, -1720000.00, -1900000.00),
        ("4000-200", "2026-02", -625000.00, None, -580000.00, -650000.00),
        ("4100-100", "2026-02", -15000.00, None, -12000.00, -10000.00),
        
        # Expenses (positive = debit)
        ("5000-100", "2026-02", 925000.00, None, 860000.00, 950000.00),
        ("6000-100", "2026-02", 485000.00, None, 470000.00, 480000.00),
        ("6000-200", "2026-02", 121250.00, None, 117500.00, 120000.00),
        ("6100-100", "2026-02", 75000.00, None, 75000.00, 75000.00),
        ("6200-100", "2026-02", 18500.00, None, 16800.00, 17000.00),
        ("6300-100", "2026-02", 26667.00, None, 26667.00, 26667.00),
        ("6400-100", "2026-02", 4000.00, None, 4000.00, 4000.00),
        ("6500-100", "2026-02", 35000.00, None, 28000.00, 30000.00),
        ("6600-100", "2026-02", 78000.00, None, 65000.00, 70000.00),
        ("6700-100", "2026-02", 42000.00, None, 38000.00, 40000.00),
        ("6800-100", "2026-02", 22000.00, None, 18000.00, 15000.00),
        ("7000-100", "2026-02", 12500.00, None, 12500.00, 12500.00),
        ("8000-100", "2026-02", 95000.00, None, 88000.00, 92000.00),
    ]

    cursor.executemany("""
        INSERT INTO account_balances (account_number, period, gl_balance,
                                     subledger_balance, prior_period_balance, budget_amount)
        VALUES (?, ?, ?, ?, ?, ?)
    """, balances)

    # ============================================================
    # SOX CONTROLS
    # ============================================================
    sox_controls = [
        ("SOX-JE-001", "Journal Entry Authorization",
         "All journal entries above materiality threshold require appropriate level approval before posting to GL",
         "journal_entry", "Unauthorized or erroneous journal entries posted to GL",
         "preventive", "monthly", "Controller"),
        
        ("SOX-JE-002", "Journal Entry Segregation of Duties",
         "The person who prepares a journal entry cannot be the same person who approves or posts it",
         "segregation", "Fraud risk from single individual controlling entire transaction",
         "preventive", "monthly", "Controller"),
        
        ("SOX-JE-003", "Non-Standard Journal Entry Review",
         "All manual, non-recurring, and top-side journal entries are reviewed by management",
         "journal_entry", "Material misstatement from unusual or non-routine entries",
         "detective", "monthly", "Controller"),
        
        ("SOX-REC-001", "Account Reconciliation Completeness",
         "All control accounts are reconciled monthly with variances investigated and resolved",
         "reconciliation", "Undetected errors or fraud in account balances",
         "detective", "monthly", "Accounting Manager"),
        
        ("SOX-REC-002", "Reconciliation Review and Approval",
         "All reconciliations are reviewed by someone other than the preparer",
         "reconciliation", "Errors in reconciliation not detected by independent review",
         "detective", "monthly", "Accounting Manager"),
        
        ("SOX-REC-003", "Timely Reconciliation Completion",
         "All reconciliations completed within 5 business days of period end",
         "reconciliation", "Delayed detection of errors impacting financial statements",
         "detective", "monthly", "Accounting Manager"),
        
        ("SOX-VAR-001", "Flux Analysis Review",
         "Material variances from budget or prior period are investigated and explained by management",
         "reporting", "Unexplained material changes in financial statements",
         "detective", "monthly", "FP&A Manager"),
        
        ("SOX-ACC-001", "System Access Controls",
         "Access to post journal entries is restricted to authorized personnel only",
         "access", "Unauthorized posting of journal entries",
         "preventive", "quarterly", "IT Manager"),
        
        ("SOX-CLS-001", "Close Checklist Completion",
         "All month-end close tasks are completed and signed off before financial statements are finalized",
         "reporting", "Incomplete close process leading to material misstatement",
         "detective", "monthly", "Controller"),
        
        ("SOX-CLS-002", "Management Review of Financial Statements",
         "CFO reviews and approves final financial statements before external reporting",
         "reporting", "Material misstatement in externally reported financials",
         "detective", "monthly", "CFO"),
    ]

    cursor.executemany("""
        INSERT INTO sox_controls (control_id, control_name, description, category,
                                 risk_addressed, control_type, frequency, owner)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, sox_controls)

    # ============================================================
    # CLOSE TASKS (Month-End Checklist)
    # ============================================================
    close_tasks = [
        ("TASK-001", "Collect Subledger Balances", "Extract balances from all subledger systems (AP, AR, Inventory, Payroll)", 1, "[]", "Data Collection Agent"),
        ("TASK-002", "Prepare Adjusting Entries", "Create adjusting entries for accruals, deferrals, and reclassifications", 2, '["TASK-001"]', "Journal Entry Agent"),
        ("TASK-003", "Reconcile Control Accounts", "Reconcile all control accounts (Cash, AR, AP, Inventory) to subledgers", 3, '["TASK-001"]', "Reconciliation Agent"),
        ("TASK-004", "Post Approved Entries", "Post all approved journal entries to the general ledger", 4, '["TASK-002"]', "Journal Entry Agent"),
        ("TASK-005", "Perform Flux Analysis", "Analyze variances between actuals, budget, and prior period", 5, '["TASK-004"]', "Variance Analysis Agent"),
        ("TASK-006", "Test SOX Controls", "Execute SOX control testing for the close period", 6, '["TASK-002", "TASK-003"]', "Compliance Agent"),
        ("TASK-007", "Prepare Close Package", "Compile all close documentation for management review", 7, '["TASK-003", "TASK-004", "TASK-005", "TASK-006"]', "Review Agent"),
        ("TASK-008", "Management Sign-Off", "Controller and CFO review and sign off on close package", 8, '["TASK-007"]', "Human (Controller/CFO)"),
    ]

    cursor.executemany("""
        INSERT INTO close_tasks (task_id, task_name, description, sequence,
                                depends_on, assigned_to)
        VALUES (?, ?, ?, ?, ?, ?)
    """, close_tasks)

    conn.commit()
    conn.close()
    print(f"Accounting database seeded successfully at {DB_PATH}")


# ============================================================
# QUERY HELPERS
# ============================================================

def get_account(account_number: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM accounts WHERE account_number = ?", (account_number,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_accounts() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM accounts ORDER BY account_number").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account_balance(account_number: str, period: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT ab.*, a.account_name, a.account_type FROM account_balances ab "
        "JOIN accounts a ON ab.account_number = a.account_number "
        "WHERE ab.account_number = ? AND ab.period = ?",
        (account_number, period)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_balances(period: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT ab.*, a.account_name, a.account_type, a.is_control_account, "
        "a.requires_reconciliation FROM account_balances ab "
        "JOIN accounts a ON ab.account_number = a.account_number "
        "WHERE ab.period = ? ORDER BY ab.account_number",
        (period,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_control_accounts(period: str) -> list[dict]:
    """Get accounts that require reconciliation."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT ab.*, a.account_name, a.account_type FROM account_balances ab "
        "JOIN accounts a ON ab.account_number = a.account_number "
        "WHERE a.requires_reconciliation = 1 AND ab.period = ? "
        "ORDER BY ab.account_number",
        (period,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sox_controls() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM sox_controls ORDER BY control_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_close_tasks() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM close_tasks ORDER BY sequence").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_journal_entry(entry: dict):
    conn = get_connection()
    if isinstance(entry.get("lines"), list):
        entry["lines"] = json.dumps([l if isinstance(l, dict) else l for l in entry["lines"]])
    columns = ", ".join(entry.keys())
    placeholders = ", ".join(["?" for _ in entry])
    conn.execute(f"INSERT OR REPLACE INTO journal_entries ({columns}) VALUES ({placeholders})",
                 list(entry.values()))
    conn.commit()
    conn.close()


def save_reconciliation(recon: dict):
    conn = get_connection()
    if isinstance(recon.get("reconciling_items"), list):
        recon["reconciling_items"] = json.dumps(recon["reconciling_items"])
    columns = ", ".join(recon.keys())
    placeholders = ", ".join(["?" for _ in recon])
    conn.execute(f"INSERT OR REPLACE INTO reconciliations ({columns}) VALUES ({placeholders})",
                 list(recon.values()))
    conn.commit()
    conn.close()


def save_agent_decision(decision: dict):
    conn = get_connection()
    for key in ["data_sources", "affected_accounts"]:
        if isinstance(decision.get(key), list):
            decision[key] = json.dumps(decision[key])
    columns = ", ".join(decision.keys())
    placeholders = ", ".join(["?" for _ in decision])
    conn.execute(f"INSERT INTO agent_decisions ({columns}) VALUES ({placeholders})",
                 list(decision.values()))
    conn.commit()
    conn.close()


def save_audit_log(entry: dict):
    conn = get_connection()
    columns = ", ".join(entry.keys())
    placeholders = ", ".join(["?" for _ in entry])
    conn.execute(f"INSERT INTO audit_log ({columns}) VALUES ({placeholders})",
                 list(entry.values()))
    conn.commit()
    conn.close()


def get_journal_entries(period: str, status: str = None) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM journal_entries WHERE period = ?"
    params = [period]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY prepared_at"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_reviews() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM human_reviews WHERE status = 'pending'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_audit_trail(period: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM agent_decisions WHERE close_period = ? ORDER BY timestamp",
        (period,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize on import
initialize_database()
