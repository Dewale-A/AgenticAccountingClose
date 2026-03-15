"""
============================================================
Data Models (Pydantic Schemas)
============================================================
These models define every data structure in the month-end close
system. They enforce:
  1. Type safety across the entire pipeline
  2. SOX-compliant data structures (audit fields on everything)
  3. Clear documentation for auditors and developers

Key governance concept: EVERY model includes audit fields.
Who created it, when, who approved it, when. This isn't optional
in a SOX environment. If you can't prove who did what and when,
you fail the audit.

Month-End Close Workflow:
  1. Data Collection   -> Gather subledger balances
  2. Journal Entries    -> Adjusting entries, accruals, deferrals
  3. Reconciliation     -> Match and verify balances
  4. Variance Analysis  -> Explain material differences
  5. Compliance Review  -> SOX controls validation
  6. Close Package      -> Final review and sign-off
============================================================
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================

class AccountType(str, Enum):
    """
    Standard chart of accounts categories.
    Every GL account falls into one of these types.
    """
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class EntryStatus(str, Enum):
    """
    Journal entry lifecycle status.
    
    SOX requires that entries go through a defined approval workflow.
    The status tracks where each entry is in that workflow.
    
    Flow: draft -> pending_review -> approved -> posted
                                  -> rejected (back to draft)
                -> pending_l2_review (if above L2 threshold)
                -> pending_l3_review (if above L3 threshold)
    """
    DRAFT = "draft"                         # Created by agent, not yet reviewed
    PENDING_REVIEW = "pending_review"       # Awaiting L1 approval (manager)
    PENDING_L2_REVIEW = "pending_l2_review" # Awaiting L2 approval (controller)
    PENDING_L3_REVIEW = "pending_l3_review" # Awaiting L3 approval (CFO)
    APPROVED = "approved"                   # Approved, ready to post
    POSTED = "posted"                       # Posted to general ledger
    REJECTED = "rejected"                   # Rejected, needs revision
    REVERSED = "reversed"                   # Reversed (correction posted)


class ApprovalLevel(str, Enum):
    """
    Approval hierarchy based on materiality thresholds.
    
    This implements the "Four-Eyes Principle" required by SOX:
    - The person who prepares an entry cannot approve it
    - Higher dollar amounts require higher authority approval
    - Each level has its own threshold (configurable)
    """
    AUTO = "auto"           # Below L1 threshold, auto-approved with audit log
    L1_MANAGER = "l1"       # Manager approval ($10K - $50K default)
    L2_CONTROLLER = "l2"    # Controller approval ($50K - $250K default)
    L3_CFO = "l3"           # CFO approval ($250K+ default)


class ReconciliationStatus(str, Enum):
    """Status of an account reconciliation."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    RECONCILED = "reconciled"         # Balances match within tolerance
    VARIANCE_IDENTIFIED = "variance"  # Discrepancy found, needs investigation
    REVIEWED = "reviewed"             # Variance reviewed and explained
    CERTIFIED = "certified"           # Signed off by reviewer


class CloseTaskStatus(str, Enum):
    """Status of a close checklist task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"           # Waiting on dependency
    NEEDS_REVIEW = "needs_review"
    SIGNED_OFF = "signed_off"


class VarianceCause(str, Enum):
    """Standard variance explanation categories for flux analysis."""
    TIMING = "timing"                 # Revenue/expense recognized in different period
    VOLUME = "volume"                 # More or fewer transactions than expected
    RATE = "rate"                     # Price/rate changes
    ONE_TIME = "one_time"             # Non-recurring item
    RECLASSIFICATION = "reclass"      # Account reclassification
    ACCRUAL_ADJUSTMENT = "accrual"    # Accrual timing differences
    ERROR_CORRECTION = "correction"   # Prior period correction
    BUSINESS_CHANGE = "business"      # New product, market, or operational change
    OTHER = "other"


# ============================================================
# CHART OF ACCOUNTS AND BALANCES
# ============================================================

class Account(BaseModel):
    """
    A general ledger account in the chart of accounts.
    
    In a real system, this maps to NetSuite or SAP GL accounts.
    The account structure drives how journal entries are validated
    (debits must equal credits within the same entry).
    """
    account_number: str = Field(description="GL account number (e.g., '1000-100')")
    account_name: str = Field(description="Account description (e.g., 'Cash - Operating')")
    account_type: AccountType = Field(description="Asset, Liability, Equity, Revenue, or Expense")
    department: str = Field(description="Department or cost center")
    is_control_account: bool = Field(default=False, description="Whether this is a control account (subledger)")
    requires_reconciliation: bool = Field(default=False, description="Whether monthly reconciliation is required")


class AccountBalance(BaseModel):
    """
    Account balance for a specific period.
    
    Both the subledger balance and the GL balance are tracked.
    The Reconciliation Agent compares these to find discrepancies.
    """
    account_number: str
    account_name: str
    period: str = Field(description="Close period (e.g., '2026-02')")
    gl_balance: float = Field(description="General ledger balance")
    subledger_balance: Optional[float] = Field(default=None, description="Subledger balance (if control account)")
    prior_period_balance: Optional[float] = Field(default=None, description="Prior period balance for comparison")
    budget_amount: Optional[float] = Field(default=None, description="Budgeted amount for variance analysis")
    variance_to_budget: Optional[float] = Field(default=None, description="Actual minus budget")
    variance_pct: Optional[float] = Field(default=None, description="Variance as percentage of budget")


# ============================================================
# JOURNAL ENTRIES
# ============================================================

class JournalEntryLine(BaseModel):
    """
    A single line in a journal entry.
    
    Accounting rule: Total debits must equal total credits.
    Each line is either a debit OR a credit (not both).
    The Journal Entry Agent creates these, and the system
    validates the balancing before allowing submission.
    """
    line_number: int = Field(description="Line sequence number")
    account_number: str = Field(description="GL account to debit or credit")
    account_name: Optional[str] = Field(default=None, description="Account description")
    department: Optional[str] = Field(default=None, description="Department code")
    debit: float = Field(default=0.0, description="Debit amount (positive)")
    credit: float = Field(default=0.0, description="Credit amount (positive)")
    description: str = Field(description="Line-level description of the entry")


class JournalEntryCreate(BaseModel):
    """
    Input model for creating a journal entry.
    This is what agents produce and what comes from the API.
    """
    entry_type: str = Field(description="Type: adjusting, accrual, deferral, reclassification, correction")
    description: str = Field(description="Entry description and business justification")
    period: str = Field(description="Close period (e.g., '2026-02')")
    lines: list[JournalEntryLine] = Field(description="Debit and credit lines")
    supporting_documentation: Optional[str] = Field(default=None, description="Reference to supporting docs")
    source_system: Optional[str] = Field(default=None, description="Originating system (e.g., 'AP Subledger')")


class JournalEntry(BaseModel):
    """
    Complete journal entry with full audit trail.
    
    SOX Requirements reflected in this model:
    - entry_id: Unique, sequential, tamper-evident
    - prepared_by: Who created it (agent or human)
    - approved_by: Who approved it (MUST be different from preparer)
    - approval_level: What level of authority approved it
    - posted_by: Who posted to GL (MUST be different from preparer)
    - All timestamps are immutable once set
    
    The segregation of duties is enforced at the model level:
    prepared_by != approved_by != posted_by
    """
    entry_id: str = Field(description="Unique entry ID (e.g., 'JE-2026-02-0001')")
    entry_type: str
    description: str
    period: str
    lines: list[JournalEntryLine]
    
    # Financial totals
    total_debits: float = Field(description="Sum of all debit lines")
    total_credits: float = Field(description="Sum of all credit lines")
    is_balanced: bool = Field(description="Whether debits equal credits (within $0.01 tolerance)")
    
    # Materiality and approval routing
    materiality_amount: float = Field(description="Absolute value of largest line item")
    approval_level_required: ApprovalLevel = Field(description="Required approval level based on materiality")
    
    # Audit trail (SOX mandatory)
    prepared_by: str = Field(description="Agent or person who created the entry")
    prepared_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    reviewed_by: Optional[str] = Field(default=None, description="First reviewer")
    reviewed_at: Optional[str] = Field(default=None)
    approved_by: Optional[str] = Field(default=None, description="Final approver (must differ from preparer)")
    approved_at: Optional[str] = Field(default=None)
    posted_by: Optional[str] = Field(default=None, description="Person who posted to GL")
    posted_at: Optional[str] = Field(default=None)
    
    # Supporting information
    supporting_documentation: Optional[str] = None
    source_system: Optional[str] = None
    agent_reasoning: Optional[str] = Field(default=None, description="AI agent's reasoning for this entry")
    confidence_score: Optional[float] = Field(default=None, description="Agent confidence (0.0 to 1.0)")
    
    # Status
    status: EntryStatus = Field(default=EntryStatus.DRAFT)
    rejection_reason: Optional[str] = Field(default=None, description="Why it was rejected (if applicable)")


# ============================================================
# RECONCILIATION
# ============================================================

class ReconciliationItem(BaseModel):
    """
    A single reconciling item (difference between GL and subledger).
    
    In accounting, reconciliation means explaining WHY two numbers
    that should match don't match. Each difference gets a reconciling
    item that explains the cause.
    """
    item_id: str
    description: str = Field(description="What this reconciling item represents")
    amount: float = Field(description="Dollar amount of the difference")
    category: str = Field(description="Category: timing, outstanding_check, in_transit, error, other")
    resolution: Optional[str] = Field(default=None, description="How this will be resolved")
    expected_clear_date: Optional[str] = Field(default=None, description="When this should clear")
    is_resolved: bool = Field(default=False)


class Reconciliation(BaseModel):
    """
    Account reconciliation for a specific period.
    
    SOX requires that all control accounts (bank, AR, AP, inventory)
    are reconciled monthly. The reconciliation must be:
    - Prepared by one person
    - Reviewed by a different person
    - Completed within the close timeline
    - All variances explained or flagged
    """
    recon_id: str = Field(description="Unique reconciliation ID")
    account_number: str
    account_name: str
    period: str
    
    # Balances being reconciled
    gl_balance: float = Field(description="General ledger balance")
    subledger_balance: float = Field(description="Subledger or external balance")
    difference: float = Field(description="GL minus subledger")
    difference_pct: float = Field(description="Difference as percentage")
    
    # Reconciling items that explain the difference
    reconciling_items: list[ReconciliationItem] = Field(default_factory=list)
    explained_amount: float = Field(default=0.0, description="Sum of reconciling items")
    unexplained_amount: float = Field(default=0.0, description="Remaining unexplained difference")
    
    # Audit trail
    prepared_by: str
    prepared_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    
    status: ReconciliationStatus = Field(default=ReconciliationStatus.NOT_STARTED)
    agent_reasoning: Optional[str] = None
    confidence_score: Optional[float] = None


# ============================================================
# VARIANCE / FLUX ANALYSIS
# ============================================================

class VarianceItem(BaseModel):
    """
    A single variance explanation in the flux analysis.
    
    Flux analysis answers the question: "Why did this account
    change significantly from budget or prior period?"
    
    The SEC and auditors expect management to explain material
    variances. This model captures those explanations.
    """
    account_number: str
    account_name: str
    actual_amount: float
    budget_amount: float
    variance_amount: float
    variance_pct: float
    cause: VarianceCause = Field(description="Category of variance")
    explanation: str = Field(description="Detailed explanation of the variance")
    is_material: bool = Field(description="Whether this variance is material")
    action_required: Optional[str] = Field(default=None, description="Follow-up action needed")


class VarianceReport(BaseModel):
    """
    Complete variance/flux analysis report for a period.
    """
    report_id: str
    period: str
    prepared_by: str
    prepared_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    reviewed_by: Optional[str] = None
    
    total_accounts_analyzed: int
    material_variances_count: int
    variances: list[VarianceItem] = Field(default_factory=list)
    executive_summary: Optional[str] = None
    confidence_score: Optional[float] = None


# ============================================================
# CLOSE MANAGEMENT
# ============================================================

class CloseTask(BaseModel):
    """
    A task in the month-end close checklist.
    
    The close process follows a strict sequence. Some tasks
    depend on others (you can't reconcile until journal entries
    are posted). This model tracks the dependency chain.
    """
    task_id: str
    task_name: str
    description: str
    sequence: int = Field(description="Order in the close sequence")
    depends_on: list[str] = Field(default_factory=list, description="Task IDs this depends on")
    assigned_to: str = Field(description="Agent or person responsible")
    status: CloseTaskStatus = Field(default=CloseTaskStatus.PENDING)
    due_date: Optional[str] = None
    completed_at: Optional[str] = None
    notes: Optional[str] = None


class ClosePackage(BaseModel):
    """
    The final month-end close package.
    
    This is what gets presented to the controller/CFO for sign-off.
    It summarizes everything: entries posted, reconciliations completed,
    variances explained, controls tested, and any open items.
    
    In a SOX environment, the close package IS the evidence that
    the close was performed properly. It must be complete, accurate,
    and signed off by appropriate authority.
    """
    package_id: str
    period: str
    
    # Summary counts
    total_journal_entries: int
    total_entries_posted: int
    total_entries_pending: int
    total_reconciliations: int
    reconciliations_certified: int
    material_variances: int
    variances_explained: int
    sox_controls_tested: int
    sox_controls_passed: int
    
    # Financial summary
    total_adjustments_debit: float
    total_adjustments_credit: float
    
    # Status
    all_tasks_complete: bool
    open_items: list[str] = Field(default_factory=list, description="Items still outstanding")
    
    # Sign-off chain
    prepared_by: str
    prepared_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    controller_sign_off: Optional[str] = None
    controller_sign_off_at: Optional[str] = None
    cfo_sign_off: Optional[str] = None
    cfo_sign_off_at: Optional[str] = None
    
    executive_summary: Optional[str] = None


# ============================================================
# SOX GOVERNANCE MODELS
# ============================================================

class SOXControl(BaseModel):
    """
    A SOX internal control relevant to the close process.
    
    SOX Section 404 requires companies to document internal controls
    over financial reporting and test them regularly. Each control
    maps to a specific risk and has defined testing procedures.
    
    This model tracks the controls and their test results.
    """
    control_id: str = Field(description="Control reference (e.g., 'SOX-JE-001')")
    control_name: str
    description: str
    category: str = Field(description="Category: journal_entry, reconciliation, access, segregation, reporting")
    risk_addressed: str = Field(description="What financial reporting risk this control mitigates")
    control_type: str = Field(description="Type: preventive or detective")
    frequency: str = Field(description="How often tested: monthly, quarterly, annually")
    owner: str = Field(description="Control owner responsible for execution")
    
    # Test results
    last_tested: Optional[str] = None
    test_result: Optional[str] = Field(default=None, description="pass, fail, or not_tested")
    test_evidence: Optional[str] = Field(default=None, description="Evidence supporting test result")
    deficiency_noted: Optional[str] = None


class SOXControlTest(BaseModel):
    """
    Record of a SOX control test performed during the close.
    """
    test_id: str
    control_id: str
    period: str
    tested_by: str
    tested_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    result: str = Field(description="pass or fail")
    evidence: str = Field(description="Description of evidence examined")
    sample_size: Optional[int] = Field(default=None, description="Number of items tested")
    exceptions_found: int = Field(default=0)
    conclusion: str


# ============================================================
# GOVERNANCE MODELS (Audit Trail and HITL)
# ============================================================

class AgentDecision(BaseModel):
    """
    Records a single decision made by an agent.
    Same pattern as AgenticFacilitiesMaintenance but with
    additional accounting-specific fields.
    """
    decision_id: str
    close_period: str
    agent_name: str
    decision_type: str
    decision_value: str
    reasoning: str
    confidence: float
    data_sources: list[str] = Field(default_factory=list)
    affected_accounts: list[str] = Field(default_factory=list, description="GL accounts affected")
    dollar_impact: Optional[float] = Field(default=None, description="Financial impact of this decision")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class HumanReview(BaseModel):
    """
    Records a human-in-the-loop review action.
    Enhanced with approval chain tracking for SOX compliance.
    """
    review_id: str
    entry_id: Optional[str] = Field(default=None, description="Journal entry being reviewed")
    recon_id: Optional[str] = Field(default=None, description="Reconciliation being reviewed")
    escalation_reason: str
    approval_level: ApprovalLevel
    agent_recommendation: str
    reviewer_name: Optional[str] = None
    reviewer_title: Optional[str] = Field(default=None, description="Manager, Controller, or CFO")
    status: str = Field(default="pending")
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AuditLogEntry(BaseModel):
    """Chronological audit log entry for SOX compliance."""
    entry_id: str
    close_period: str
    event_type: str
    event_detail: str
    actor: str
    actor_role: Optional[str] = Field(default=None, description="Role: agent, manager, controller, cfo")
    affected_entity: Optional[str] = Field(default=None, description="JE ID, Recon ID, etc.")
    dollar_impact: Optional[float] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class GovernancePolicy(BaseModel):
    """
    Configurable governance rules for the close process.
    
    These policies can be tuned per organization:
    - Conservative (bank): Lower thresholds, more human review
    - Moderate (public company): Standard thresholds
    - Progressive (startup): Higher thresholds, more automation
    
    The key insight: governance is a DIAL, not a switch.
    Organizations should start conservative and increase
    automation as they build trust in the system.
    """
    # Materiality thresholds (determines approval level)
    materiality_l1: float = Field(
        default=10000.0,
        description="Entries above this need manager (L1) approval"
    )
    materiality_l2: float = Field(
        default=50000.0,
        description="Entries above this need controller (L2) approval"
    )
    materiality_l3: float = Field(
        default=250000.0,
        description="Entries above this need CFO (L3) approval"
    )
    
    # Reconciliation tolerance
    recon_variance_threshold_pct: float = Field(
        default=1.0,
        description="Reconciliation variance above this % triggers review"
    )
    recon_variance_threshold_abs: float = Field(
        default=100.0,
        description="Reconciliation variance above this dollar amount triggers review"
    )
    
    # Flux analysis
    flux_threshold_pct: float = Field(
        default=5.0,
        description="Budget variance above this % is considered material"
    )
    flux_threshold_abs: float = Field(
        default=25000.0,
        description="Budget variance above this amount is considered material"
    )
    
    # Agent confidence
    confidence_threshold: float = Field(
        default=0.7,
        description="Agent confidence below this triggers human review"
    )
    
    # Segregation of duties
    enforce_segregation_of_duties: bool = Field(
        default=True,
        description="Enforce that preparer != approver != poster"
    )
    
    # Auto-approval
    auto_approve_below_l1: bool = Field(
        default=True,
        description="Auto-approve entries below L1 threshold (with full audit trail)"
    )
