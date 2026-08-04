import { useState } from 'react'
import AgentPanel from './components/AgentPanel.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import EvalPanel from './components/EvalPanel.jsx'
import InterviewPanel from './components/InterviewPanel.jsx'
import JDPanel from './components/JDPanel.jsx'
import MatchPanel from './components/MatchPanel.jsx'
import PipelinePanel from './components/PipelinePanel.jsx'
import ResumePanel from './components/ResumePanel.jsx'

const iconProps = {
  width: 20,
  height: 20,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round'
}

const icons = {
  resume: (
    <svg {...iconProps}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </svg>
  ),
  jd: (
    <svg {...iconProps}>
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" />
    </svg>
  ),
  match: (
    <svg {...iconProps}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 3" />
    </svg>
  ),
  pipeline: (
    <svg {...iconProps}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  ),
  interview: (
    <svg {...iconProps}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <path d="M9 10h6M9 14h4" />
    </svg>
  ),
  eval: (
    <svg {...iconProps}>
      <path d="M3 3v18h18" />
      <path d="M7 15l4-5 3 3 5-7" />
    </svg>
  ),
  agent: (
    <svg {...iconProps}>
      <path d="M12 3a6 6 0 0 0-6 6v2a4 4 0 0 0-2 3.5V16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1.5A4 4 0 0 0 18 11V9a6 6 0 0 0-6-6z" />
      <path d="M9 18v2a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-2" />
    </svg>
  )
}

const NAV = [
  { key: 'resume', label: '简历', desc: '上传 PDF 并确认结构化结果', icon: icons.resume },
  { key: 'jd', label: '岗位 JD', desc: '录入 / 批量导入 / 企业研究与洞察', icon: icons.jd },
  { key: 'match', label: '匹配与自荐信', desc: '四维打分、差距分析与自荐信', icon: icons.match },
  { key: 'pipeline', label: '投递看板', desc: '状态流转、跟进建议与提醒', icon: icons.pipeline },
  { key: 'interview', label: '面试陪练', desc: '按 JD + 简历的多轮模拟面试', icon: icons.interview },
  { key: 'eval', label: '系统自检', desc: 'golden set 回归：改代码后验证系统没变坏', icon: icons.eval },
  { key: 'agent', label: '助手', desc: 'Supervisor 意图识别与路由', icon: icons.agent }
]

export default function App() {
  const [active, setActive] = useState('resume')
  const [resumeId, setResumeId] = useState(localStorage.getItem('jc_resume_id') || '')
  const [jdIds, setJdIds] = useState(JSON.parse(localStorage.getItem('jc_jd_ids') || '[]'))
  const [resume, setResume] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('jc_resume_structured') || 'null')
    } catch {
      return null
    }
  })

  const handleResumeReady = (id, structured) => {
    setResumeId(id)
    localStorage.setItem('jc_resume_id', id)
    if (structured) {
      setResume(structured)
      localStorage.setItem('jc_resume_structured', JSON.stringify(structured))
    }
  }

  const handleJDAdded = (id) => {
    const next = [...jdIds, id]
    setJdIds(next)
    localStorage.setItem('jc_jd_ids', JSON.stringify(next))
  }

  const current = NAV.find((n) => n.key === active)
  const ActiveComponent = {
    resume: ResumePanel,
    jd: JDPanel,
    match: MatchPanel,
    pipeline: PipelinePanel,
    interview: InterviewPanel,
    eval: EvalPanel,
    agent: AgentPanel
  }[active]

  return (
    <div className="min-h-screen lg:flex">
      <aside className="flex w-full flex-col border-b border-slate-800 bg-slate-900 text-slate-300 lg:fixed lg:inset-y-0 lg:w-60 lg:border-b-0 lg:border-r">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg shadow-indigo-900/40">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M13 2 4.5 13.5H11L9.5 22 19 9.5h-6.5z" />
            </svg>
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-tight text-white">Job Copilot</div>
            <div className="text-[11px] text-slate-500">求职全生命周期 Agent</div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-1 lg:flex-col lg:overflow-visible lg:px-3 lg:pb-0">
          {NAV.map((item) => {
            const isActive = active === item.key
            return (
              <button
                key={item.key}
                onClick={() => setActive(item.key)}
                className={
                  'group flex shrink-0 items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors duration-150 ' +
                  (isActive
                    ? 'bg-indigo-500/15 text-white'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-200')
                }
              >
                <span
                  className={
                    'transition-colors duration-150 ' +
                    (isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-300')
                  }
                >
                  {item.icon}
                </span>
                <span className="whitespace-nowrap font-medium">{item.label}</span>
                {isActive && (
                  <span className="ml-auto h-1.5 w-1.5 rounded-full bg-indigo-400 lg:hidden" />
                )}
              </button>
            )
          })}
        </nav>
        <div className="hidden border-t border-slate-800 px-5 py-4 lg:block">
          <div className="text-[11px] leading-relaxed text-slate-500">
            一站式求职 Agent，帮你完成简历结构化、岗位匹配、投递管理与面试准备。
          </div>
        </div>
      </aside>

      <div className="min-w-0 flex-1 lg:ml-60">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/85 px-5 py-4 backdrop-blur lg:px-8">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-slate-900">{current.label}</h1>
              <p className="mt-0.5 text-xs text-slate-500">{current.desc}</p>
            </div>
            <div className="hidden items-center gap-2 sm:flex">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                服务运行中
              </span>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-5xl px-5 py-6 lg:px-8 lg:py-8">
          <ErrorBoundary>
            <ActiveComponent
              resumeId={resumeId}
              resume={resume}
              jdIds={jdIds}
              onResumeReady={handleResumeReady}
              onJDAdded={handleJDAdded}
            />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
