/** Quick browser-side checks that mirror the Django serializer (the server remains the authority). */
export function validateInvoice(values, today = new Date().toISOString().slice(0, 10)) {
  const errors = {}
  if (!values.vendor) errors.vendor = 'Choose the vendor.'
  if (!values.invoice_number.trim()) errors.invoice_number = 'Enter the invoice number.'
  if (!values.invoice_date) errors.invoice_date = 'Enter the invoice date.'
  else if (values.invoice_date > today) errors.invoice_date = 'Invoice date cannot be in the future.'
  if (values.due_date && values.invoice_date && values.due_date < values.invoice_date) {
    errors.due_date = 'Due date cannot be before the invoice date.'
  }
  if (!(Number(values.amount) > 0)) errors.amount = 'Invoice amount must be greater than zero.'
  if (Number(values.tax) < 0) errors.tax = 'Tax cannot be negative.'
  if (!/^[A-Za-z]{3}$/.test(values.currency.trim())) errors.currency = 'Use a 3-letter code, e.g. USD.'
  if (values.description.trim().length < 3) errors.description = 'Description must be at least 3 characters.'
  return errors
}
