# Month-End Close Procedures

## Overview

The month-end close process converts raw transaction data into reliable financial statements. This document describes the close calendar, step-by-step procedures, and documentation requirements. All procedures are designed to comply with SOX internal control requirements.

---

## 1. Close Calendar

The close follows a structured timeline measured in business days (BD) after period end:

| Day | Task | Owner | Dependencies |
|-----|------|-------|-------------|
| BD 1 | Collect subledger balances and run cutoff reports | Data Collection Agent | None |
| BD 1 | Complete revenue cutoff analysis | Revenue Accounting | None |
| BD 2 | Complete expense cutoff analysis | AP Team | None |
| BD 2 | Prepare adjusting journal entries (accruals, deferrals) | Journal Entry Agent | BD 1 tasks |
| BD 3 | Reconcile control accounts (Cash, AR, AP, Inventory) | Reconciliation Agent | BD 1 tasks |
| BD 3 | Complete bank reconciliations | Treasury | None |
| BD 3 | Post approved journal entries | Journal Entry Agent | BD 2 approvals |
| BD 4 | Perform flux analysis (actuals vs. budget vs. prior period) | Variance Analysis Agent | BD 3 tasks |
| BD 4 | Run SOX control tests | Compliance Agent | BD 2, BD 3 tasks |
| BD 5 | Prepare close package and summary | Review Agent | All prior tasks |
| BD 5 | Controller review and sign-off | Controller | Close package |
| BD 6 | CFO review and certification | CFO | Controller sign-off |
| BD 7 | Close period in system, lock GL | Finance Systems | CFO certification |

### Target Completion

- Routine monthly close: 5 business days
- Quarter-end close: 7 business days (additional disclosure requirements)
- Year-end close: 10 business days (audit coordination, tax provisions)

---

## 2. Close Checklist

Every close must complete the following items. Each item is tracked with status, owner, and completion timestamp.

### Pre-Close (Before Period End)

- [ ] Confirm all recurring journal entries are set up for the month
- [ ] Review open POs for potential accruals
- [ ] Verify fixed asset additions and disposals for the month
- [ ] Confirm payroll processing schedule aligns with close dates

### Core Close Tasks

- [ ] Extract subledger balances from all source systems
- [ ] Run trial balance and verify it is in balance
- [ ] Prepare and submit adjusting journal entries
- [ ] Obtain approvals for all journal entries above materiality threshold
- [ ] Reconcile all control accounts to subledgers
- [ ] Investigate and resolve reconciliation variances
- [ ] Calculate and record depreciation
- [ ] Amortize prepaid expenses per schedule
- [ ] Record revenue accruals and deferrals
- [ ] Record expense accruals
- [ ] Complete intercompany reconciliation and elimination

### Post-Close Review

- [ ] Perform flux analysis (budget vs. actual, prior period vs. actual)
- [ ] Document explanations for all material variances
- [ ] Run SOX control tests and document results
- [ ] Compile close package
- [ ] Obtain Controller sign-off
- [ ] Obtain CFO certification

---

## 3. Journal Entry Procedures

### Entry Types

| Type | Description | Example |
|------|------------|---------|
| Standard/Recurring | Same entry every month, automated | Monthly depreciation, rent expense |
| Adjusting | Corrects balances based on period-end analysis | Accrued salaries for days worked but not yet paid |
| Accrual | Records expenses incurred but not yet invoiced | Consulting fees for work performed in period |
| Deferral | Defers revenue or expense to future period | Prepaid insurance amortization |
| Reclassification | Moves amounts between accounts | Reclass from miscellaneous to correct expense category |
| Correction | Fixes errors in prior entries | Reverse and correct a misclassified transaction |
| Consolidation/Elimination | Removes intercompany transactions | Eliminate intercompany revenue and expense |

### Required Supporting Documentation

Every journal entry must have:

1. **Description**: Clear business purpose explaining why the entry is needed.
2. **Calculation support**: For estimated amounts, show the calculation methodology.
3. **Source documents**: Invoice, contract, schedule, or other primary evidence.
4. **Account mapping**: For each debit and credit line, the account number and amount.
5. **Period**: The close period the entry belongs to.

### Approval Workflow

The approval workflow is driven by the materiality of the entry:

| Entry Amount | Approval Required | Approver |
|-------------|-------------------|----------|
| Below $10,000 | Auto-approved | Governance Engine (with audit log) |
| $10,000 to $49,999 | L1 approval | Accounting Manager |
| $50,000 to $249,999 | L2 approval | Controller |
| $250,000 and above | L3 approval | CFO |

**Segregation of Duties Requirement**: The person who prepares a journal entry cannot be the same person who approves it. This is enforced by the system and tested as part of SOX control SOX-JE-002.

### Non-Standard Entry Review (SOX-JE-003)

All entries that meet any of the following criteria require additional management review:

- Manual (not system-generated) entries
- Non-recurring entries
- Entries above $100,000
- Entries affecting multiple reporting entities
- Top-side adjustments (entries made at the consolidation level)
- Entries with unusual account combinations

---

## 4. Reconciliation Procedures

### Accounts Requiring Reconciliation

All control accounts with subledger detail must be reconciled monthly:

| Account | Reconciliation Source | Tolerance |
|---------|---------------------|-----------|
| Cash (Operating and Payroll) | Bank statements | $0 (exact match after reconciling items) |
| Accounts Receivable | Customer subledger | 1% or $100 |
| Inventory | Perpetual inventory system | 1% or $100 |
| Accounts Payable | Vendor subledger | 1% or $100 |
| Accrued Salaries | Payroll register | $500 (timing differences) |
| Accrued Benefits | Benefits reports | $500 |
| Deferred Revenue | Billing schedule | 1% or $100 |
| Income Tax Payable | Tax provision workpaper | $1,000 |

### Reconciliation Steps

1. **Extract balances**: Pull the GL balance and subledger/external balance as of month end.
2. **Calculate difference**: GL balance minus subledger balance.
3. **Identify reconciling items**: For each difference, determine the cause:
   - Timing differences (items recorded in one system but not the other)
   - Outstanding items (checks not yet cleared, deposits in transit)
   - Errors (mispostings, incorrect amounts)
   - System differences (rounding, currency conversion)
4. **Quantify reconciling items**: Each item must have a dollar amount and description.
5. **Verify explained amount**: Sum of reconciling items should equal the total difference.
6. **Flag unexplained amounts**: Any difference not explained by reconciling items is escalated.
7. **Sign and date**: The preparer signs the reconciliation with the completion date.
8. **Independent review**: A reviewer (different from the preparer) reviews and signs off.

### Reconciliation Quality Standards

- All reconciling items must have a clear description and expected resolution date.
- Stale reconciling items (outstanding for more than 90 days) must be investigated.
- Reconciliations must be completed within 5 business days of period end (SOX-REC-003).
- The reviewer must verify that reconciling items are valid and the methodology is sound.

---

## 5. Flux Analysis Procedures

### Purpose

Flux analysis (also called variance analysis) compares current period results to budget and prior period. Material variances must be investigated and explained. This is a key detective control required by SOX (SOX-VAR-001).

### Materiality Thresholds

A variance is considered material if it meets EITHER of these criteria:
- **Percentage threshold**: Greater than 5% from budget
- **Dollar threshold**: Greater than $25,000 from budget

### Analysis Process

1. **Generate variance report**: Pull actuals, budget, and prior period balances for all accounts.
2. **Identify material variances**: Flag accounts exceeding materiality thresholds.
3. **Investigate causes**: For each material variance, determine the root cause:
   - Timing (revenue or expense recognized in a different period than budgeted)
   - Volume (more or fewer transactions than expected)
   - Rate/Price (unit prices or rates changed from budget assumptions)
   - One-time items (non-recurring events not in the budget)
   - Business changes (new products, markets, or operations)
   - Errors (incorrect recording requiring correction)
4. **Document explanations**: Write a clear, specific explanation for each material variance.
5. **Identify action items**: Note any follow-up actions needed (e.g., budget reforecast, process change).
6. **Management review**: The FP&A Manager reviews the analysis and escalates concerns to the Controller.

### Variance Explanation Standards

Good variance explanation: "Marketing expense is $8,000 (11.4%) over budget due to the Q1 product launch campaign approved in January. The campaign included $5,000 in digital advertising and $3,000 in print materials not originally budgeted."

Poor variance explanation: "Higher than expected." (This is insufficient for SOX purposes.)

---

## 6. Close Package Requirements

### Contents

The close package is the final deliverable of the close process. It must contain:

1. **Executive Summary**: One-page overview of the close, highlighting key items.
2. **Trial Balance**: Complete trial balance showing all account balances.
3. **Journal Entry Register**: List of all adjusting entries posted during the close.
4. **Reconciliation Summary**: Status of all reconciliations with any outstanding items noted.
5. **Variance Analysis Report**: Budget vs. actual analysis with explanations for all material variances.
6. **SOX Control Test Results**: Summary of control tests performed with pass/fail status.
7. **Open Items**: Any unresolved issues or items requiring follow-up.
8. **Sign-off Page**: Signatures from the preparer, Controller, and CFO.

### Quality Standards

- All numbers must tie. The trial balance totals must match the financial statements.
- All reconciliations must be completed and reviewed before the package is finalized.
- All material variances must have documented explanations.
- All SOX controls must be tested with results documented.
- The Controller reviews the entire package before forwarding to the CFO.
- The CFO signs off, confirming the financials are ready for reporting.

### Retention

- Close packages are retained for 7 years per SOX record retention requirements.
- Electronic copies are stored in the document management system with audit trail.
- Physical copies (if any) are stored in a secure, climate-controlled location.
