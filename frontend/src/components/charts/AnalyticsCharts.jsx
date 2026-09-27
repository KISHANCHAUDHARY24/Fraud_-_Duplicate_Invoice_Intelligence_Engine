/**
 * Charts for the Analytics page (GET /api/analytics/). Same rules as the dashboard: one value axis,
 * fixed categorical colour order, thin marks, recessive grid, a hover tooltip, and a table view.
 */
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import ChartCard from './ChartCard'
import ChartLegend from './ChartLegend'
import ChartTooltip from './ChartTooltip'
import { BAR_RADIUS_END, INK, SERIES, SURFACE, axisProps, gridProps, monthLabel } from './chartTheme'

const cursorLine = { stroke: INK.axis, strokeWidth: 1 }
const cursorBand = { fill: '#f1f5f9' }
const TREND_SERIES = [['high_risk', 'High / critical invoices'], ['alerts', 'Alerts raised']]

/** Two counts over the same months, so they share one axis (never a second y-axis). */
export function RiskTrendChart({ data }) {
  const empty = data.every((row) => !row.high_risk && !row.alerts)
  return (
    <ChartCard title="Risk over time" subtitle="High / critical invoices (by invoice date) and alerts raised, per month"
      empty={empty} legend={<ChartLegend items={TREND_SERIES.map(([, label], i) => [label, SERIES[i]])} />}
      table={{ rows: data, columns: [
        { key: 'month', label: 'Month', format: monthLabel },
        ...TREND_SERIES.map(([key, label]) => ({ key, label, align: 'right' })),
      ] }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="month" tickFormatter={monthLabel} {...axisProps} interval="preserveStartEnd" minTickGap={16} />
          <YAxis allowDecimals={false} {...axisProps} axisLine={false} width={40} />
          <Tooltip cursor={cursorLine} content={<ChartTooltip labelFormatter={monthLabel} />} />
          {TREND_SERIES.map(([key, label], i) => (
            <Line key={key} type="monotone" dataKey={key} name={label} stroke={SERIES[i]} strokeWidth={2}
              strokeLinecap="round" dot={data.length <= 3 ? { r: 4, fill: SERIES[i], stroke: SURFACE, strokeWidth: 2 } : false}
              activeDot={{ r: 5, stroke: SURFACE, strokeWidth: 2 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/**
 * A ranked horizontal bar chart (one series): spending by department, signals that fire most, ...
 * columns: the table view's columns; `format` formats the value on the bars and in the tooltip.
 */
export function RankedBarChart({ title, subtitle, rows, labelKey = 'label', valueKey, valueName, format = String,
  columns, labelWidth = 128, emptyMessage }) {
  const height = Math.max(160, rows.length * 34 + 24)
  return (
    <ChartCard title={title} subtitle={subtitle} empty={rows.length === 0} emptyMessage={emptyMessage}
      table={{ rows, columns }} height={height}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 56, left: 8, bottom: 0 }} barCategoryGap={6}>
          <CartesianGrid {...gridProps} vertical horizontal={false} />
          <XAxis type="number" tickFormatter={format} {...axisProps} allowDecimals={false} />
          <YAxis type="category" dataKey={labelKey} {...axisProps} axisLine={false} width={labelWidth}
            tickFormatter={(name) => (String(name).length > 18 ? `${String(name).slice(0, 17)}…` : name)} />
          <Tooltip cursor={cursorBand} content={<ChartTooltip valueFormatter={format} />} />
          <Bar dataKey={valueKey} name={valueName} fill={SERIES[0]} barSize={18} radius={BAR_RADIUS_END}
            label={{ position: 'right', fill: INK.secondary, fontSize: 12, formatter: format }} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
