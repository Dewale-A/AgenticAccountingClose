"""
============================================================
Governance Engine (SOX-Compliant)
============================================================
This is the core policy enforcement layer for the month-end
close process. It extends the basic governance pattern with
accounting-specific controls:

1. MATERIALITY GATES
   Entries are routed to different approval levels based on
   dollar amount. This is a fundamental SOX requirement.
   
   Below $10K  -> Auto-approved (with full audit trail)
   $10K-$50K   -> Manager approval (L1)
   $50K-$250K  -> Controller approval (L2)
   $250K+      -> CFO approval (L3)

2. SEGREGATION OF DUTIES
   The person who prepares an entry CANNOT be the same person
   who approves or posts it. This prevents fraud and is a
   cornerstone of internal controls.

3. FOUR-EYES PRINCIPLE
   Material items require at least two people to review before
   they hit the general ledger. This catches errors and fraud.

4. RECONCILIATION TOLERANCE
   Small differences in reconciliations can be auto-approved.
   Material differences require investigation and sign-off.

5. CONFIDENCE-BASED ESCALATION
   When an AI agent is uncertain (confidence < threshold),
   it escalates to a human rather than proceeding with a
   potentially wrong decision.

Every action is logged to an immutable audit trail that
auditors can review during SOX testing.
============================================================
"""

import uuid
from datetime import datetime
from src.models.schemas import (
    JournalEntry,
    GovernancePolicy,
    AgentDecision,
    ApprovalLevel,
    EntryStatus,
)
from src.data.database import (
    save_agent_decision,
    save_audit_log,
    get_connection,
)


class GovernanceEngine:
    """
    Central governance controller for the accounting close process.
    
    Usage:
        engine = GovernanceEngine()
        
        # Determine approval level for a journal entry
        level = engine.get_approval_level(entry_amount)
        
        # Log every agent decision
        engine.log_decision(...)
        
        # Evaluate a journal entry for compliance
        entry = engine.evaluate_entry(entry)
        
        # Check segregation of duties
        engine.validate_segregation(preparer, approver)
    """

    def __init__(self, policy: GovernancePolicy = None):
        self.policy = policy or GovernancePolicy()

    def get_approval_level(self, amount: float) -> ApprovalLevel:
        """
        Determine the required approval level based on materiality.
        
        This is the materiality gate. Every journal entry passes
        through here to determine who needs to approve it.
        
        Args:
            amount: The absolute dollar amount of the entry
            
        Returns:
            The required ApprovalLevel
        """
        abs_amount = abs(amount)

        if abs_amount >= self.policy.materiality_l3:
            return ApprovalLevel.L3_CFO
        elif abs_amount >= self.policy.materiality_l2:
            return ApprovalLevel.L2_CONTROLLER
        elif abs_amount >= self.policy.materiality_l1:
            return ApprovalLevel.L1_MANAGER
        else:
            return ApprovalLevel.AUTO

    def validate_segregation(self, preparer: str, approver: str) -> bool:
        """
        Enforce segregation of duties.
        
        SOX requires that the person who prepares a journal entry
        cannot be the same person who approves it. This function
        validates that constraint.
        
        Args:
            preparer: Who prepared the entry
            approver: Who is trying to approve it
            
        Returns:
            True if segregation is maintained, False if violated
        """
        if not self.policy.enforce_segregation_of_duties:
            return True

        if preparer.lower() == approver.lower():
            self._log_event(
                period="",
                event_type="segregation_violation",
                event_detail=f"Segregation of duties violation: {preparer} cannot both prepare and approve",
                actor="Governance Engine",
            )
            return False
        return True

    def evaluate_entry(self, entry: JournalEntry) -> JournalEntry:
        """
        Evaluate a journal entry against all governance policies.
        
        Checks performed:
        1. Is the entry balanced? (debits == credits)
        2. What approval level is required?
        3. Is agent confidence sufficient?
        4. Are there any compliance flags?
        
        Args:
            entry: The journal entry to evaluate
            
        Returns:
            Updated entry with governance fields set
        """
        # ---- Check 1: Entry must be balanced ----
        if not entry.is_balanced:
            entry.status = EntryStatus.REJECTED
            entry.rejection_reason = "Entry is not balanced. Total debits must equal total credits."
            self._log_event(
                entry.period,
                "entry_rejected",
                f"Entry {entry.entry_id} rejected: unbalanced (DR: {entry.total_debits}, CR: {entry.total_credits})",
                "Governance Engine",
                affected_entity=entry.entry_id,
                dollar_impact=entry.materiality_amount,
            )
            return entry

        # ---- Check 2: Determine approval level ----
        approval_level = self.get_approval_level(entry.materiality_amount)
        entry.approval_level_required = approval_level

        # ---- Check 3: Auto-approve if below threshold ----
        if (
            approval_level == ApprovalLevel.AUTO
            and self.policy.auto_approve_below_l1
            and (entry.confidence_score is None or entry.confidence_score >= self.policy.confidence_threshold)
        ):
            entry.status = EntryStatus.APPROVED
            entry.approved_by = "Auto-Approved (Governance Engine)"
            entry.approved_at = datetime.now().isoformat()

            self._log_event(
                entry.period,
                "entry_auto_approved",
                f"Entry {entry.entry_id} auto-approved. Amount ${entry.materiality_amount:,.2f} below L1 threshold ${self.policy.materiality_l1:,.2f}",
                "Governance Engine",
                affected_entity=entry.entry_id,
                dollar_impact=entry.materiality_amount,
            )
            return entry

        # ---- Check 4: Route to appropriate approval level ----
        if approval_level == ApprovalLevel.L1_MANAGER:
            entry.status = EntryStatus.PENDING_REVIEW
        elif approval_level == ApprovalLevel.L2_CONTROLLER:
            entry.status = EntryStatus.PENDING_L2_REVIEW
        elif approval_level == ApprovalLevel.L3_CFO:
            entry.status = EntryStatus.PENDING_L3_REVIEW

        # ---- Check 5: Low confidence override ----
        if (
            entry.confidence_score is not None
            and entry.confidence_score < self.policy.confidence_threshold
            and entry.status == EntryStatus.APPROVED
        ):
            entry.status = EntryStatus.PENDING_REVIEW

        # Create human review record
        self._create_review(entry, approval_level)

        self._log_event(
            entry.period,
            "entry_escalated",
            f"Entry {entry.entry_id} escalated to {approval_level.value}. "
            f"Amount: ${entry.materiality_amount:,.2f}. Confidence: {entry.confidence_score}",
            "Governance Engine",
            affected_entity=entry.entry_id,
            dollar_impact=entry.materiality_amount,
        )

        return entry

    def evaluate_reconciliation(self, recon_data: dict) -> dict:
        """
        Evaluate a reconciliation against tolerance thresholds.
        
        If the variance is within tolerance, it can be auto-certified.
        If it exceeds tolerance, it needs human investigation.
        """
        difference = abs(recon_data.get("difference", 0))
        difference_pct = abs(recon_data.get("difference_pct", 0))

        if (difference <= self.policy.recon_variance_threshold_abs
            and difference_pct <= self.policy.recon_variance_threshold_pct):
            recon_data["status"] = "reconciled"
            self._log_event(
                recon_data.get("period", ""),
                "recon_auto_reconciled",
                f"Account {recon_data['account_number']} auto-reconciled. "
                f"Variance: ${difference:,.2f} ({difference_pct:.2f}%) within tolerance.",
                "Governance Engine",
                affected_entity=recon_data.get("recon_id"),
                dollar_impact=difference,
            )
        else:
            recon_data["status"] = "variance"
            self._log_event(
                recon_data.get("period", ""),
                "recon_variance_flagged",
                f"Account {recon_data['account_number']} variance flagged. "
                f"Variance: ${difference:,.2f} ({difference_pct:.2f}%) exceeds tolerance.",
                "Governance Engine",
                affected_entity=recon_data.get("recon_id"),
                dollar_impact=difference,
            )

        return recon_data

    def log_decision(
        self,
        period: str,
        agent_name: str,
        decision_type: str,
        decision_value: str,
        reasoning: str,
        confidence: float,
        data_sources: list[str] = None,
        affected_accounts: list[str] = None,
        dollar_impact: float = None,
    ) -> AgentDecision:
        """Record an agent's decision in the audit trail."""
        decision = AgentDecision(
            decision_id=f"DEC-{uuid.uuid4().hex[:8]}",
            close_period=period,
            agent_name=agent_name,
            decision_type=decision_type,
            decision_value=decision_value,
            reasoning=reasoning,
            confidence=confidence,
            data_sources=data_sources or [],
            affected_accounts=affected_accounts or [],
            dollar_impact=dollar_impact,
        )
        save_agent_decision(decision.model_dump())

        self._log_event(
            period,
            "agent_decision",
            f"{agent_name}: {decision_type}={decision_value} (confidence: {confidence:.2f})",
            agent_name,
            dollar_impact=dollar_impact,
        )
        return decision

    def process_human_review(
        self,
        entry_id: str,
        approved: bool,
        reviewer_name: str,
        reviewer_title: str = "Manager",
        notes: str = None,
    ) -> dict:
        """Process a human reviewer's decision on an escalated entry."""
        conn = get_connection()
        now = datetime.now().isoformat()

        # Get the entry to check segregation of duties
        entry = conn.execute(
            "SELECT prepared_by FROM journal_entries WHERE entry_id = ?", (entry_id,)
        ).fetchone()

        if entry and not self.validate_segregation(entry["prepared_by"], reviewer_name):
            conn.close()
            return {
                "error": "Segregation of duties violation",
                "detail": f"{reviewer_name} cannot approve an entry prepared by {entry['prepared_by']}",
            }

        # Update review record
        status = "approved" if approved else "rejected"
        conn.execute(
            """UPDATE human_reviews 
               SET status = ?, reviewer_name = ?, reviewer_title = ?, 
                   reviewer_notes = ?, reviewed_at = ?
               WHERE entry_id = ? AND status = 'pending'""",
            (status, reviewer_name, reviewer_title, notes, now, entry_id)
        )

        # Update journal entry
        if approved:
            conn.execute(
                """UPDATE journal_entries 
                   SET status = 'approved', approved_by = ?, approved_at = ?
                   WHERE entry_id = ?""",
                (reviewer_name, now, entry_id)
            )
        else:
            conn.execute(
                """UPDATE journal_entries 
                   SET status = 'rejected', rejection_reason = ?
                   WHERE entry_id = ?""",
                (notes or "Rejected by reviewer", entry_id)
            )

        conn.commit()
        conn.close()

        action = "approved" if approved else "rejected"
        self._log_event(
            "",
            "human_review",
            f"Entry {entry_id} {action} by {reviewer_name} ({reviewer_title}). Notes: {notes or 'None'}",
            reviewer_name,
            affected_entity=entry_id,
        )

        return {"entry_id": entry_id, "status": status, "reviewer": reviewer_name}

    def _create_review(self, entry: JournalEntry, approval_level: ApprovalLevel):
        """Create a pending human review record."""
        conn = get_connection()
        review_id = f"REV-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO human_reviews 
               (review_id, entry_id, escalation_reason, approval_level,
                agent_recommendation, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (
                review_id,
                entry.entry_id,
                f"Materiality: ${entry.materiality_amount:,.2f} requires {approval_level.value} approval",
                approval_level.value,
                entry.agent_reasoning or entry.description,
                datetime.now().isoformat(),
            )
        )
        conn.commit()
        conn.close()

    def _log_event(self, period: str, event_type: str, event_detail: str,
                   actor: str, affected_entity: str = None, dollar_impact: float = None):
        """Add an entry to the audit log."""
        entry = {
            "entry_id": f"LOG-{uuid.uuid4().hex[:8]}",
            "close_period": period,
            "event_type": event_type,
            "event_detail": event_detail,
            "actor": actor,
            "actor_role": "system",
            "affected_entity": affected_entity,
            "dollar_impact": dollar_impact,
            "timestamp": datetime.now().isoformat(),
        }
        save_audit_log(entry)
