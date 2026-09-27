/**
 * Half-circle meter for the 0-100 risk score. The fill carries severity; the unfilled track is a
 * light neutral. The number and the RiskBadge (icon + word) carry the meaning, never colour alone.
 */
import RiskBadge from '../badges/RiskBadge'

const FILL = { LOW: '#15803d', MEDIUM: '#a16207', HIGH: '#c2410c', CRITICAL: '#b91c1c' }
const RADIUS = 80
const LENGTH = Math.PI * RADIUS

export default function RiskScoreGauge({ score, level }) {
  const analysed = score !== null && score !== undefined
  const value = analysed ? Math.max(0, Math.min(100, score)) : 0
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 112" className="w-48" role="img"
        aria-label={analysed ? `Risk score ${value} out of 100, ${level} risk` : 'Not analysed yet'}>
        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#e2e8f0" strokeWidth="14" strokeLinecap="round" />
        {analysed && value > 0 && (
          <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke={FILL[level] || '#64748b'} strokeWidth="14"
            strokeLinecap="round" strokeDasharray={`${(value / 100) * LENGTH} ${LENGTH}`} />
        )}
        <text x="100" y="92" textAnchor="middle" className="fill-slate-900" style={{ fontSize: 34, fontWeight: 600 }}>
          {analysed ? value : '–'}
        </text>
        <text x="100" y="108" textAnchor="middle" className="fill-slate-400" style={{ fontSize: 11 }}>out of 100</text>
      </svg>
      <div className="mt-1"><RiskBadge level={level} /></div>
    </div>
  )
}
