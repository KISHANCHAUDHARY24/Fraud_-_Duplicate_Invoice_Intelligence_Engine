import { Copy, Eye, EyeOff, FileSearch, LogIn, ShieldCheck, Split } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import Alert from '../components/common/Alert'
import Button from '../components/common/Button'
import FormField from '../components/common/FormField'
import { useAuth } from '../hooks/useAuth'

const HIGHLIGHTS = [
  { icon: Copy, text: 'Finds near-duplicate invoices such as INV-1001, INV1001 and INV-100I' },
  { icon: Split, text: 'Spots split purchases, bank-account changes and unusual timing' },
  { icon: FileSearch, text: 'Explains every risk score so reviewers can decide with confidence' },
]

export default function LoginPage() {
  const { user, login, sessionMessage } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ username: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const destination = location.state?.from?.pathname || '/dashboard'
  if (user) return <Navigate to={destination} replace />

  async function handleSubmit(event) {
    event.preventDefault()
    setError(null)
    if (!form.username.trim() || !form.password) {
      setError({ message: 'Enter your username and password.' })
      return
    }
    setSubmitting(true)
    try {
      await login(form.username.trim(), form.password)
      navigate(destination, { replace: true })
    } catch (err) {
      setError(err)
      setSubmitting(false)
    }
  }

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }))

  return (
    <div className="flex min-h-full">
      <section className="relative hidden w-[46%] flex-col justify-between overflow-hidden bg-brand-900 p-12 text-white lg:flex">
        <div className="absolute -top-24 -right-24 size-80 rounded-full bg-brand-700/40 blur-3xl" aria-hidden />
        <div className="relative flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-xl bg-white/10">
            <ShieldCheck className="size-6" aria-hidden />
          </span>
          <span className="text-lg font-semibold">Expense Intelligence</span>
        </div>
        <div className="relative max-w-md">
          <h1 className="text-3xl leading-tight font-semibold">Corporate expense fraud &amp; duplicate invoice intelligence</h1>
          <ul className="mt-8 space-y-4">
            {HIGHLIGHTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3 text-brand-100">
                <Icon className="mt-0.5 size-5 shrink-0 text-white" aria-hidden />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-brand-100/60">
          Risk scores are indicators for human review. They never determine that an invoice is fraudulent.
        </p>
      </section>

      <section className="flex flex-1 items-center justify-center bg-white px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <ShieldCheck className="size-7 text-brand-700" aria-hidden />
            <span className="text-lg font-semibold text-slate-900">Expense Intelligence</span>
          </div>
          <h2 className="text-2xl font-semibold text-slate-900">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">Use the account provided by your administrator.</p>

          {sessionMessage && !error && <Alert tone="warning" className="mt-6">{sessionMessage}</Alert>}
          {error && <Alert tone="error" className="mt-6">{error.message}</Alert>}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
            <FormField label="Username" name="username" autoComplete="username" autoFocus
              value={form.username} onChange={update('username')} />
            <FormField
              label="Password" name="password" autoComplete="current-password"
              type={showPassword ? 'text' : 'password'} value={form.password} onChange={update('password')}
              trailing={
                <button type="button" onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="rounded p-1 text-slate-400 hover:text-slate-600">
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              }
            />
            <Button type="submit" size="lg" className="w-full" loading={submitting} icon={LogIn}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </div>
      </section>
    </div>
  )
}
