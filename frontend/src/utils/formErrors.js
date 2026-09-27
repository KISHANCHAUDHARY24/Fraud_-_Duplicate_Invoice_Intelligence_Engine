/**
 * Map a backend VALIDATION_ERROR ({details: {field: ["message", ...]}}) to {field: "first message"},
 * keeping only fields the form actually shows (other problems appear in the form's error banner).
 */
export function fieldErrors(error, fields) {
  const details = error?.details && typeof error.details === 'object' && !Array.isArray(error.details) ? error.details : {}
  return Object.fromEntries(Object.entries(details).filter(([key]) => fields.includes(key))
    .map(([key, messages]) => [key, [].concat(messages)[0]]))
}
