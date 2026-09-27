/**
 * Business-rule settings (thresholds, weights, working hours...). Admins edit; Managers and Auditors
 * may view them, so they understand why an invoice was scored or routed the way it was.
 */
import { Info } from 'lucide-react'
import { useState } from 'react'

import { listSettings } from '../api/settings'
import Alert from '../components/common/Alert'
import Card from '../components/common/Card'
import PageHeader from '../components/common/PageHeader'
import { ErrorState, LoadingState } from '../components/common/StateViews'
import SettingEditor from '../components/settings/SettingEditor'
import { useAsync } from '../hooks/useAsync'
import { useAuth } from '../hooks/useAuth'
import { Cap } from '../utils/permissions'
import { SETTING_GROUPS, metaFor } from '../utils/settingsMeta'

export default function SettingsPage() {
  const { can } = useAuth()
  const canEdit = can(Cap.SETTINGS_MANAGE)
  const { data, error, reload } = useAsync(listSettings)
  const [notice, setNotice] = useState(null)

  if (error) return <Card><ErrorState error={error} onRetry={reload} /></Card>
  if (!data) return <LoadingState label="Loading settings…" />

  const byKey = Object.fromEntries(data.map((setting) => [setting.key, setting]))
  const grouped = new Set(SETTING_GROUPS.flatMap((group) => group.keys))
  const groups = [
    ...SETTING_GROUPS.map((group) => ({ ...group, settings: group.keys.map((key) => byKey[key]).filter(Boolean) })),
    { title: 'Other', description: 'Settings without a dedicated editor.', settings: data.filter((s) => !grouped.has(s.key)) },
  ].filter((group) => group.settings.length > 0)

  const onSaved = (setting, how) => {
    setNotice(`${metaFor(setting.key).label} ${how === 'reset' ? 'was reset to its default' : 'was saved'}. New analyses use it from now on.`)
    reload()
  }

  return (
    <>
      <PageHeader title="Settings" description="The business rules behind duplicate detection, risk scoring and approval routing." />
      {!canEdit && (
        <Alert tone="info" className="mb-6">
          <span className="inline-flex items-center gap-1.5"><Info className="size-4" aria-hidden />
            You can view these settings; only an Administrator can change them.</span>
        </Alert>
      )}
      {canEdit && (
        <Alert tone="warning" className="mb-6" title="Changes apply to new analyses only">
          Invoices already analysed keep their score until they are re-analysed. Every change is recorded in the audit log with the old and new value.
        </Alert>
      )}
      {notice && <Alert tone="success" className="mb-6">{notice}</Alert>}
      <div className="space-y-6">
        {groups.map((group) => (
          <Card key={group.title} title={group.title} subtitle={group.description}>
            <div className="divide-y divide-slate-100">
              {group.settings.map((setting) => (
                // Keyed by the last change, so the editor restarts from the saved value after a save or reset.
                <SettingEditor key={`${setting.key}-${setting.updated_at}`} setting={setting} canEdit={canEdit} onSaved={onSaved} />
              ))}
            </div>
          </Card>
        ))}
      </div>
    </>
  )
}
