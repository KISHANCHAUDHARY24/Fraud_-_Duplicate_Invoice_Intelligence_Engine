/** Vendor and bank-account checks, the same rules as backend/vendors (fast feedback; the server decides). */

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Same rule as the backend: 6–34 letters or digits once spaces and dashes are removed (IBANs allowed). */
export const isValidAccountNumber = (value) => /^[A-Za-z0-9]{6,34}$/.test(value.replace(/[\s-]/g, ''))
export const ACCOUNT_NUMBER_HELP = 'Use 6–34 letters or digits (spaces and dashes are ignored).'

export function validateVendor(values, { creating }) {
  const errors = {}
  if (values.vendor_name.trim().length < 2) errors.vendor_name = 'Vendor name must be at least 2 characters.'
  if (values.email.trim() && !EMAIL.test(values.email.trim())) errors.email = 'Enter a valid email address.'
  if (creating && Boolean(values.bank_name.trim()) !== Boolean(values.account_number.trim())) {
    errors[values.bank_name.trim() ? 'account_number' : 'bank_name'] = 'Enter both the bank name and the account number, or neither.'
  }
  if (creating && values.account_number.trim() && !isValidAccountNumber(values.account_number)) {
    errors.account_number = ACCOUNT_NUMBER_HELP
  }
  return errors
}
