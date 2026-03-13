"""
============================================================
FastAPI Routes
============================================================
REST API endpoints for the Month-End Close Assistant.

Endpoints are organized into groups:
  - Close Management:  Initiate and monitor close processes
  - Journal Entries:   CRUD + approval workflow for JEs
  - Reconciliations:   View and certify account reconciliations
  - Variance Analysis: Budget vs. actual reporting
  - Human Reviews:     HITL approval queue
  - Governance:        Audit trail, dashboard, SOX controls
  - System:            Health check

Design decisions:
  - POST /close/initiate runs the agent pipeline asynchronously
    because it can take 30-60 seconds. The caller gets an
    immediate 202 response and polls /close/status for progress.
  - All approval endpoints enforce segregation of duties.
    The system rejects approvals where preparer == approver.
  - Every mutation is logged to the audit trail.
============================================================
"""

import uuid
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks

from src.crew import run_close_process
from src.governance.engine import GovernanceEngine
from src.governance.sox_controls import SOXControlsEngine
from src.models.schemas import JournalEntryCreate, ApprovalLevel, EntryStatus
from src.data.database import (
    get_connection,
    get_journal_entries,
    get_pending_reviews,
    get_audit_trail,
    get_sox_controls,
    get_close_tasks,
    get_all_balances,
    get_control_accounts,
    save_journal_entry,
    save_reconciliation,
    seed_database,
    initialize_database,
)


# ============================================================
# APP INITIALIZATION
# ============================================================

app = FastAPI(
    title="Agentic Accounting Close Assistant",
    description=(
        "AI-powered month-end close system with SOX-compliant governance, "
        "segregation of duties, and human-in-the-loop controls. "
        "6 specialized AI agents handle data collection, journal entries, "
        "reconciliation, variance analysis, compliance testing, and review. "
        "Every decision is logged to an immutable audit trail."
    ),
    version="1.0.0",
)

# Initialize and seed database on startup.
# This ensures the simulated ERP data is available
# before any requests arrive.
initialize_database()
seed_database()

# Shared governance engine instance.
# All endpoints use the same engine so policies are consistent.
governance_engine = GovernanceEngine()

# Track close process status in memory.
# In production, you would use a proper job queue (Celery, Redis).
_close_status = {}


# ============================================================
# CLOSE MANAGEMENT ENDPOINTS
# ============================================================

@app.post("/close/initiate", status_code=202)
async def initiate_close(period: str, background_tasks: BackgroundTasks):
    """
    Start the month-end close process for a given period.

    Accepted immediately (202) and processed asynchronously
    because the agent pipeline takes 30-60 seconds. Use
    GET /close/status to monitor progress.

    Args:
        period: Close period in YYYY-MM format (e.g., '2026-02')
    """
    if period in _close_status and _close_status[period].get("status") == "in_progress":
        raise HTTPException(
            status_code=409,
            detail=f"Close process already in progress for {period}"
        )

    _close_status[period] = {
        "status": "in_progress",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "result": None,
    }

    # Run the full agent pipeline in the background.
    # FastAPI's BackgroundTasks ensures the response returns immediately.
    background_tasks.add_task(_run_close_background, period)

    return {
        "message": f"Close process initiated for period {period}",
        "status": "in_progress",
        "check_status": f"GET /close/status?period={period}",
    }


async def _run_close_background(period: str):
    """Background task that runs the full agent pipeline."""
    try:
        result = run_close_process(period)
        _close_status[period] = {
            "status": "complete",
            "started_at": _close_status[period]["started_at"],
            "completed_at": datetime.now().isoformat(),
            "result": result,
        }
    except Exception as e:
        _close_status[period] = {
            "status": "error",
            "started_at": _close_status[period]["started_at"],
            "completed_at": datetime.now().isoformat(),
            "error": str(e),
        }


@app.get("/close/status")
async def get_close_status(period: Optional[str] = None):
    """
    Get the status of the close process.

    Returns progress for a specific period or all periods.
    Includes close task checklist with completion status.
    """
    if period:
        status = _close_status.get(period)
        if not status:
            # Check if we have close tasks in the database
            tasks = get_close_tasks()
            return {
                "period": period,
                "status": "not_started",
                "close_tasks": tasks,
            }
        result = {"period": period, **status}
        result["close_tasks"] = get_close_tasks()
        return result

    return {
        "periods": _close_status,
        "close_tasks": get_close_tasks(),
    }


@app.get("/close/package")
async def get_close_package(period: str = "2026-02"):
    """
    Generate the close package summary.

    The close package is the final deliverable: a comprehensive
    summary of everything that happened during the close.
    This is what the Controller and CFO review before sign-off.
    """
    conn = get_connection()

    # Journal entry summary
    entries = conn.execute(
        "SELECT status, COUNT(*) as count, SUM(total_debits) as total_dr, "
        "SUM(total_credits) as total_cr FROM journal_entries "
        "WHERE period = ? GROUP BY status",
        (period,)
    ).fetchall()

    je_summary = {row["status"]: {"count": row["count"], "total_debits": row["total_dr"],
                                   "total_credits": row["total_cr"]} for row in entries}

    # Reconciliation summary
    recons = conn.execute(
        "SELECT status, COUNT(*) as count FROM reconciliations "
        "WHERE period = ? GROUP BY status",
        (period,)
    ).fetchall()
    recon_summary = {row["status"]: row["count"] for row in recons}

    # SOX test results
    sox_tests = conn.execute(
        "SELECT control_id, result, conclusion FROM sox_control_tests "
        "WHERE period = ? ORDER BY control_id",
        (period,)
    ).fetchall()

    # Audit trail count
    audit_count = conn.execute(
        "SELECT COUNT(*) FROM agent_decisions WHERE close_period = ?",
        (period,)
    ).fetchone()[0]

    # Open items (pending reviews)
    open_items = conn.execute(
        "SELECT COUNT(*) FROM human_reviews WHERE status = 'pending'"
    ).fetchone()[0]

    conn.close()

    return {
        "period": period,
        "generated_at": datetime.now().isoformat(),
        "journal_entries": je_summary,
        "reconciliations": recon_summary,
        "sox_control_tests": [dict(r) for r in sox_tests],
        "audit_trail_entries": audit_count,
        "open_items_pending_review": open_items,
        "close_tasks": get_close_tasks(),
    }


# ============================================================
# JOURNAL ENTRY ENDPOINTS
# ============================================================

@app.post("/journal-entries")
async def create_journal_entry(entry: JournalEntryCreate):
    """
    Submit a new journal entry.

    The entry goes through the governance engine's materiality
    gate to determine the required approval level. Entries below
    the L1 threshold are auto-approved with full audit trail.
    Entries above are routed to the appropriate human reviewer.
    """
    # Calculate totals from the entry lines
    total_debits = sum(line.debit for line in entry.lines)
    total_credits = sum(line.credit for line in entry.lines)
    is_balanced = abs(total_debits - total_credits) < 0.01
    materiality = max(total_debits, total_credits)

    # Determine approval level using the governance engine
    approval_level = governance_engine.get_approval_level(materiality)

    # Build the entry record for storage
    entry_id = f"JE-{entry.period}-{uuid.uuid4().hex[:4].upper()}"
    now = datetime.now().isoformat()

    entry_dict = {
        "entry_id": entry_id,
        "entry_type": entry.entry_type,
        "description": entry.description,
        "period": entry.period,
        "lines": json.dumps([line.model_dump() for line in entry.lines]),
        "total_debits": total_debits,
        "total_credits": total_credits,
        "is_balanced": 1 if is_balanced else 0,
        "materiality_amount": materiality,
        "approval_level_required": approval_level.value,
        "prepared_by": "API User",
        "prepared_at": now,
        "source_system": entry.source_system,
        "supporting_documentation": entry.supporting_documentation,
        "status": "draft",
    }

    # Reject unbalanced entries immediately.
    # This is a fundamental accounting control.
    if not is_balanced:
        entry_dict["status"] = "rejected"
        entry_dict["rejection_reason"] = (
            f"Entry is not balanced. Debits: ${total_debits:,.2f}, "
            f"Credits: ${total_credits:,.2f}"
        )
        save_journal_entry(entry_dict)
        raise HTTPException(
            status_code=400,
            detail=entry_dict["rejection_reason"]
        )

    # Auto-approve entries below L1 threshold
    if approval_level == ApprovalLevel.AUTO:
        entry_dict["status"] = "approved"
        entry_dict["approved_by"] = "Auto-Approved (Governance Engine)"
        entry_dict["approved_at"] = now

    # Route to human approval for entries above threshold
    elif approval_level == ApprovalLevel.L1_MANAGER:
        entry_dict["status"] = "pending_review"
    elif approval_level == ApprovalLevel.L2_CONTROLLER:
        entry_dict["status"] = "pending_l2_review"
    elif approval_level == ApprovalLevel.L3_CFO:
        entry_dict["status"] = "pending_l3_review"

    save_journal_entry(entry_dict)

    return {
        "entry_id": entry_id,
        "status": entry_dict["status"],
        "approval_level": approval_level.value,
        "materiality_amount": materiality,
        "message": f"Journal entry created. Status: {entry_dict['status']}",
    }


@app.get("/journal-entries")
async def list_journal_entries(period: str = "2026-02", status: Optional[str] = None):
    """List all journal entries for a period, optionally filtered by status."""
    entries = get_journal_entries(period, status)
    return {"period": period, "count": len(entries), "entries": entries}


@app.get("/journal-entries/{entry_id}")
async def get_journal_entry(entry_id: str):
    """Get detailed information about a specific journal entry."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM journal_entries WHERE entry_id = ?", (entry_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Journal entry {entry_id} not found")
    return dict(row)


@app.post("/journal-entries/{entry_id}/approve")
async def approve_journal_entry(
    entry_id: str,
    reviewer_name: str = "Accounting Manager",
    notes: Optional[str] = None,
):
    """
    Approve a journal entry pending human review.

    Enforces segregation of duties: the approver cannot be the
    same person who prepared the entry. This is a key SOX control
    (SOX-JE-002).
    """
    result = governance_engine.process_human_review(
        entry_id=entry_id,
        approved=True,
        reviewer_name=reviewer_name,
        reviewer_title="Manager",
        notes=notes,
    )

    if "error" in result:
        raise HTTPException(status_code=403, detail=result["detail"])

    return {"message": "Journal entry approved", **result}


@app.post("/journal-entries/{entry_id}/reject")
async def reject_journal_entry(
    entry_id: str,
    reviewer_name: str = "Accounting Manager",
    notes: Optional[str] = None,
):
    """
    Reject a journal entry pending human review.

    The rejection reason is logged in the audit trail.
    Rejected entries can be revised and resubmitted.
    """
    result = governance_engine.process_human_review(
        entry_id=entry_id,
        approved=False,
        reviewer_name=reviewer_name,
        reviewer_title="Manager",
        notes=notes or "Rejected by reviewer",
    )

    if "error" in result:
        raise HTTPException(status_code=403, detail=result["detail"])

    return {"message": "Journal entry rejected", **result}


# ============================================================
# RECONCILIATION ENDPOINTS
# ============================================================

@app.get("/reconciliations")
async def list_reconciliations(period: str = "2026-02"):
    """List all reconciliations for a period."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM reconciliations WHERE period = ? ORDER BY account_number",
        (period,)
    ).fetchall()
    conn.close()
    return {"period": period, "count": len(rows), "reconciliations": [dict(r) for r in rows]}


@app.get("/reconciliations/{recon_id}")
async def get_reconciliation(recon_id: str):
    """Get detailed information about a specific reconciliation."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM reconciliations WHERE recon_id = ?", (recon_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Reconciliation {recon_id} not found")
    return dict(row)


@app.post("/reconciliations/{recon_id}/certify")
async def certify_reconciliation(
    recon_id: str,
    reviewer_name: str = "Accounting Manager",
    notes: Optional[str] = None,
):
    """
    Certify a completed reconciliation.

    Certification means the reviewer has verified the reconciliation
    is accurate and complete. Enforces segregation: the certifier
    must be different from the preparer (SOX-REC-002).
    """
    conn = get_connection()
    recon = conn.execute(
        "SELECT * FROM reconciliations WHERE recon_id = ?", (recon_id,)
    ).fetchone()

    if not recon:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Reconciliation {recon_id} not found")

    # Enforce segregation of duties
    if recon["prepared_by"] and recon["prepared_by"].lower() == reviewer_name.lower():
        conn.close()
        raise HTTPException(
            status_code=403,
            detail=f"Segregation of duties violation: {reviewer_name} prepared this "
                   f"reconciliation and cannot also certify it."
        )

    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE reconciliations SET status = 'certified', reviewed_by = ?, reviewed_at = ? "
        "WHERE recon_id = ?",
        (reviewer_name, now, recon_id)
    )
    conn.commit()
    conn.close()

    return {
        "recon_id": recon_id,
        "status": "certified",
        "certified_by": reviewer_name,
        "certified_at": now,
        "notes": notes,
    }


# ============================================================
# VARIANCE ANALYSIS ENDPOINT
# ============================================================

@app.get("/variance-report")
async def get_variance_report(period: str = "2026-02"):
    """
    Generate a budget vs. actual variance report.

    Returns all account variances with material items flagged.
    Material thresholds: >5% or >$25,000 from budget.
    """
    balances = get_all_balances(period)

    if not balances:
        return {"period": period, "message": "No balances found", "variances": []}

    variances = []
    material_count = 0

    for b in balances:
        budget = b.get("budget_amount")
        if budget is None or budget == 0:
            continue

        actual = b["gl_balance"]
        variance = actual - budget
        pct = (variance / abs(budget)) * 100
        is_material = abs(pct) > 5.0 or abs(variance) > 25000

        if is_material:
            material_count += 1

        variances.append({
            "account_number": b["account_number"],
            "account_name": b["account_name"],
            "account_type": b["account_type"],
            "actual": actual,
            "budget": budget,
            "variance": variance,
            "variance_pct": round(pct, 2),
            "is_material": is_material,
        })

    return {
        "period": period,
        "total_accounts": len(variances),
        "material_variances": material_count,
        "variances": variances,
    }


# ============================================================
# HUMAN-IN-THE-LOOP REVIEW ENDPOINTS
# ============================================================

@app.get("/reviews/pending")
async def get_pending_review_list():
    """
    Get all items waiting for human review.

    This is the reviewer's inbox. Each item includes the
    escalation reason so the reviewer knows why the AI
    could not auto-approve it.
    """
    reviews = get_pending_reviews()
    if not reviews:
        return {"message": "No items pending review", "count": 0}
    return {"count": len(reviews), "pending_reviews": reviews}


# ============================================================
# GOVERNANCE ENDPOINTS
# ============================================================

@app.get("/governance/audit-trail")
async def get_governance_audit_trail(period: str = "2026-02"):
    """
    Full audit trail of all agent decisions for a close period.

    Returns every decision made by every agent, including
    reasoning, confidence scores, data sources, and financial
    impact. This is the transparency endpoint that auditors
    use to understand how and why decisions were made.
    """
    trail = get_audit_trail(period)
    return {
        "period": period,
        "total_decisions": len(trail),
        "decisions": trail,
    }


@app.get("/governance/dashboard")
async def governance_dashboard(period: str = "2026-02"):
    """
    Governance overview dashboard.

    Summary statistics about the close process: entries processed,
    approval breakdown, SOX control status, and pending items.
    """
    conn = get_connection()

    # Journal entry counts by status
    je_stats = conn.execute(
        "SELECT status, COUNT(*) as count FROM journal_entries "
        "WHERE period = ? GROUP BY status",
        (period,)
    ).fetchall()

    # Reconciliation counts
    recon_stats = conn.execute(
        "SELECT status, COUNT(*) as count FROM reconciliations "
        "WHERE period = ? GROUP BY status",
        (period,)
    ).fetchall()

    # Pending reviews
    pending = conn.execute(
        "SELECT COUNT(*) FROM human_reviews WHERE status = 'pending'"
    ).fetchone()[0]

    # Total audit trail entries
    audit_count = conn.execute(
        "SELECT COUNT(*) FROM agent_decisions WHERE close_period = ?",
        (period,)
    ).fetchone()[0]

    # SOX control test results
    sox_tests = conn.execute(
        "SELECT result, COUNT(*) as count FROM sox_control_tests "
        "WHERE period = ? GROUP BY result",
        (period,)
    ).fetchall()

    conn.close()

    return {
        "period": period,
        "journal_entries": {row["status"]: row["count"] for row in je_stats},
        "reconciliations": {row["status"]: row["count"] for row in recon_stats},
        "pending_human_reviews": pending,
        "total_audit_trail_entries": audit_count,
        "sox_control_tests": {row["result"]: row["count"] for row in sox_tests},
        "governance_policy": {
            "materiality_l1": governance_engine.policy.materiality_l1,
            "materiality_l2": governance_engine.policy.materiality_l2,
            "materiality_l3": governance_engine.policy.materiality_l3,
            "confidence_threshold": governance_engine.policy.confidence_threshold,
            "recon_variance_threshold_pct": governance_engine.policy.recon_variance_threshold_pct,
            "enforce_segregation_of_duties": governance_engine.policy.enforce_segregation_of_duties,
        },
    }


@app.get("/governance/sox-controls")
async def get_sox_control_status():
    """
    Get the current status of all SOX controls.

    Returns each control with its last test result and evidence.
    """
    controls = get_sox_controls()
    return {"total_controls": len(controls), "controls": controls}


@app.post("/governance/sox-tests/run")
async def run_sox_tests(period: str = "2026-02"):
    """
    Run all SOX control tests for a period.

    Tests are executed against actual data in the database.
    Results are stored with evidence that auditors can review.
    """
    sox_engine = SOXControlsEngine()
    results = sox_engine.run_all_tests(period)

    passed = sum(1 for r in results if r["result"] == "pass")
    failed = sum(1 for r in results if r["result"] == "fail")

    return {
        "period": period,
        "total_tests": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


# ============================================================
# SYSTEM ENDPOINTS
# ============================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    Verifies database connectivity and returns system status.
    Used by Docker healthcheck and load balancers.
    """
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "connected"
    except Exception:
        db_status = "error"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }
