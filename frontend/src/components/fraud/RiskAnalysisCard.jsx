/** Gauge + explained score, or a placeholder when there is no analysis yet. Used on invoice and alert pages. */
import Card from '../common/Card'
import RiskExplanation from './RiskExplanation'
import RiskScoreGauge from './RiskScoreGauge'

export default function RiskAnalysisCard({ analysis, emptyMessage = 'No analysis is available for this invoice.' }) {
  return (
    <Card title="Risk analysis" subtitle="Why this invoice got its score">
      {analysis ? (
        <div className="grid gap-6 [&>*]:min-w-0 xl:grid-cols-[auto_1fr]">
          <div className="flex justify-center xl:block">
            <RiskScoreGauge score={analysis.risk_score} level={analysis.risk_level} />
          </div>
          <RiskExplanation analysis={analysis} />
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <RiskScoreGauge score={null} level={null} />
          <p className="max-w-md text-sm text-slate-500">{emptyMessage}</p>
        </div>
      )}
    </Card>
  )
}
