# SOX Compliance Guide

## Overview

The Sarbanes-Oxley Act of 2002 (SOX) requires public companies to establish and maintain adequate internal controls over financial reporting (ICFR). This guide covers the requirements relevant to the month-end close process, including control design, testing procedures, and deficiency evaluation.

---

## 1. Section 302: Corporate Responsibility for Financial Reports

### Requirements

Section 302 requires the CEO and CFO to personally certify that:

1. They have reviewed the financial statements.
2. The statements do not contain untrue statements of material fact or omit material facts.
3. The financial statements fairly present the financial condition and results of operations.
4. They are responsible for establishing and maintaining internal controls.
5. They have disclosed any significant deficiencies or material weaknesses to the audit committee.
6. They have disclosed any fraud involving management or employees who have a significant role in ICFR.

### Implications for the Close Process

- The close process must produce financial statements that the CEO and CFO can certify with confidence.
- Every material account balance must be supported by documentation.
- All significant estimates must have a documented basis.
- The close package must provide sufficient evidence for the certifying officers to fulfill their obligations.

---

## 2. Section 404: Management Assessment of Internal Controls

### Requirements

Section 404 requires:

1. **Management assessment**: Management must assess the effectiveness of ICFR as of the fiscal year end.
2. **Auditor attestation**: The external auditor must attest to management's assessment (for accelerated filers).

### Control Framework

The organization uses the COSO Internal Control Framework (2013) with five components:

1. **Control Environment**: Tone at the top, organizational structure, commitment to competence.
2. **Risk Assessment**: Identification of risks to reliable financial reporting.
3. **Control Activities**: Policies and procedures that address identified risks.
4. **Information and Communication**: Systems that capture and communicate relevant information.
5. **Monitoring**: Ongoing evaluation of control effectiveness.

### Key Controls in the Close Process

| Control ID | Control Name | Category | Type |
|-----------|-------------|----------|------|
| SOX-JE-001 | Journal Entry Authorization | Journal Entry | Preventive |
| SOX-JE-002 | Segregation of Duties | Segregation | Preventive |
| SOX-JE-003 | Non-Standard JE Review | Journal Entry | Detective |
| SOX-REC-001 | Reconciliation Completeness | Reconciliation | Detective |
| SOX-REC-002 | Reconciliation Review | Reconciliation | Detective |
| SOX-REC-003 | Timely Reconciliation | Reconciliation | Detective |
| SOX-VAR-001 | Flux Analysis Review | Reporting | Detective |
| SOX-ACC-001 | System Access Controls | Access | Preventive |
| SOX-CLS-001 | Close Checklist Completion | Reporting | Detective |
| SOX-CLS-002 | Management Review | Reporting | Detective |

---

## 3. Internal Controls over Financial Reporting (ICFR)

### Control Types

- **Preventive controls** stop errors or fraud before they occur. Examples: segregation of duties, authorization limits, system access restrictions.
- **Detective controls** identify errors or fraud after they occur. Examples: reconciliations, management reviews, variance analysis.

### Control Design Principles

1. **Precision**: The control must be precise enough to detect a material misstatement. A control that reviews totals is less precise than one that reviews individual transactions.
2. **Competence**: The person performing the control must have the knowledge and authority to do so effectively.
3. **Segregation**: No single individual should control all aspects of a transaction (initiation, authorization, recording, custody).
4. **Documentation**: The control must be documented, including who performs it, when, and what evidence is retained.

### Automated vs. Manual Controls

- **Automated controls** (system-enforced) are tested once and relied upon continuously, assuming IT general controls (ITGCs) are effective. Examples: system-enforced approval workflows, automated three-way matching.
- **Manual controls** require testing each period because human execution varies. Examples: management review of reconciliations, manual journal entry approval.
- **IT-dependent manual controls** combine both. The system generates a report (automated), and a person reviews it (manual). Both the report accuracy and the review quality must be tested.

---

## 4. Control Testing Procedures

### Testing Approach

1. **Inquiry**: Ask the control owner how the control operates. This alone is insufficient.
2. **Observation**: Watch the control being performed. Useful for understanding the process.
3. **Inspection**: Examine evidence that the control was performed (signatures, timestamps, system logs).
4. **Re-performance**: Independently execute the control to verify it produces the expected result.

### Sample Sizes

The number of items to test depends on the control frequency:

| Control Frequency | Minimum Sample Size |
|------------------|-------------------|
| Annual | 1 |
| Quarterly | 2 |
| Monthly | 2-5 |
| Weekly | 5-15 |
| Daily | 20-25 |
| Multiple per day | 25-40 |

### Evidence Requirements

For each control test, document:
- Control being tested (ID and description)
- Period covered by the test
- Who performed the test
- Date of the test
- Sample selected and rationale
- Test procedures performed
- Results (pass/fail for each item)
- Exceptions noted and their significance
- Overall conclusion

---

## 5. Deficiency Classification

### Definitions

- **Control Deficiency**: A control does not operate effectively, but the deficiency is not severe enough to be classified as a significant deficiency or material weakness.
- **Significant Deficiency**: A deficiency (or combination of deficiencies) that is less severe than a material weakness but is important enough to merit the attention of those responsible for oversight of financial reporting.
- **Material Weakness**: A deficiency (or combination of deficiencies) such that there is a reasonable possibility that a material misstatement of the financial statements will not be prevented or detected on a timely basis.

### Evaluation Factors

When classifying a deficiency, consider:

1. **Likelihood**: How likely is it that the deficiency could result in a misstatement?
2. **Magnitude**: If a misstatement occurred, how large could it be?
3. **Nature of accounts affected**: Are they susceptible to fraud or error?
4. **Subjectivity**: Does the account involve significant estimates or judgment?
5. **Compensating controls**: Are there other controls that mitigate the risk?
6. **Pervasiveness**: Does the deficiency affect multiple accounts or assertions?

### Indicators of Material Weakness

- Restatement of previously issued financial statements
- Identification of fraud by management (of any amount)
- Override of controls by management
- Ineffective oversight by the audit committee
- Failure to timely detect material adjustments through the normal close process

### Remediation

All significant deficiencies and material weaknesses require a remediation plan with:
- Root cause analysis
- Specific corrective actions
- Responsible parties
- Target completion dates
- Evidence that the remediated control operates effectively

---

## 6. Management Assessment Requirements

### Annual Assessment

Management must assess ICFR effectiveness as of fiscal year end. The assessment includes:

1. Identification of all significant accounts, disclosures, and relevant assertions.
2. Documentation of all key controls that address the risk of material misstatement.
3. Testing of each key control to evaluate operating effectiveness.
4. Evaluation of any deficiencies identified during testing.
5. A conclusion on whether ICFR is effective as of the assessment date.

### Ongoing Monitoring

Throughout the year, management monitors control effectiveness through:
- Monthly close process controls (reconciliations, reviews, approvals)
- Quarterly management review of financial results
- Internal audit testing
- Incident reporting and resolution tracking

---

## 7. Auditor Reliance on Automated Controls

### When Auditors Rely on Automated Controls

External auditors can place greater reliance on automated controls because:
- Once properly configured, automated controls perform consistently without variation.
- Automated controls are not subject to human error, fatigue, or judgment.
- The same automated control applies uniformly to all transactions.

### Requirements for Reliance

For auditors to rely on automated controls, the following must be demonstrated:

1. **IT General Controls (ITGCs)** are effective. This includes:
   - Access management (who can change the system)
   - Change management (how system changes are controlled)
   - Computer operations (backup, recovery, job scheduling)
   - System development (how new systems are implemented)

2. **Application controls** are properly configured:
   - System-enforced approval workflows operate as designed
   - Automated calculations produce correct results
   - System access is restricted to authorized users
   - Audit logs capture all relevant activity

3. **Baseline testing** is performed when the control is first implemented or after any change.

### AI-Augmented Controls

When AI agents participate in the control process:
- The AI decision must be logged with full reasoning and confidence score.
- Human oversight must be maintained for material decisions.
- The AI system must be subject to the same change management controls as other systems.
- Periodic validation must confirm the AI continues to operate as designed.
- The governance engine serves as the automated control layer, enforcing policies consistently.
