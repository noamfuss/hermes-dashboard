import type { SessionRow } from '../api'

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return String(n)
}

function usd(n: number | null): string {
  if (n === null || n === 0) return '—'
  if (n < 0.01) return '$' + n.toFixed(4)
  return '$' + n.toFixed(2)
}

type Props = {
  data: SessionRow[]
  total: number
  loading: boolean
  onPage: (offset: number) => void
}

export function SessionsTable({ data, total, loading, onPage }: Props) {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-xs text-zinc-500 uppercase">
              <th className="text-left px-4 py-2 font-medium">Date</th>
              <th className="text-left px-4 py-2 font-medium">Model</th>
              <th className="text-left px-4 py-2 font-medium max-w-[200px]">Title</th>
              <th className="text-right px-4 py-2 font-medium">Input</th>
              <th className="text-right px-4 py-2 font-medium">Output</th>
              <th className="text-right px-4 py-2 font-medium">Cache</th>
              <th className="text-right px-4 py-2 font-medium">Total</th>
              <th className="text-right px-4 py-2 font-medium">Cost</th>
              <th className="text-center px-4 py-2 font-medium">Source</th>
            </tr>
          </thead>
          <tbody className={`transition-opacity ${loading ? 'opacity-50' : ''}`}>
            {data.map((row) => {
              const tokens = row.input_tokens + row.output_tokens + (row.cache_read_tokens || 0) + (row.cache_write_tokens || 0)
              const dt = new Date(row.started_at * 1000)
              return (
                <tr key={row.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                  <td className="px-4 py-2.5 text-zinc-400 whitespace-nowrap">
                    {dt.toLocaleDateString()} {dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-200 font-mono text-xs max-w-[200px] truncate" title={row.model}>
                    {row.model || '—'}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-400 max-w-[200px] truncate" title={row.title ?? ''}>
                    {row.title || '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right text-zinc-300 font-mono text-xs">{fmt(row.input_tokens)}</td>
                  <td className="px-4 py-2.5 text-right text-zinc-300 font-mono text-xs">{fmt(row.output_tokens)}</td>
                  <td className="px-4 py-2.5 text-right text-emerald-400 font-mono text-xs font-medium">{fmt(tokens)}</td>
                  <td className="px-4 py-2.5 text-right text-amber-400 font-mono text-xs">
                    {usd(row.estimated_cost_usd)}
                    {row.cost_status === 'actual' && (
                      <span className="text-zinc-600 ml-1 text-[10px]">✓</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-center text-zinc-500 text-[10px] uppercase">
                    {row.source || '—'}
                  </td>
                </tr>
              )
            })}
            {data.length === 0 && !loading && (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-zinc-500 text-sm">No sessions found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {/* Pagination hint */}
      {total > 50 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-zinc-800 text-xs text-zinc-500">
          <span>{total} sessions total</span>
          <div className="flex gap-2">
            <button
              className="px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 transition-colors disabled:opacity-40"
              onClick={() => onPage(0)}
              disabled={loading}
            >
              First
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
