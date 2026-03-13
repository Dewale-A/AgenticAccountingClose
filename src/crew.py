"""
============================================================
Crew Orchestration
============================================================
This module ties everything together. It:
  1. Creates all 6 agents with their tools
  2. Creates tasks for a specific close period
  3. Runs the sequential pipeline
  4. Passes results through the Governance Engine
  5. Returns the close status

This is the entry point for the agent pipeline. The FastAPI
endpoints call run_close_process() to execute a close.

Sequential Flow:
  Initiate Close -> Data Collection -> Journal Entries ->
  Reconciliation -> Variance Analysis -> Compliance ->
  Review -> Governance Check -> Close Package

Design decision: Tool wrappers use @tool decorator here
(not in the tool modules). This keeps the tool functions
pure and testable while satisfying CrewAI's decorator
requirement. The actual logic lives in accounting_tools.py
and rag_tools.py.
============================================================
"""

import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from crewai import Crew, Process
from crewai.tools import tool

# Load environment variables before any other imports
# that might need OPENAI_API_KEY
load_dotenv()

# Local imports
from src.agents.definitions import (
    create_data_collection_agent,
    create_journal_entry_agent,
    create_reconciliation_agent,
    create_variance_analysis_agent,
    create_compliance_agent,
    create_review_agent,
)
from src.tasks.definitions import (
    create_data_collection_task,
    create_journal_entry_task,
    create_reconciliation_task,
    create_variance_analysis_task,
    create_compliance_task,
    create_review_task,
)
from src.tools.accounting_tools import (
    get_trial_balance,
    get_single_account_balance,
    get_control_accounts_for_recon,
    get_budget_variance,
    get_journal_entries_for_period,
)
from src.tools.rag_tools import search_accounting_docs, get_document_list
from src.governance.engine import GovernanceEngine
from src.governance.sox_controls import SOXControlsEngine
from src.data.database import seed_database, get_connection


# ============================================================
# TOOL WRAPPERS
# ============================================================
# CrewAI requires tools to be decorated with @tool.
# These wrappers are thin: they just call the underlying
# function and add the decorator. The real logic stays in
# the tool modules for testability and reuse.


@tool("Get Trial Balance")
def get_trial_balance_tool(period: str) -> str:
    """Retrieve the full trial balance for a close period. Returns all
    account balances organized by type (assets, liabilities, equity,
    revenue, expenses) with total debits and credits."""
    return get_trial_balance(period)


@tool("Get Account Balance")
def get_account_balance_tool(account_number: str, period: str) -> str:
    """Get detailed balance information for a single GL account including
    GL balance, subledger balance, prior period, and budget comparison.
    Use this to investigate specific accounts."""
    return get_single_account_balance(account_number, period)


@tool("Get Control Accounts for Reconciliation")
def get_control_accounts_tool(period: str) -> str:
    """Get all control accounts that require reconciliation for the period.
    Shows GL vs subledger balance and flags accounts with material
    discrepancies that need investigation."""
    return get_control_accounts_for_recon(period)


@tool("Get Budget Variance Report")
def get_budget_variance_tool(period: str) -> str:
    """Calculate and display budget variance (flux analysis) for all
    accounts. Flags material variances exceeding 5% or $25,000 from
    budget. Used for management discussion and SOX compliance."""
    return get_budget_variance(period)


@tool("Get Journal Entries")
def get_journal_entries_tool(period: str) -> str:
    """List all journal entries for a close period with their approval
    status, amounts, and audit trail. Use this to verify entries are
    properly processed and approved."""
    return get_journal_entries_for_period(period)


@tool("Search Accounting Documentation")
def search_accounting_docs_tool(query: str) -> str:
    """Search accounting policy documents, SOX compliance guides, and
    close procedures using semantic search. Use natural language queries
    like 'revenue recognition cutoff rules' or 'SOX journal entry
    approval requirements'."""
    return search_accounting_docs(query)


@tool("List Available Documents")
def get_document_list_tool() -> str:
    """List all available accounting documents in the knowledge base.
    Useful for discovering what documentation exists before searching."""
    return get_document_list()


# ============================================================
# CREW BUILDER
# ============================================================

def run_close_process(period: str) -> dict:
    """
    Run the full month-end close process for a given period.

    This is the main orchestration function. It:
      1. Seeds the database with sample data (first run only)
      2. Creates agents with appropriate tools
      3. Creates tasks parameterized by close period
      4. Runs the CrewAI sequential pipeline
      5. Runs SOX control tests via the compliance engine
      6. Logs all decisions to the governance audit trail
      7. Returns the close results

    Args:
        period: Close period in YYYY-MM format (e.g., '2026-02')

    Returns:
        Dictionary with close results, including agent outputs,
        SOX test results, and governance status
    """
    # Ensure database is seeded with sample data
    seed_database()

    # Initialize engines
    governance = GovernanceEngine()
    sox_engine = SOXControlsEngine()

    # ---- Configure LLM ----
    model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini")

    # ---- Create Agents ----
    # Each agent gets only the tools it needs.
    # This follows the principle of least privilege:
    # agents should not have access to tools they don't need.

    data_agent = create_data_collection_agent(llm=model_name)
    data_agent.tools = [
        get_trial_balance_tool,
        get_control_accounts_tool,
        get_account_balance_tool,
    ]

    je_agent = create_journal_entry_agent(llm=model_name)
    je_agent.tools = [
        get_trial_balance_tool,
        get_account_balance_tool,
        search_accounting_docs_tool,
    ]

    recon_agent = create_reconciliation_agent(llm=model_name)
    recon_agent.tools = [
        get_control_accounts_tool,
        get_account_balance_tool,
        search_accounting_docs_tool,
    ]

    variance_agent = create_variance_analysis_agent(llm=model_name)
    variance_agent.tools = [
        get_budget_variance_tool,
        get_account_balance_tool,
        search_accounting_docs_tool,
    ]

    compliance_agent = create_compliance_agent(llm=model_name)
    compliance_agent.tools = [
        get_journal_entries_tool,
        get_control_accounts_tool,
        search_accounting_docs_tool,
    ]

    review_agent = create_review_agent(llm=model_name)
    review_agent.tools = [
        get_journal_entries_tool,
        get_trial_balance_tool,
        get_control_accounts_tool,
    ]

    # ---- Create Tasks ----
    # Tasks are parameterized by the close period so agents know
    # which month they are closing.
    data_task = create_data_collection_task(data_agent, period)
    je_task = create_journal_entry_task(je_agent, period)
    recon_task = create_reconciliation_task(recon_agent, period)
    variance_task = create_variance_analysis_task(variance_agent, period)
    compliance_task = create_compliance_task(compliance_agent, period)
    review_task = create_review_task(review_agent, period)

    # ---- Build and Run Crew ----
    # Sequential process: each task runs after the previous one completes.
    # The output of each task is available as context to subsequent agents.
    crew = Crew(
        agents=[
            data_agent,
            je_agent,
            recon_agent,
            variance_agent,
            compliance_agent,
            review_agent,
        ],
        tasks=[
            data_task,
            je_task,
            recon_task,
            variance_task,
            compliance_task,
            review_task,
        ],
        process=Process.sequential,
        verbose=True,
    )

    print(f"\n{'='*60}")
    print(f"Month-End Close Process: {period}")
    print(f"{'='*60}\n")

    # Run the crew pipeline
    result = crew.kickoff()
    result_text = str(result)

    # ---- Run SOX Control Tests ----
    # These run against actual data in the database to verify
    # controls are operating effectively.
    sox_results = sox_engine.run_all_tests(period)

    # ---- Log Governance Decisions ----
    # Record that the close process was executed with all results.
    governance.log_decision(
        period=period,
        agent_name="Close Orchestrator",
        decision_type="close_process_completed",
        decision_value="complete",
        reasoning=f"Full close pipeline executed for period {period}. "
                  f"6 agents processed sequentially. SOX controls tested.",
        confidence=0.85,
        data_sources=["trial_balance", "journal_entries", "reconciliations", "sox_tests"],
    )

    # ---- Update Close Tasks ----
    # Mark the close tasks as completed in the database
    _update_close_task_status(period)

    # Count SOX test results
    sox_passed = sum(1 for r in sox_results if r["result"] == "pass")
    sox_failed = sum(1 for r in sox_results if r["result"] == "fail")

    print(f"\n{'='*60}")
    print(f"Close Process Complete: {period}")
    print(f"SOX Controls: {sox_passed} passed, {sox_failed} failed")
    print(f"{'='*60}\n")

    return {
        "period": period,
        "status": "complete",
        "agent_output": result_text,
        "sox_test_results": sox_results,
        "sox_summary": {
            "total_tests": len(sox_results),
            "passed": sox_passed,
            "failed": sox_failed,
        },
        "timestamp": datetime.now().isoformat(),
    }


def _update_close_task_status(period: str):
    """
    Mark close tasks as completed in the database.

    This updates the close checklist to reflect that the
    agent pipeline has run. In production, each agent would
    update its own tasks in real-time.
    """
    conn = get_connection()
    now = datetime.now().isoformat()

    # Mark all tasks assigned to agents as completed
    agent_tasks = [
        "Data Collection Agent",
        "Journal Entry Agent",
        "Reconciliation Agent",
        "Variance Analysis Agent",
        "Compliance Agent",
        "Review Agent",
    ]

    for agent_name in agent_tasks:
        conn.execute(
            "UPDATE close_tasks SET status = 'completed', completed_at = ? "
            "WHERE assigned_to = ? AND status != 'completed'",
            (now, agent_name)
        )

    conn.commit()
    conn.close()
