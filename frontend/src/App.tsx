import { Activity, BookOpen, Server } from 'lucide-react'
import type { ReactNode } from 'react'

type StatusTone = 'neutral' | 'warning' | 'positive'

interface StatusItem {
  label: string
  value: string
  tone: StatusTone
  icon: ReactNode
}

const STATUS_ITEMS: StatusItem[] = [
  {
    label: 'System status',
    value: 'Initializing',
    tone: 'neutral',
    icon: <Activity className="h-4 w-4" aria-hidden="true" />,
  },
  {
    label: 'Backend',
    value: 'Not yet connected',
    tone: 'warning',
    icon: <Server className="h-4 w-4" aria-hidden="true" />,
  },
  {
    label: 'Frontend',
    value: 'Operational',
    tone: 'positive',
    icon: <BookOpen className="h-4 w-4" aria-hidden="true" />,
  },
]

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: 'text-slate-300',
  warning: 'text-amber-400',
  positive: 'text-emerald-400',
}

export default function App() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 py-12 text-slate-100">
      <section
        className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900/60 p-10 shadow-2xl"
        aria-labelledby="papermind-title"
      >
        <header className="flex items-center gap-4 border-b border-slate-800 pb-6">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400">
            <Activity className="h-6 w-6" aria-hidden="true" />
          </span>
          <div>
            <h1 id="papermind-title" className="text-2xl font-semibold tracking-tight">
              PaperMind AI
            </h1>
            <p className="text-sm text-slate-400">Research Intelligence Platform</p>
          </div>
        </header>

        <dl className="mt-8 space-y-3">
          {STATUS_ITEMS.map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between gap-4 rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3"
            >
              <dt className="flex items-center gap-2 text-sm text-slate-400">
                {item.icon}
                {item.label}
              </dt>
              <dd className={`text-sm font-medium ${TONE_CLASSES[item.tone]}`}>{item.value}</dd>
            </div>
          ))}
        </dl>

        <p className="mt-8 text-xs text-slate-500">
          Milestone 0 scaffold - status screen only. The research assistant interface arrives in
          Milestone 5.
        </p>
      </section>
    </main>
  )
}
