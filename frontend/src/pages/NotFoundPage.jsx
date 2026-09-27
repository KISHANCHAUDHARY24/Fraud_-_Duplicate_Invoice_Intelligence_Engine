import { FileQuestion } from 'lucide-react'
import { Link } from 'react-router-dom'

import { EmptyState } from '../components/common/StateViews'

export default function NotFoundPage() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white">
      <EmptyState
        icon={FileQuestion}
        title="Page not found"
        message="The page you are looking for does not exist, or you may not have access to it."
        action={<Link to="/dashboard" className="text-sm font-medium text-brand-700 hover:underline">Go to the dashboard</Link>}
      />
    </div>
  )
}
