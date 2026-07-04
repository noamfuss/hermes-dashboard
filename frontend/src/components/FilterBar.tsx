import type { Filters } from '../api'

type Props = {
  models: string[]
  filters: Filters
  onChange: (f: Filters) => void
}

export function FilterBar({ models, filters, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Model filter */}
      <select
        value={filters.model ?? ''}
        onChange={(e) => onChange({ ...filters, model: e.target.value || undefined })}
        className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-emerald-500/50"
      >
        <option value="">All models</option>
        {models.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>

      {/* Date range */}
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <input
          type="date"
          value={filters.startDate ?? ''}
          onChange={(e) => onChange({ ...filters, startDate: e.target.value || undefined, days: 0 })}
          className="bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-zinc-300 focus:outline-none focus:border-emerald-500/50 [color-scheme:dark]"
        />
        <span>→</span>
        <input
          type="date"
          value={filters.endDate ?? ''}
          onChange={(e) => onChange({ ...filters, endDate: e.target.value || undefined, days: 0 })}
          className="bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-zinc-300 focus:outline-none focus:border-emerald-500/50 [color-scheme:dark]"
        />
      </div>
    </div>
  )
}
