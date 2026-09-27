/** Choice lists mirroring the Django model choices (backend/invoices/models.py). */

export const STATUS_OPTIONS = [
  ['DRAFT', 'Draft'],
  ['SUBMITTED', 'Submitted'],
  ['PROCESSING', 'Processing'],
  ['UNDER_REVIEW', 'Under review'],
  ['APPROVED', 'Approved'],
  ['REJECTED', 'Rejected'],
  ['BLOCKED', 'Blocked'],
  ['PAID', 'Paid (simulated)'],
]

export const RISK_OPTIONS = [
  ['MEDIUM,HIGH,CRITICAL', 'Medium or higher'],
  ['HIGH,CRITICAL', 'High or critical'],
  ['LOW', 'Low'],
  ['MEDIUM', 'Medium'],
  ['HIGH', 'High'],
  ['CRITICAL', 'Critical'],
]

export const CATEGORY_OPTIONS = [
  ['SOFTWARE', 'Software'],
  ['HARDWARE', 'Hardware'],
  ['SERVICES', 'Services'],
  ['CONSULTING', 'Consulting'],
  ['TRAVEL', 'Travel'],
  ['OFFICE_SUPPLIES', 'Office supplies'],
  ['MAINTENANCE', 'Maintenance'],
  ['UTILITIES', 'Utilities'],
  ['MARKETING', 'Marketing'],
  ['OTHER', 'Other'],
]

export const categoryLabel = (value) => CATEGORY_OPTIONS.find(([key]) => key === value)?.[1] || value
