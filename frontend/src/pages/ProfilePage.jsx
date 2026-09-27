import { KeyRound } from 'lucide-react'
import { useState } from 'react'

import { changePassword } from '../api/auth'
import Alert from '../components/common/Alert'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import FormField from '../components/common/FormField'
import PageHeader from '../components/common/PageHeader'
import { useAuth } from '../hooks/useAuth'
import { formatDateTime } from '../utils/format'

function Detail({ label, value }) {
  return (
    <div className="py-3 sm:grid sm:grid-cols-3 sm:gap-4">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-slate-800 sm:col-span-2 sm:mt-0">{value || '—'}</dd>
    </div>
  )
}

const EMPTY = { old_password: '', new_password: '', confirm: '' }

function ChangePasswordForm() {
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [result, setResult] = useState(null)
  const [saving, setSaving] = useState(false)

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }))

  async function submit(event) {
    event.preventDefault()
    setResult(null)
    if (form.new_password !== form.confirm) {
      setErrors({ confirm: 'The two new passwords do not match.' })
      return
    }
    setErrors({})
    setSaving(true)
    try {
      await changePassword(form.old_password, form.new_password)
      setForm(EMPTY)
      setResult({ tone: 'success', message: 'Password changed. Other devices have been signed out.' })
    } catch (error) {
      const details = error.details || {}
      setErrors({ old_password: details.old_password?.[0], new_password: details.new_password?.[0] })
      setResult({ tone: 'error', message: error.message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card title="Change password" subtitle="At least 8 characters; not too common and not only numbers.">
      {result && <Alert tone={result.tone} className="mb-4">{result.message}</Alert>}
      <form onSubmit={submit} className="space-y-4" noValidate>
        <FormField label="Current password" type="password" autoComplete="current-password"
          value={form.old_password} onChange={update('old_password')} error={errors.old_password} />
        <FormField label="New password" type="password" autoComplete="new-password"
          value={form.new_password} onChange={update('new_password')} error={errors.new_password} />
        <FormField label="Confirm new password" type="password" autoComplete="new-password"
          value={form.confirm} onChange={update('confirm')} error={errors.confirm} />
        <Button type="submit" icon={KeyRound} loading={saving}
          disabled={!form.old_password || !form.new_password || !form.confirm}>
          Change password
        </Button>
      </form>
    </Card>
  )
}

export default function ProfilePage() {
  const { user } = useAuth()
  return (
    <>
      <PageHeader title="My profile" description="Your account details and what your role allows you to do." />
      <div className="grid gap-6 [&>*]:min-w-0 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          <Card title="Account">
            <dl className="-my-3 divide-y divide-slate-100">
              <Detail label="Full name" value={user.full_name} />
              <Detail label="Username" value={user.username} />
              <Detail label="Email" value={user.email} />
              <Detail label="Role" value={user.role_name} />
              <Detail label="Department" value={user.department} />
              <Detail label="Last sign-in" value={formatDateTime(user.last_login)} />
            </dl>
          </Card>
          <Card title="Permissions" subtitle="Granted by your role and checked by the server on every request.">
            <ul className="flex flex-wrap gap-2">
              {user.permissions.map((permission) => (
                <li key={permission} className="rounded-md bg-slate-100 px-2 py-1 font-mono text-xs text-slate-700">{permission}</li>
              ))}
            </ul>
          </Card>
        </div>
        <div className="lg:col-span-2">
          <ChangePasswordForm />
        </div>
      </div>
    </>
  )
}
