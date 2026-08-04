import { useState } from 'react'
import AgentPanel from './components/AgentPanel.jsx'
import InterviewPanel from './components/InterviewPanel.jsx'
import JDPanel from './components/JDPanel.jsx'
import MatchPanel from './components/MatchPanel.jsx'
import PipelinePanel from './components/PipelinePanel.jsx'
import ResumePanel from './components/ResumePanel.jsx'

const TABS = [
  { key: 'resume', label: '简历', component: ResumePanel },
  { key: 'jd', label: '岗位 JD', component: JDPanel },
  { key: 'match', label: '匹配与自荐信', component: MatchPanel },
  { key: 'pipeline', label: '投递看板', component: PipelinePanel },
  { key: 'interview', label: '面试陪练', component: InterviewPanel },
  { key: 'agent', label: '助手', component: AgentPanel }
]

export default function App() {
  const [active, setActive] = useState('resume')
  const [resumeId, setResumeId] = useState(localStorage.getItem('jc_resume_id') || '')
  const [jdIds, setJdIds] = useState(JSON.parse(localStorage.getItem('jc_jd_ids') || '[]'))

  const handleResumeReady = (id) => {
    setResumeId(id)
    localStorage.setItem('jc_resume_id', id)
  }

  const handleJDAdded = (id) => {
    const next = [...jdIds, id]
    setJdIds(next)
    localStorage.setItem('jc_jd_ids', JSON.stringify(next))
  }

  const ActiveComponent = TABS.find((t) => t.key === active).component

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="bg-white border-b px-6 py-4">
        <h1 className="text-xl font-bold">Job Copilot</h1>
        <p className="text-sm text-slate-500">求职全生命周期 Agent · Phase 1 核心闭环</p>
      </header>
      <nav className="flex gap-2 px-6 py-3 bg-white border-b">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActive(t.key)}
            className={`px-4 py-2 rounded-lg text-sm ${
              active === t.key ? 'bg-blue-600 text-white' : 'bg-slate-100 hover:bg-slate-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>
      <main className="p-6 max-w-4xl">
        <ActiveComponent
          resumeId={resumeId}
          jdIds={jdIds}
          onResumeReady={handleResumeReady}
          onJDAdded={handleJDAdded}
        />
      </main>
    </div>
  )
}
