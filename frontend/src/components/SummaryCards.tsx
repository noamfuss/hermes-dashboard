import type { Summary } from '../api'
import { Database, Coins, FileText, Activity, MessageSquare } from 'lucide-react'

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function usd(n: number): string {
  if (n < 0.01) return '$' + n.toFixed(4)
  if (n < 1) return '$' + n.toFixed(3)
  return '$' + n.toFixed(2)
}

export function SummaryCards({ summary, loading }: { summary: Summary; loading: boolean }) {
  const cards = [
    { icon: Activity, label: 'Total Sessions', value: fmt(summary.total_sessions), color: 'text-blue-400', bg: 'bg-blue-500/10' },
    { icon: Database, label: 'Total Tokens', value: fmt(summary.total_tokens), color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
    { icon: MessageSquare, label: 'Total Messages', value: fmt(summary.total_messages), color: 'text-sky-400', bg: 'bg-sky-500/10' },
    { icon: FileText, label: 'Input · Output · Cache', value: `${fmt(summary.total_input_tokens)} · ${fmt(summary.total_output_tokens)} · ${fmt(summary.total_cache_read_tokens)}`, color: 'text-violet-400', bg: 'bg-violet-500/10' },
    { icon: Coins, label: 'Estimated Cost', value: usd(summary.total_estimated_cost), color: 'text-amber-400', bg: 'bg-amber-500/10' },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      {cards.map((card) => (
        <div key={card.label} className={`rounded-xl border border-zinc-800 ${card.bg} p-4 transition-opacity ${loading ? 'opacity-50' : ''}`}>
          <div className="flex items-center gap-2 mb-2">
            <card.icon className={`w-4 h-4 ${card.color}`} />
            <span className="text-xs text-zinc-500">{card.label}</span>
          </div>
          <div className={`text-2xl font-semibold ${card.color}`}>{card.value}</div>
        </div>
      ))}
    </div>
  )
}
