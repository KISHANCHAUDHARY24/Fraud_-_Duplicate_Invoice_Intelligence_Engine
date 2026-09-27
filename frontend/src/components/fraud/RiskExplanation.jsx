/** The explainable part of an analysis: summary, ranked reasons with points, warnings, disclaimer. */
import { BrainCircuit, CircleCheck, Info } from 'lucide-react'

import { formatDateTime } from '../../utils/format'
import Alert from '../common/Alert'

/** "98% similarity with invoice INV-1001 (+29)" -> ["98% similarity with invoice INV-1001", 29] */
function splitPoints(line) {
  const match = line.match(/^(.*) \(\+(\d+)\)$/)
  return match ? [match[1], Number(match[2])] : [line, null]
}

export default function RiskExplanation({ analysis }) {
  const reasons = analysis.explanation || []
  return (
    <div>
      <p className="text-sm font-medium text-slate-800">{analysis.summary}</p>
      {reasons.length === 0 ? (
        <p className="mt-3 flex items-center gap-2 text-sm text-slate-600">
          <CircleCheck className="size-4 text-green-600" aria-hidden /> No risk indicators were found.
        </p>
      ) : (
        <ol className="mt-3 space-y-2" aria-label="Reasons for the risk score">
          {reasons.map((line) => {
            const [text, points] = splitPoints(line)
            return (
              <li key={line} className="flex items-start gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="mt-0.5 text-slate-400" aria-hidden>✓</span>
                <span className="flex-1 text-slate-700">{text}</span>
                {points !== null && (
                  <span className="rounded-md bg-white px-2 py-0.5 text-xs font-semibold text-slate-700 tabular-nums ring-1 ring-slate-200">
                    +{points}
                  </span>
                )}
              </li>
            )
          })}
        </ol>
      )}
      {analysis.warnings?.map((warning) => <Alert key={warning} tone="warning" className="mt-3">{warning}</Alert>)}
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
        <span className="flex items-center gap-1"><BrainCircuit className="size-3.5" aria-hidden />
          Model {analysis.model_version || 'not available'}</span>
        <span>Analysed {formatDateTime(analysis.analyzed_at)}</span>
      </div>
      <p className="mt-2 flex items-start gap-1.5 text-xs text-slate-500">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {analysis.disclaimer}
      </p>
    </div>
  )
}
