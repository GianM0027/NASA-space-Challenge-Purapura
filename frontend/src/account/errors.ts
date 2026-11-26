// ABOUTME: Message to show for a failed account or proposal call (decision D45)
// ABOUTME: Owner: Gian. The backend's `detail` when there is one, else the error text

import { ApiError } from '../api/client'

/** The message to show for a failed account call. */
export function accountError(reason: unknown): string {
  if (reason instanceof ApiError) return reason.detail || `HTTP ${reason.status}`
  return reason instanceof Error ? reason.message : String(reason)
}
