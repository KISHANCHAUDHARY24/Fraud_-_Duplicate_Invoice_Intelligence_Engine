/** /vendors/new and /vendors/:id/edit share one form. Only Admins may change a vendor's status. */
import { ArrowLeft } from 'lucide-react'
import { useCallback } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { createVendor, getVendor, updateVendor } from '../api/vendors'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import { ErrorState, LoadingState } from '../components/common/StateViews'
import VendorForm from '../components/vendors/VendorForm'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { Cap } from '../utils/permissions'

const noVendor = () => Promise.resolve(null)

export default function VendorFormPage() {
  const { id } = useParams()
  const { can } = useAuth()
  const navigate = useNavigate()
  const load = useCallback(() => (id ? getVendor(id) : noVendor()), [id])
  const { data: vendor, error, loading, reload } = useAsync(load)

  if (error) return <Card><ErrorState error={error} onRetry={reload} /></Card>
  if (loading) return <LoadingState label="Loading vendor…" />

  async function save(payload) {
    const saved = id ? await updateVendor(id, payload) : await createVendor(payload)
    navigate(`/vendors/${saved.id}`, { replace: !id })
  }

  return (
    <>
      <Link to={id ? `/vendors/${id}` : '/vendors'} className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="size-4" aria-hidden /> {id ? vendor.vendor_name : 'All vendors'}
      </Link>
      <PageHeader title={id ? `Edit ${vendor.vendor_name}` : 'New vendor'}
        description={id ? 'Bank details are changed from the vendor page, so every change is confirmed and reviewed.'
          : 'Similar names are checked, so the same supplier is not added twice.'} />
      <Card className="max-w-3xl">
        <VendorForm key={id || 'new'} vendor={vendor} onSubmit={save} canChangeStatus={Boolean(id) && can(Cap.VENDORS_EDIT)} />
      </Card>
    </>
  )
}
