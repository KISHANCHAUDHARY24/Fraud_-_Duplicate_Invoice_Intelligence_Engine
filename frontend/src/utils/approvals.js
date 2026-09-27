import { Cap } from './permissions'

/** True when the signed-in user can decide on this approval step right now (the backend checks again). */
export function canDecide(approval, user, can) {
  return approval?.decision === 'PENDING' && approval.assigned_to === user?.id && can(Cap.APPROVALS_DECIDE)
}
