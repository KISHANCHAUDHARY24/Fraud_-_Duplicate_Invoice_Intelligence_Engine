/**
 * The six dashboard charts. Each gets its data straight from GET /api/dashboard/summary/.
 * Single-series charts carry no legend (the title names the series); the multi-series
 * chart has a legend. Every chart has a hover tooltip and a table view (ChartCard).
 */
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

import { formatCurrency } from '../../utils/format'
import ChartCard from './ChartCard'
import ChartLegend from './ChartLegend'
import ChartTooltip from './ChartTooltip'
import {
  BAR_RADIUS_END, BAR_RADIUS_TOP, BAR_SIZE, INK, RISK_RAMP, SERIES, SURFACE, axisProps, formatCompact,
  formatCompactMoney, gridProps, monthLabel,
} from './chartTheme'

const cursorLine = { stroke: INK.axis, strokeWidth: 1 }
const cursorBand = { fill: '#f1f5f9' }
const allZero = (rows, key) => rows.every((row) => !Number(row[key]))

export function MonthlySpendingChart({ data, title = 'Monthly spending',
  subtitle = 'Submitted invoices, last 12 months (drafts and rejected excluded)' }) {
  const rows = data.map((row) => ({ ...row, total: Number(row.total) }))
  return (
    <ChartCard title={title} subtitle={subtitle}
      empty={allZero(rows, 'total')}
      table={{ rows, columns: [
        { key: 'month', label: 'Month', format: monthLabel },
        { key: 'count', label: 'Invoices', align: 'right' },
        { key: 'total', label: 'Spending', align: 'right', format: (v) => formatCurrency(v) },
      ] }}>
      <ResponsiveContainer>
        <AreaChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="month" tickFormatter={monthLabel} {...axisProps} interval="preserveStartEnd" minTickGap={16} />
          <YAxis tickFormatter={formatCompactMoney} {...axisProps} axisLine={false} width={56} />
          <Tooltip cursor={cursorLine} content={<ChartTooltip labelFormatter={monthLabel} valueFormatter={(v) => formatCurrency(v)} />} />
          <Area type="monotone" dataKey="total" name="Spending" stroke={SERIES[0]} strokeWidth={2} fill={SERIES[0]}
            fillOpacity={0.1} activeDot={{ r: 5, stroke: SURFACE, strokeWidth: 2 }} />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

export function AlertsOverTimeChart({ data }) {
  return (
    <ChartCard title="Fraud alerts over time" subtitle="Alerts opened per month (medium risk or higher)"
      empty={allZero(data, 'count')}
      table={{ rows: data, columns: [
        { key: 'month', label: 'Month', format: monthLabel },
        { key: 'count', label: 'Alerts', align: 'right' },
      ] }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="month" tickFormatter={monthLabel} {...axisProps} interval="preserveStartEnd" minTickGap={16} />
          <YAxis allowDecimals={false} {...axisProps} axisLine={false} width={40} />
          <Tooltip cursor={cursorLine} content={<ChartTooltip labelFormatter={monthLabel} />} />
          <Line type="monotone" dataKey="count" name="Alerts" stroke={SERIES[0]} strokeWidth={2} strokeLinecap="round"
            dot={false} activeDot={{ r: 5, stroke: SURFACE, strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

const RISK_LABELS = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical', NOT_ANALYZED: 'Not analysed' }

export function RiskDistributionChart({ data, title = 'Risk distribution', subtitle = 'Invoices by risk level (darker = more severe)' }) {
  const rows = data.map((row) => ({ ...row, label: RISK_LABELS[row.level] }))
  return (
    <ChartCard title={title} subtitle={subtitle}
      empty={allZero(rows, 'count')}
      table={{ rows, columns: [{ key: 'label', label: 'Risk level' }, { key: 'count', label: 'Invoices', align: 'right' }] }}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 32, left: 8, bottom: 0 }} barCategoryGap={8}>
          <CartesianGrid {...gridProps} vertical horizontal={false} />
          <XAxis type="number" allowDecimals={false} {...axisProps} />
          <YAxis type="category" dataKey="label" {...axisProps} axisLine={false} width={92} />
          <Tooltip cursor={cursorBand} content={<ChartTooltip />} />
          <Bar dataKey="count" name="Invoices" barSize={BAR_SIZE} radius={BAR_RADIUS_END}
            label={{ position: 'right', fill: INK.secondary, fontSize: 12 }}>
            {rows.map((row) => <Cell key={row.level} fill={RISK_RAMP[row.level]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

export function StatusDistributionChart({ data }) {
  const rows = data.filter((row) => row.count > 0)
  return (
    <ChartCard title="Invoice status" subtitle="Where invoices are in the workflow" empty={rows.length === 0}
      table={{ rows: data, columns: [{ key: 'label', label: 'Status' }, { key: 'count', label: 'Invoices', align: 'right' }] }}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 32, left: 8, bottom: 0 }} barCategoryGap={8}>
          <CartesianGrid {...gridProps} vertical horizontal={false} />
          <XAxis type="number" allowDecimals={false} {...axisProps} />
          <YAxis type="category" dataKey="label" {...axisProps} axisLine={false} width={112} />
          <Tooltip cursor={cursorBand} content={<ChartTooltip />} />
          <Bar dataKey="count" name="Invoices" fill={SERIES[0]} barSize={BAR_SIZE} radius={BAR_RADIUS_END}
            label={{ position: 'right', fill: INK.secondary, fontSize: 12 }} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

export function VendorRiskChart({ data, subtitle = "Average risk score of each vendor's analysed invoices (top 8)" }) {
  return (
    <ChartCard title="Vendor risk" subtitle={subtitle} empty={data.length === 0}
      table={{ rows: data, columns: [
        { key: 'vendor_name', label: 'Vendor' },
        { key: 'avg_risk', label: 'Avg. risk', align: 'right' },
        { key: 'high_risk', label: 'High / critical', align: 'right' },
        { key: 'invoices', label: 'Invoices', align: 'right' },
      ] }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 32, left: 8, bottom: 0 }} barCategoryGap={6}>
          <CartesianGrid {...gridProps} vertical horizontal={false} />
          <XAxis type="number" domain={[0, 100]} {...axisProps} />
          <YAxis type="category" dataKey="vendor_name" {...axisProps} axisLine={false} width={140}
            tickFormatter={(name) => (name.length > 20 ? `${name.slice(0, 19)}…` : name)} />
          <Tooltip cursor={cursorBand} content={<ChartTooltip valueFormatter={(v) => `${v} / 100`} />} />
          <Bar dataKey="avg_risk" name="Average risk score" fill={SERIES[0]} barSize={18} radius={BAR_RADIUS_END}
            label={{ position: 'right', fill: INK.secondary, fontSize: 12 }} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

const DECISIONS = [
  ['APPROVED', 'Approved'],
  ['REJECTED', 'Rejected'],
  ['CLARIFICATION_REQUESTED', 'Clarification'],
  ['ESCALATED', 'Escalated'],
]

export function ApprovalTrendsChart({ data }) {
  const empty = data.every((row) => DECISIONS.every(([key]) => !row[key]))
  return (
    <ChartCard title="Approval trends" subtitle="Review decisions per month (automatic approvals included)" empty={empty}
      legend={<ChartLegend items={DECISIONS.map(([, label], i) => [label, SERIES[i]])} />}
      table={{ rows: data, columns: [
        { key: 'month', label: 'Month', format: monthLabel },
        ...DECISIONS.map(([key, label]) => ({ key, label, align: 'right' })),
      ] }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="month" tickFormatter={monthLabel} {...axisProps} interval="preserveStartEnd" minTickGap={16} />
          <YAxis allowDecimals={false} tickFormatter={formatCompact} {...axisProps} axisLine={false} width={40} />
          <Tooltip cursor={cursorBand} content={<ChartTooltip labelFormatter={monthLabel} />} />
          {DECISIONS.map(([key, label], i) => (
            // 2px surface-coloured edge = the gap between stacked segments.
            <Bar key={key} dataKey={key} name={label} stackId="decisions" fill={SERIES[i]} stroke={SURFACE}
              strokeWidth={2} barSize={BAR_SIZE} radius={i === DECISIONS.length - 1 ? BAR_RADIUS_TOP : 0} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
