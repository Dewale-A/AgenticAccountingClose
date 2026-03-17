# AgenticAccountingClose: The Story Behind the System

## The Problem Everyone Knows But Nobody Has Solved

Every month, accounting teams go through the same ritual. The books need to close. Trial balances need to be pulled. Adjusting entries need to be prepared, reviewed, and approved. Accounts need to be reconciled. Variances need to be explained. SOX controls need to be tested. And a close package needs to land on the Controller's desk, ready for sign-off.

This process typically takes 5 to 10 business days. It involves dozens of people touching spreadsheets, chasing approvals, and manually verifying that nobody cut corners. The work is repetitive, high-stakes, and unforgiving. Miss one accrual, and the financials are wrong. Skip one reconciliation, and an auditor flags it six months later. Let the wrong person approve their own journal entry, and you have a SOX deficiency.

The question is not whether AI can help. It can. The question is: **how do you deploy AI in a process where a single mistake can trigger a material weakness finding?**

Most teams that try to automate the close start by building the AI first and adding controls later. They discover too late that retrofitting governance into an automated pipeline is like installing brakes on a car that is already moving.

This project takes the opposite approach.

## Governance First, Then Automation

AgenticAccountingClose is a multi-agent system where the governance layer was designed before a single agent was built. The reason is simple: in a SOX-regulated environment, the controls are not optional features. They are the foundation.

The system has six AI agents. Each one is a specialist, the same way an accounting department has specialists. And the same way that no single person in a well-run accounting department has unchecked authority, no single agent in this system operates without oversight.

Here is how the pipeline works, and why each agent exists.

## The Six Agents

### Agent 1: Data Collection Analyst

**What it does:** Gathers balances from every subledger system (AP, AR, Payroll, Inventory, Fixed Assets, Treasury) and compiles the trial balance.

**Why it exists as a separate agent:** In every accounting close, the trial balance is the foundation. If the starting data is wrong, everything downstream is wrong. This agent is modeled after the data analyst who spends the first day of close pulling numbers from six different systems and making sure total debits equal total credits before anyone else starts working.

**Why it matters:** An accounting professional knows that the trial balance is not just a report. It is a control point. By isolating this step in its own agent, the system can verify data quality before the more complex work begins. If something looks unusual compared to prior periods, this agent flags it before it contaminates downstream analysis.

### Agent 2: Journal Entry Accountant

**What it does:** Analyzes the trial balance and prepares all adjusting entries: accruals, deferrals, depreciation, prepaid amortization, and reclassifications.

**Why it exists as a separate agent:** Journal entries are where judgment lives. How much salary should we accrue for days worked since the last payroll? What is the correct depreciation for this period? These calculations require domain expertise and clear documentation.

**Why it matters:** Every entry this agent creates passes through the governance engine's materiality gate. An entry below $10,000 can be auto-approved. An entry between $10,000 and $50,000 requires a manager. Between $50,000 and $250,000, the Controller must approve. Above $250,000, it goes to the CFO. This mirrors exactly how a well-controlled accounting department operates, with one critical addition: the agent that prepares the entry is never the one that approves it.

### Agent 3: Reconciliation Specialist

**What it does:** Compares GL balances to subledger balances for every control account, investigates discrepancies, and documents reconciling items.

**Why it exists as a separate agent:** Reconciliation is one of the most important detective controls in SOX. It is how you catch errors, omissions, and fraud. A cash reconciliation catches outstanding checks. An AR reconciliation catches unapplied payments. An inventory reconciliation catches count adjustments.

**Why it matters:** This agent does not dismiss small differences as "immaterial" without understanding the cause. A $3,245 difference in cash might be three outstanding checks. That is expected. But a $3,245 difference with no explanation might be something else entirely. The agent documents every reconciling item with a description, amount, and expected resolution date, exactly what an auditor would review.

### Agent 4: Financial Analyst (FP&A)

**What it does:** Performs flux analysis by comparing current period actuals to budget and prior period. Identifies, investigates, and explains material variances.

**Why it exists as a separate agent:** Variance analysis is the section auditors scrutinize most heavily. "Higher than expected" is never an acceptable explanation. Auditors want to know: Was it timing? Volume? A rate change? A one-time event?

**Why it matters:** This agent classifies each variance using standard categories and quantifies the impact. Revenue up 8% because of a contract that started mid-month is fundamentally different from revenue up 8% for no identifiable reason. The first is a timing variance. The second is a red flag. Material variances (above 5% or $25,000) are flagged automatically and require documented explanations before the close can proceed.

### Agent 5: SOX Compliance Officer

**What it does:** Tests 10 SOX controls for the close period and classifies any deficiencies.

**Why it exists as a separate agent:** This is the internal audit function. It tests controls by examining actual evidence, not by taking management's word for it. When testing journal entry authorization, it pulls a sample of entries above the materiality threshold and verifies each has approval from someone other than the preparer. When testing reconciliation completeness, it verifies every required account was reconciled within the deadline.

**Why it matters:** A single missed approval might be a control deficiency. A pattern of missed approvals is a significant deficiency, or worse, a material weakness. This agent classifies findings with the rigor expected in an external audit. Its test results are documented with evidence, sample sizes, exceptions, and conclusions.

### Agent 6: Close Review Manager

**What it does:** Reviews everything the other five agents produced and generates the close package summary for Controller and CFO sign-off.

**Why it exists as a separate agent:** Separation of review from execution is a fundamental control principle. The agents that did the work should not be the ones certifying it is complete. The Review Agent reads the entire pipeline's output with a critical eye and produces a summary that a Controller can read in five minutes and know whether the close is clean or has issues.

**Why it matters:** The close package is organized into sections: financial highlights, adjusting entries, reconciliation status, variance analysis, compliance status, and open items. Anything that could be a problem for external auditors is flagged. This is the artifact that sits in the audit file.

## The Governance Engine: The Real Innovation

The agents are important, but they are not the innovation. The innovation is the governance engine that governs all of them.

**Materiality Gates:** Every journal entry is evaluated against configurable dollar thresholds. The system routes items to the appropriate approval level automatically. Start conservative. Increase thresholds as trust builds.

**Segregation of Duties:** Enforced at the architecture level. The system does not allow the preparer to approve their own entry. This is not a policy that people might forget. It is code that will not execute.

**Four-Eyes Principle:** Material items require at least two reviewers before posting. The governance engine tracks who reviewed what and when.

**Confidence-Based Escalation:** When an agent is uncertain (confidence below 0.7), it escalates to a human rather than guessing. In finance, an honest "I am not sure" is infinitely better than a confident wrong answer.

**Immutable Audit Trail:** Every agent decision, every governance routing, every approval, every rejection is logged with timestamps, actors, and reasons. The supervisor agents receive the same scrutiny as the worker agents. Nobody is above the audit trail.

## The Framework: Why CrewAI

The system is built on CrewAI, a framework for orchestrating multiple AI agents in a defined workflow. The choice was deliberate:

**Sequential pipeline:** Agents run in strict order because each depends on the previous agent's output. You cannot reconcile accounts without the trial balance. You cannot test SOX controls without journal entries and reconciliations. CrewAI's sequential process enforces this dependency chain.

**Specialization over generalization:** Each agent has a defined role, goal, and backstory that shapes its reasoning. An agent told "you are a senior accountant with 15 years of SOX audit experience" produces fundamentally different reasoning than a generic assistant. Domain expertise is encoded into the agent's identity.

**No delegation:** Agents do not hand work to each other. Each completes its defined scope and passes the output forward. This is intentional. In a controlled environment, you want clear accountability for who did what.

## The Bigger Picture

This project demonstrates that agentic AI in regulated industries does not have to be a governance nightmare. The controls that make accounting reliable (segregation of duties, materiality thresholds, audit trails, independent review) can be built into the AI architecture itself.

The approach works because it respects a fundamental truth: **automation without controls is not efficiency. It is risk.**

The agents are the workforce. The governance engine is the control environment. Together, they show what a responsible, production-aware approach to AI in accounting looks like.

---

*Built by Wale Aderonmu. Part of a portfolio demonstrating governance-first agentic AI design for financial services.*
