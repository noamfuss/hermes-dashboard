import { useEffect, useState } from 'react'
import { fetchModels, fetchSummary, fetchDaily, fetchSessions, type Filters, type Summary, type DailyRow, type SessionsResponse } from './api'
import { SummaryCards } from './components/SummaryCards'
import { TokenChart, type Metric, type ViewMode } from './components/TokenChart'
import { SessionsTable } from './components/SessionsTable'
import { FilterBar } from './components/FilterBar'
import { RefreshCw, AlertCircle, MessageSquare, DollarSign, BarChart3, Layers } from 'lucide-react'

const PRESETS = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
  { label: 'All', days: 0 },
]

const METRIC_TABS: { key: Metric; label: string; icon: typeof BarChart3 }[] = [
  { key: 'messages', label: 'Messages', icon: MessageSquare },
  { key: 'cost', label: 'Cost', icon: DollarSign },
]

const TOP_VIEWS: { key: ViewMode; label: string }[] = [
  { key: 'per-model', label: 'By Model' },
  { key: 'composition', label: 'Composition' },
]

export default function App() {
  const [filters, setFilters] = useState<Filters>({ days: 30 })
  const [models, setModels] = useState<string[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [daily, setDaily] = useState<DailyRow[]>([])
  const [sessionsData, setSessionsData] = useState<SessionsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [bottomMetric, setBottomMetric] = useState<Metric>('messages')
  const [topView, setTopView] = useState<ViewMode>('per-model')

  // Fetch models once
  useEffect(() => {
    fetchModels().then(setModels).catch(() => {})
  }, [])

  // Fetch data on filter change
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setRefreshing(true)
    setError(null)

    Promise.all([
      fetchSummary(filters),
      fetchDaily(filters),
      fetchSessions(filters),
    ])
      .then(([s, d, sess]) => {
        if (cancelled) return
        setSummary(s)
        setDaily(d)
        setSessionsData(sess)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to load data')
      })
      .finally(() => {
        if (!cancelled) { setLoading(false); setRefreshing(false) }
      })

    return () => { cancelled = true }
  }, [filters])

  // Auto-refresh every 30s
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => {
      setRefreshing(true)
      Promise.all([
        fetchSummary(filters).then(setSummary),
        fetchDaily(filters).then(setDaily),
      ])
        .catch(() => {})
        .finally(() => setRefreshing(false))
    }, 30000)
    return () => clearInterval(interval)
  }, [filters, autoRefresh])

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
              <span className="text-emerald-400 font-bold text-sm">H</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold">Hermes Token Dashboard</h1>
              <p className="text-xs text-zinc-500">Usage monitor</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Preset buttons */}
            <div className="flex rounded-lg border border-zinc-800 overflow-hidden">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => setFilters({ ...filters, days: p.days, startDate: undefined, endDate: undefined })}
                  className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                    filters.days === p.days && !filters.startDate
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'text-zinc-400 hover:bg-zinc-800'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`p-2 rounded-lg transition-colors ${
                autoRefresh ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-500 hover:bg-zinc-800'
              }`}
              title="Auto-refresh (30s)"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Filter bar */}
        <FilterBar
          models={models}
          filters={filters}
          onChange={setFilters}
        />

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Summary cards */}
        {summary && <SummaryCards summary={summary} loading={loading} />}

        {/* Token chart — switchable between per-model and composition */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-zinc-300">
              {topView === 'composition' ? 'Daily Token Composition' : 'Daily Token Usage by Model'}
            </h2>
            <div className="flex rounded-lg border border-zinc-800 overflow-hidden">
              {TOP_VIEWS.map((v) => (
                <button
                  key={v.key}
                  onClick={() => setTopView(v.key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
                    topView === v.key
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'text-zinc-400 hover:bg-zinc-800'
                  }`}
                >
                  {v.key === 'composition' && <Layers className="w-3.5 h-3.5" />}
                  {v.label}
                </button>
              ))}
            </div>
          </div>
          <TokenChart data={daily} loading={loading} metric="tokens" view={topView} />
        </div>

        {/* Switchable chart (Messages / Cost) */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-zinc-300">Daily {bottomMetric === 'messages' ? 'Messages' : 'Cost'} by Model</h2>
            <div className="flex rounded-lg border border-zinc-800 overflow-hidden">
              {METRIC_TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setBottomMetric(tab.key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
                    bottomMetric === tab.key
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'text-zinc-400 hover:bg-zinc-800'
                  }`}
                >
                  <tab.icon className="w-3.5 h-3.5" />
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
          <TokenChart data={daily} loading={loading} metric={bottomMetric} />
        </div>

        {/* Sessions table */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 overflow-hidden">
          <div className="p-4 border-b border-zinc-800">
            <h2 className="text-sm font-medium text-zinc-300">Recent Sessions</h2>
          </div>
          <SessionsTable
            data={sessionsData?.sessions ?? []}
            total={sessionsData?.total ?? 0}
            loading={loading}
            onPage={(offset) => {
              fetchSessions(filters, 50, offset).then(setSessionsData).catch(() => {})
            }}
          />
        </div>
      </main>
    </div>
  )
}
