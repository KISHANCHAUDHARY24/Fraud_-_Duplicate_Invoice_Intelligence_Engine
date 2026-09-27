/** Choice lists mirroring the Django model choices for vendors, fraud alerts and approvals. */

export const VENDOR_STATUS_OPTIONS = [
  ['ACTIVE', 'Active'],
  ['UNDER_REVIEW', 'Under review'],
  ['INACTIVE', 'Inactive'],
  ['BLOCKED', 'Blocked'],
]

export const ALERT_STATUS_OPTIONS = [
  ['OPEN,IN_REVIEW', 'Open or in review'],
  ['OPEN', 'Open'],
  ['IN_REVIEW', 'In review'],
  ['RESOLVED', 'Resolved'],
  ['DISMISSED', 'Dismissed'],
]

export const SEVERITY_OPTIONS = [
  ['HIGH,CRITICAL', 'High or critical'],
  ['MEDIUM', 'Medium'],
  ['HIGH', 'High'],
  ['CRITICAL', 'Critical'],
]

export const SIGNAL_TYPE_OPTIONS = [
  ['DUPLICATE', 'Possible duplicate'],
  ['AMOUNT_ANOMALY', 'Amount anomaly'],
  ['TIME_ANOMALY', 'Unusual submission time'],
  ['THRESHOLD_PROXIMITY', 'Near approval threshold'],
  ['SPLIT_PURCHASE', 'Potential split purchase'],
  ['BANK_ACCOUNT_CHANGE', 'Bank account change'],
  ['ROUND_AMOUNT', 'Round amount'],
  ['VENDOR_ANOMALY', 'Vendor anomaly'],
  ['ML_ANOMALY', 'Machine-learning anomaly'],
]

export const OUTCOME_OPTIONS = [
  ['CLEARED', 'Cleared: the invoice is legitimate'],
  ['CONFIRMED_ISSUE', 'Issue confirmed: reject the invoice'],
]

export const DECISION_OPTIONS = [
  ['PENDING', 'Waiting for me'],
  ['APPROVED', 'Approved'],
  ['REJECTED', 'Rejected'],
  ['CLARIFICATION_REQUESTED', 'Clarification requested'],
  ['ESCALATED', 'Escalated'],
]

export const LEVEL_OPTIONS = [
  ['STANDARD', 'Standard approval'],
  ['MANAGER', 'Manager review'],
  ['AUDITOR', 'Auditor review'],
]

const lookup = (options) => (value) => options.find(([key]) => key === value)?.[1] || value
export const signalTypeLabel = lookup(SIGNAL_TYPE_OPTIONS)
export const levelLabel = lookup(LEVEL_OPTIONS)
