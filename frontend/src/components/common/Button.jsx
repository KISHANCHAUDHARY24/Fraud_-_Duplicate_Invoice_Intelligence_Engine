import { LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'

const VARIANTS = {
  primary: 'bg-brand-700 text-white hover:bg-brand-800 disabled:bg-brand-700/60',
  secondary: 'bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 disabled:text-slate-400',
  danger: 'bg-red-700 text-white hover:bg-red-800 disabled:bg-red-700/60',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
}
// `icon`: a square icon-only button (give it an aria-label).
const SIZES = { sm: 'h-8 px-3 text-sm gap-1.5', md: 'h-10 px-4 text-sm gap-2', lg: 'h-11 px-5 text-base gap-2', icon: 'size-8 shrink-0' }

export default function Button({
  children, variant = 'primary', size = 'md', loading = false, icon: Icon, className = '', type = 'button', ...props
}) {
  return (
    <button
      type={type}
      disabled={loading || props.disabled}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors
        disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : Icon && <Icon className="size-4" aria-hidden />}
      {children}
    </button>
  )
}

/** A navigation link that looks like a button (never nest a <button> inside a <Link>). */
export function ButtonLink({ to, children, variant = 'primary', size = 'md', icon: Icon, className = '', ...props }) {
  return (
    <Link to={to} className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors
      ${VARIANTS[variant]} ${SIZES[size]} ${className}`} {...props}>
      {Icon && <Icon className="size-4" aria-hidden />}
      {children}
    </Link>
  )
}
