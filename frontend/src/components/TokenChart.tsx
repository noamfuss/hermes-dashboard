import { useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import type { DailyRow } from '../api'

const PALETTE = [
  '#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444',
  '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1',
  '#14b8a6', '#d946ef', '#0ea5e9', '#eab308', '#a855f7',
]

export type Metric = 'tokens' | 'messages' | 'cost'

type Props = {
  data: DailyRow[]
  loading: boolean
  metric: Metric
}

const METRIC_CONFIG: Record<Metric, { key: keyof DailyRow; label: string }> = {
  tokens: { key: 'total_tokens', label: 'Tokens' },
  messages: { key: 'total_messages', label: 'Messages' },
  cost: { key: 'estimated_cost_usd', label: 'Cost' },
}

function fmtTokens(v: number): string {
  if (typeof v !== 'number' || isNaN(v)) return '0'
  return v >= 1_000_000 ? (v / 1_000_000).toFixed(1) + 'M'
    : v >= 1_000 ? (v / 1_000).toFixed(0) + 'K'
    : String(v)
}

function fmtCost(v: number): string {
  if (typeof v !== 'number' || isNaN(v)) return '$0'
  return v < 0.01 ? '$~0' : '$' + v.toFixed(3)
}

function fmtMessages(v: number): string {
  if (typeof v !== 'number' || isNaN(v)) return '0'
  return String(v)
}

export function TokenChart({ data, loading, metric }: Props) {
  const { chartData, models, fmt } = useMemo(() => {
    const cfg = METRIC_CONFIG[metric]
    const valueKey = cfg.key

    const byDay = new Map<string, Record<string, number>>()
    const modelSet = new Set<string>()

    for (const row of data) {
      modelSet.add(row.model)
      const day = row.day
      if (!byDay.has(day)) byDay.set(day, {})
      byDay.get(day)![row.model] = (byDay.get(day)![row.model] ?? 0) + (row[valueKey] as number)
    }

    const modelsArr = Array.from(modelSet).sort()
    const chart = Array.from(byDay.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([day, modelData]) => {
        const point: Record<string, any> = { day }
        let total = 0
        for (const m of modelsArr) {
          point[m] = modelData[m] ?? 0
          total += modelData[m] ?? 0
        }
        point._total = total
        return point
      })

    let fmt: (v: number) => string
    if (metric === 'cost') {
      fmt = fmtCost
    } else if (metric === 'messages') {
      fmt = fmtMessages
    } else {
      fmt = fmtTokens
    }

    return { chartData: chart, models: modelsArr, fmt }
  }, [data, metric])

  if (loading && data.length === 0) {
    return <div className="flex items-center justify-center h-64 text-zinc-500 text-sm">Loading...</div>
  }

  if (chartData.length === 0) {
    return <div className="flex items-center justify-center h-64 text-zinc-500 text-sm">No data for this period</div>
  }

  return (
    <div className={`transition-opacity ${loading ? 'opacity-50' : ''}`}>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="day"
            tick={{ fill: '#a1a1aa', fontSize: 12 }}
            axisLine={{ stroke: '#27272a' }}
            tickLine={false}
            tickFormatter={(d: string) => {
              const [, m, day] = d.split('-')
              return `${m}/${day}`
            }}
          />
          <YAxis
            tick={{ fill: '#a1a1aa', fontSize: 12 }}
            axisLine={{ stroke: '#27272a' }}
            tickLine={false}
            tickFormatter={(v: number) => fmt(v)}
            width={60}
          />
          <Tooltip
            contentStyle={{
              background: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            labelStyle={{ color: '#d4d4d8', fontWeight: 600, marginBottom: 4 }}
            formatter={(value: number, name: string) => [fmt(value), name]}
            labelFormatter={(d: string) => {
              const [y, m, day] = d.split('-')
              return `${y}-${m}-${day}`
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px', color: '#a1a1aa' }}
          />
          {models.map((model, i) => (
            <Line
              key={model}
              type="monotone"
              dataKey={model}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
