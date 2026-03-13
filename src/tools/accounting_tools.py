"""
============================================================
Accounting Tools
============================================================
These are the tools that agents use to query accounting data
from the simulated ERP/GL system (SQLite).

In production, these functions would call the real ERP API
(NetSuite, SAP, Oracle) or query a data warehouse (Snowflake,
BigQuery). SQLite keeps this project self-contained.

Design decision: These functions are PLAIN functions, not
decorated with @tool. The @tool decorator is applied in
crew.py. This keeps the tools testable and reusable outside
of CrewAI (e.g., in the FastAPI routes or unit tests).

Each function returns a formatted string because CrewAI agents
consume text. The string includes context headers so agents
understand what they're looking at.
============================================================
"""

from src.data.database import (
    get_all_balances,
    get_account_balance,
    get_control_accounts,
    get_journal_entries,
    get_connection,
)


def get_trial_balance(period: str) -> str:
    """
    Retrieve the full trial balance for a close period.

    The trial balance is the starting point for every close.
    It lists every account with its debit or credit balance.
    Total debits must equal total credits (accounting equation).

    Agents use this to:
      - Verify the books are in balance before adjustments
      - Identify accounts that need attention
      - Calculate total assets, liabilities, equity, revenue, expenses

    Args:
        period: Close period in YYYY-MM format (e.g., '2026-02')

    Returns:
        Formatted trial balance with account details and totals
    """
    balances = get_all_balances(period)

    if not balances:
        return f"No account balances found for period {period}."

    # Group accounts by type for readability.
    # Auditors expect trial balances organized by account type.
    grouped = {}
    for b in balances:
        acct_type = b["account_type"]
        if acct_type not in grouped:
            grouped[acct_type] = []
        grouped[acct_type].append(b)

    output = f"TRIAL BALANCE FOR PERIOD {period}\n"
    output += "=" * 80 + "\n\n"

    total_debits = 0.0
    total_credits = 0.0

    # Standard ordering: Assets, Liabilities, Equity, Revenue, Expenses
    type_order = ["asset", "liability", "equity", "revenue", "expense"]
    for acct_type in type_order:
        accounts = grouped.get(acct_type, [])
        if not accounts:
            continue

        output += f"--- {acct_type.upper()} ---\n"
        for a in accounts:
            bal = a["gl_balance"]
            # Debits are positive, credits are negative in our system.
            # Display both columns for clarity.
            if bal >= 0:
                debit_str = f"${bal:>14,.2f}"
                credit_str = " " * 15
                total_debits += bal
            else:
                debit_str = " " * 15
                credit_str = f"${abs(bal):>14,.2f}"
                total_credits += abs(bal)

            output += f"  {a['account_number']}  {a['account_name']:<30s}  DR: {debit_str}  CR: {credit_str}\n"
        output += "\n"

    output += "=" * 80 + "\n"
    output += f"TOTAL DEBITS:  ${total_debits:>14,.2f}\n"
    output += f"TOTAL CREDITS: ${total_credits:>14,.2f}\n"
    difference = total_debits - total_credits
    output += f"DIFFERENCE:    ${difference:>14,.2f}\n"

    if abs(difference) < 0.01:
        output += "\nTrial balance is IN BALANCE.\n"
    else:
        output += f"\nWARNING: Trial balance is OUT OF BALANCE by ${difference:,.2f}\n"

    return output


def get_single_account_balance(account_number: str, period: str) -> str:
    """
    Get detailed balance information for a single account.

    Provides a comprehensive view including GL balance, subledger
    balance, prior period, and budget. The Reconciliation Agent
    uses this to investigate specific discrepancies.

    Args:
        account_number: GL account number (e.g., '1100-100')
        period: Close period in YYYY-MM format

    Returns:
        Formatted account detail with all balance comparisons
    """
    balance = get_account_balance(account_number, period)

    if not balance:
        return f"No balance found for account {account_number} in period {period}."

    output = f"ACCOUNT DETAIL: {balance['account_number']} - {balance['account_name']}\n"
    output += f"Type: {balance['account_type']}\n"
    output += f"Period: {period}\n"
    output += "-" * 50 + "\n"
    output += f"GL Balance:           ${balance['gl_balance']:>14,.2f}\n"

    if balance.get("subledger_balance") is not None:
        output += f"Subledger Balance:    ${balance['subledger_balance']:>14,.2f}\n"
        diff = balance["gl_balance"] - balance["subledger_balance"]
        output += f"GL vs Subledger Diff: ${diff:>14,.2f}\n"
    else:
        output += "Subledger Balance:    N/A (not a control account)\n"

    if balance.get("prior_period_balance") is not None:
        output += f"Prior Period Balance:  ${balance['prior_period_balance']:>14,.2f}\n"
        pp_change = balance["gl_balance"] - balance["prior_period_balance"]
        pp_pct = (pp_change / abs(balance["prior_period_balance"]) * 100) if balance["prior_period_balance"] != 0 else 0
        output += f"Period-over-Period:   ${pp_change:>14,.2f} ({pp_pct:+.1f}%)\n"

    if balance.get("budget_amount") is not None:
        output += f"Budget Amount:        ${balance['budget_amount']:>14,.2f}\n"
        bud_var = balance["gl_balance"] - balance["budget_amount"]
        bud_pct = (bud_var / abs(balance["budget_amount"]) * 100) if balance["budget_amount"] != 0 else 0
        output += f"Budget Variance:      ${bud_var:>14,.2f} ({bud_pct:+.1f}%)\n"

    return output


def get_control_accounts_for_recon(period: str) -> str:
    """
    Get all control accounts that require reconciliation.

    Control accounts are GL accounts backed by a subledger
    (e.g., Cash is backed by the bank statement, AR is backed
    by the customer subledger). These MUST be reconciled every
    month per SOX requirements.

    The Reconciliation Agent uses this to identify which accounts
    need attention and where discrepancies exist.

    Args:
        period: Close period in YYYY-MM format

    Returns:
        Formatted list of control accounts with variance indicators
    """
    accounts = get_control_accounts(period)

    if not accounts:
        return f"No control accounts found for period {period}."

    output = f"CONTROL ACCOUNTS REQUIRING RECONCILIATION - {period}\n"
    output += "=" * 90 + "\n\n"

    needs_investigation = []

    for a in accounts:
        gl = a["gl_balance"]
        sub = a.get("subledger_balance")

        output += f"{a['account_number']}  {a['account_name']}\n"
        output += f"  GL Balance:       ${gl:>14,.2f}\n"

        if sub is not None:
            diff = gl - sub
            pct = (diff / abs(sub) * 100) if sub != 0 else 0
            output += f"  Subledger:        ${sub:>14,.2f}\n"
            output += f"  Difference:       ${diff:>14,.2f} ({pct:+.2f}%)\n"

            # Flag material differences for the agent.
            # Using $100 and 1% as thresholds (matching governance policy defaults).
            if abs(diff) > 100 or abs(pct) > 1.0:
                output += "  STATUS: ** VARIANCE REQUIRES INVESTIGATION **\n"
                needs_investigation.append(a["account_number"])
            else:
                output += "  STATUS: Within tolerance\n"
        else:
            output += "  Subledger:        N/A\n"
            output += "  STATUS: No subledger to reconcile\n"

        output += "\n"

    output += "-" * 90 + "\n"
    output += f"Total control accounts: {len(accounts)}\n"
    output += f"Accounts with variances requiring investigation: {len(needs_investigation)}\n"
    if needs_investigation:
        output += f"Accounts to investigate: {', '.join(needs_investigation)}\n"

    return output


def get_budget_variance(period: str) -> str:
    """
    Calculate budget variance for all accounts in a period.

    Flux analysis (budget vs. actual) is a core SOX requirement.
    Management must explain material variances in financial
    statements. The Variance Analysis Agent uses this data to
    identify and explain significant differences.

    Material variance thresholds (from governance policy):
      - Percentage: >5% from budget
      - Absolute: >$25,000 from budget

    Args:
        period: Close period in YYYY-MM format

    Returns:
        Formatted variance report with material items flagged
    """
    balances = get_all_balances(period)

    if not balances:
        return f"No balances found for period {period}."

    output = f"BUDGET VARIANCE ANALYSIS - {period}\n"
    output += "=" * 90 + "\n\n"

    material_variances = []
    all_variances = []

    for b in balances:
        budget = b.get("budget_amount")
        if budget is None or budget == 0:
            continue

        actual = b["gl_balance"]
        variance = actual - budget
        pct = (variance / abs(budget)) * 100

        is_material = abs(pct) > 5.0 or abs(variance) > 25000

        item = {
            "account": b["account_number"],
            "name": b["account_name"],
            "actual": actual,
            "budget": budget,
            "variance": variance,
            "pct": pct,
            "material": is_material,
        }
        all_variances.append(item)
        if is_material:
            material_variances.append(item)

    # Show material variances first (the ones that matter for SOX)
    if material_variances:
        output += "** MATERIAL VARIANCES (require explanation) **\n"
        output += "-" * 90 + "\n"
        for v in material_variances:
            flag = "OVER" if v["variance"] > 0 else "UNDER"
            output += (
                f"  {v['account']}  {v['name']:<30s}  "
                f"Actual: ${v['actual']:>12,.2f}  Budget: ${v['budget']:>12,.2f}  "
                f"Var: ${v['variance']:>12,.2f} ({v['pct']:+.1f}%) [{flag}]\n"
            )
        output += "\n"

    # Show non-material variances for completeness
    non_material = [v for v in all_variances if not v["material"]]
    if non_material:
        output += "Non-material variances:\n"
        for v in non_material:
            output += (
                f"  {v['account']}  {v['name']:<30s}  "
                f"Var: ${v['variance']:>12,.2f} ({v['pct']:+.1f}%)\n"
            )
        output += "\n"

    output += "-" * 90 + "\n"
    output += f"Total accounts analyzed: {len(all_variances)}\n"
    output += f"Material variances: {len(material_variances)}\n"

    return output


def get_journal_entries_for_period(period: str, status: str = None) -> str:
    """
    List all journal entries for a close period.

    The Review Agent uses this to verify all entries have been
    properly processed and approved. The Compliance Agent uses
    it to check segregation of duties.

    Args:
        period: Close period in YYYY-MM format
        status: Optional filter (draft, pending_review, approved, posted, rejected)

    Returns:
        Formatted list of journal entries with approval status
    """
    entries = get_journal_entries(period, status)

    if not entries:
        filter_text = f" with status '{status}'" if status else ""
        return f"No journal entries found for period {period}{filter_text}."

    output = f"JOURNAL ENTRIES FOR PERIOD {period}"
    if status:
        output += f" (Status: {status})"
    output += "\n" + "=" * 90 + "\n\n"

    for e in entries:
        output += f"Entry ID: {e['entry_id']}\n"
        output += f"  Type: {e['entry_type']}  |  Status: {e['status']}\n"
        output += f"  Description: {e['description']}\n"
        output += f"  Debits: ${e['total_debits']:,.2f}  |  Credits: ${e['total_credits']:,.2f}  |  Balanced: {bool(e['is_balanced'])}\n"
        output += f"  Materiality: ${e['materiality_amount']:,.2f}  |  Approval Level: {e['approval_level_required']}\n"
        output += f"  Prepared By: {e['prepared_by']}  at {e['prepared_at']}\n"
        if e.get("approved_by"):
            output += f"  Approved By: {e['approved_by']}  at {e.get('approved_at', 'N/A')}\n"
        if e.get("rejection_reason"):
            output += f"  REJECTED: {e['rejection_reason']}\n"
        output += "\n"

    output += f"Total entries: {len(entries)}\n"

    # Summary counts by status
    status_counts = {}
    for e in entries:
        s = e["status"]
        status_counts[s] = status_counts.get(s, 0) + 1
    output += "Status breakdown: " + ", ".join(f"{k}: {v}" for k, v in status_counts.items()) + "\n"

    return output
