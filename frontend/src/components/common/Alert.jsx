import { CircleAlert, CircleCheckBig, Info, TriangleAlert } from 'lucide-react'

const TONES = {
  error: { box: 'border-red-200 bg-red-50 text-red-800', icon: CircleAlert },
  warning: { box: 'border-amber-200 bg-amber-50 text-amber-900', icon: TriangleAlert },
  success: { box: 'border-green-200 bg-green-50 text-green-800', icon: CircleCheckBig },
  info: { box: 'border-blue-200 bg-blue-50 text-blue-800', icon: Info },
}

export default function Alert({ tone = 'info', title, children, className = '' }) {
  const { box, icon: Icon } = TONES[tone]
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`flex gap-3 rounded-lg border px-4 py-3 text-sm ${box} ${className}`}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div>
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? 'mt-0.5' : ''}>{children}</div>}
      </div>
    </div>
  )
}
