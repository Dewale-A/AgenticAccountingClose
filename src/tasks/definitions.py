"""
============================================================
Task Definitions
============================================================
Tasks define WHAT each agent should do for a specific close period.
While agents define WHO does the work (role, goal, backstory),
tasks define the specific instructions for THIS close.

Each task includes:
  - description: Detailed instructions including the close period
  - expected_output: What format the agent should return
  - agent: Which agent performs this task

Tasks are created dynamically because the instructions must
include the specific close period and any contextual data
from earlier agents in the pipeline.

Sequential Flow:
  data_collection -> journal_entry -> reconciliation ->
  variance_analysis -> compliance -> review
============================================================
"""

from crewai import Task


def create_data_collection_task(agent, period: str) -> Task:
    """
    Task: Collect all subledger balances and prepare trial balance.

    This is the first task in the pipeline. Every other agent
    depends on the data collected here. If the trial balance
    is wrong, everything downstream is wrong.
    """
    return Task(
        description=f"""
        Collect all account balances for the close period: {period}

        Your tasks:
        1. Retrieve the full trial balance for period {period} using the
           trial balance tool. Verify total debits equal total credits.

        2. Identify all control accounts that require reconciliation.
           Use the control accounts tool to get the list.

        3. Flag any accounts with unusual balances compared to prior period.
           Look for accounts with significant changes (>10% or >$50,000).

        4. Summarize the data quality:
           - Total number of accounts
           - Trial balance in/out of balance
           - Number of control accounts requiring reconciliation
           - Any data quality concerns

        This data will be used by all subsequent agents in the close pipeline.
        """,
        expected_output="""
        A complete data collection summary including:
        - Trial balance status (in balance or out of balance)
        - Total debits and credits
        - List of control accounts requiring reconciliation
        - Any flagged anomalies or data quality issues
        - Confirmation that data is ready for the close process
        """,
        agent=agent,
    )


def create_journal_entry_task(agent, period: str) -> Task:
    """
    Task: Prepare adjusting journal entries for the close period.

    The Journal Entry Agent analyzes the trial balance and
    identifies entries that need to be booked. Common entries
    include accruals, amortizations, and reclassifications.
    """
    return Task(
        description=f"""
        Prepare adjusting journal entries for close period: {period}

        Review the trial balance and accounting policies to determine
        what adjustments are needed. Common adjustments include:

        1. ACCRUALS:
           - Salary accrual: Accrue for days worked since last payroll
           - Benefits accrual: Accrue employee benefits for the period
           - Utility accrual: Estimate utilities not yet invoiced

        2. AMORTIZATIONS:
           - Prepaid Insurance: Monthly amortization ($4,000/month)
           - Prepaid Rent: Monthly amortization if applicable

        3. DEPRECIATION:
           - Property and Equipment: Monthly depreciation per schedule
             ($26,667/month based on $3.2M assets, 10-year average life)

        4. RECLASSIFICATIONS:
           - Review accounts for items that need reclassification

        For each entry, provide:
        - Entry type (accrual, deferral, depreciation, reclassification)
        - Description with business justification
        - Debit and credit lines with account numbers
        - Supporting calculation
        - Confidence score (0.0 to 1.0)

        Search the accounting policies documentation for guidance on
        recognition criteria and thresholds.

        IMPORTANT: Every entry must balance (total debits = total credits).
        """,
        expected_output="""
        A list of proposed journal entries, each containing:
        - Entry type and description
        - Debit and credit lines with account numbers and amounts
        - Supporting calculation or reference
        - Confidence score
        - Whether it requires human approval based on materiality
        """,
        agent=agent,
    )


def create_reconciliation_task(agent, period: str) -> Task:
    """
    Task: Reconcile all control accounts for the close period.

    This is a critical detective control required by SOX.
    The agent must compare GL to subledger and explain every
    difference.
    """
    return Task(
        description=f"""
        Reconcile all control accounts for close period: {period}

        Steps for each control account:

        1. Retrieve the GL balance and subledger balance using the
           control accounts tool.

        2. Calculate the difference (GL minus subledger).

        3. For each account with a difference, identify the likely cause:
           - Cash accounts: Outstanding checks, deposits in transit,
             bank fees not yet recorded
           - Accounts Receivable: Unapplied customer payments,
             credit memos not yet posted
           - Inventory: Count adjustments, in-transit items,
             damaged goods not yet written off
           - Accounts Payable: Unprocessed vendor invoices,
             duplicate payments, credit notes

        4. Classify each reconciling item:
           - timing: Will clear in next period
           - outstanding: Requires action to resolve
           - error: Needs correction entry
           - other: Document the nature

        5. Determine if the reconciliation is within tolerance:
           - Tolerance: 1% or $100, whichever is greater
           - Within tolerance: Mark as reconciled
           - Outside tolerance: Flag for investigation

        Search the close procedures documentation for reconciliation
        standards and requirements.
        """,
        expected_output="""
        A reconciliation report for each control account:
        - Account number and name
        - GL balance and subledger balance
        - Difference amount and percentage
        - List of reconciling items with amounts and categories
        - Explained vs. unexplained amounts
        - Status: reconciled, variance identified, or needs investigation
        - Confidence score
        """,
        agent=agent,
    )


def create_variance_analysis_task(agent, period: str) -> Task:
    """
    Task: Perform flux analysis for the close period.

    Compares actuals to budget and prior period. Material
    variances must be explained with specific root causes.
    """
    return Task(
        description=f"""
        Perform variance (flux) analysis for close period: {period}

        Steps:
        1. Retrieve the budget variance report for all accounts
           using the budget variance tool.

        2. For each MATERIAL variance (>5% or >$25,000 from budget):
           a. Determine the root cause category:
              - timing: Revenue or expense in different period than budgeted
              - volume: More or fewer transactions than expected
              - rate: Price or rate changes from budget assumptions
              - one_time: Non-recurring items not in the budget
              - business: New products, markets, or operational changes
              - correction: Prior period corrections
              - other: Document the specific nature

           b. Write a SPECIFIC explanation. Example:
              "Marketing expense is $8,000 over budget due to the
              Q1 product launch campaign approved in January."
              NOT: "Higher than expected."

           c. Determine if follow-up action is needed.

        3. Compile the full variance report with:
           - Total accounts analyzed
           - Number of material variances
           - List of each material variance with explanation
           - Executive summary of overall financial performance

        Search accounting policies for materiality thresholds and
        close procedures for variance explanation standards.
        """,
        expected_output="""
        A comprehensive variance analysis report:
        - Executive summary of financial performance for the period
        - List of all material variances with:
          - Account, actual, budget, variance amount and percentage
          - Root cause category
          - Specific explanation
          - Whether follow-up action is needed
        - Overall confidence score for the analysis
        """,
        agent=agent,
    )


def create_compliance_task(agent, period: str) -> Task:
    """
    Task: Run SOX control tests for the close period.

    The Compliance Agent tests each key control and documents
    the results with evidence. This is the automated equivalent
    of internal audit testing.
    """
    return Task(
        description=f"""
        Execute SOX control testing for close period: {period}

        Test each of these key controls:

        1. SOX-JE-001 (Journal Entry Authorization):
           - Check all entries above $10,000 have proper approval
           - Verify approval timestamp exists
           - Document sample size and exceptions

        2. SOX-JE-002 (Segregation of Duties):
           - Verify preparer != approver for all approved entries
           - Check for any self-approved entries
           - Document any violations

        3. SOX-REC-001 (Reconciliation Completeness):
           - Verify all control accounts have been reconciled
           - Count required vs. completed reconciliations
           - Document any gaps

        4. SOX-REC-002 (Reconciliation Review):
           - Verify reconciliation reviewer != preparer
           - Document any segregation issues

        5. SOX-VAR-001 (Flux Analysis):
           - Verify material variances have been identified
           - Check that explanations exist for material items

        For each test, document:
        - Test performed and evidence examined
        - Sample size and selection method
        - Pass/fail result
        - Exceptions found and their significance
        - Overall conclusion

        Search the SOX compliance guide for testing procedures
        and deficiency classification criteria.
        """,
        expected_output="""
        SOX control test results including:
        - Summary: X of Y controls tested, Z passed
        - Detailed results for each control:
          - Control ID and name
          - Test performed
          - Sample size
          - Result (pass/fail)
          - Exceptions found
          - Conclusion
        - Any deficiencies noted with classification
        - Overall compliance assessment
        """,
        agent=agent,
    )


def create_review_task(agent, period: str) -> Task:
    """
    Task: Final quality review and close package generation.

    The Review Agent is the last checkpoint before the Controller
    and CFO review the close. It must catch anything the other
    agents missed.
    """
    return Task(
        description=f"""
        Perform final review and generate close package for period: {period}

        Review all work completed by prior agents:

        1. DATA COLLECTION:
           - Is the trial balance complete and in balance?
           - Were all data quality issues addressed?

        2. JOURNAL ENTRIES:
           - Are all required adjustments posted?
           - Are all entries balanced (DR = CR)?
           - Do entries above materiality have appropriate approval?

        3. RECONCILIATIONS:
           - Are all control accounts reconciled?
           - Are unexplained variances flagged and documented?
           - Have reconciliations been independently reviewed?

        4. VARIANCE ANALYSIS:
           - Are all material variances explained?
           - Are explanations specific and supported?
           - Are any action items documented?

        5. SOX COMPLIANCE:
           - Have all key controls been tested?
           - Are there any deficiencies? If so, what is their classification?
           - Is segregation of duties maintained?

        Generate the close package summary:
        - Executive summary (key highlights and issues)
        - Financial summary (total adjustments, final balances)
        - Close status (complete, open items)
        - Risk assessment (any items that could concern auditors)
        - Recommendation: Ready for sign-off or needs attention

        Use the journal entries tool to verify entry status.
        """,
        expected_output="""
        A comprehensive close package summary:
        - Executive summary paragraph
        - Close completion status (all tasks complete or with open items)
        - Total journal entries and their status breakdown
        - Reconciliation summary (complete vs. outstanding)
        - Variance analysis highlights
        - SOX compliance status
        - Open items requiring attention
        - Recommendation for Controller/CFO sign-off
        - Confidence score for overall close quality
        """,
        agent=agent,
    )
