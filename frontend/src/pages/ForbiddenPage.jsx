import { Lock } from 'lucide-react'
import { Link } from 'react-router-dom'

import { EmptyState } from '../components/common/StateViews'

export default function ForbiddenPage() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <EmptyState
        icon={Lock}
        title="You do not have access to this page"
        message="Your role does not include this area. If you need access, ask an administrator."
        action={<Link to="/dashboard" className="text-sm font-medium text-brand-700 hover:underline">Go to the dashboard</Link>}
      />
    </div>
  )
}
