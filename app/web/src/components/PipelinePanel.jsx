import { useEffect, useState } from 'react'
import {
  createJD,
  getReminders,
  listApplications,
  registerCustomStatus,
  searchJobs,
  transitionApplication
} from '../api.js'
import { Btn, Chip, EmptyState, Panel, inputCls, labelCls } from './ui.jsx'

const CORE_STATUSES = ['applied', 'screening', 'interview', 'offer', 'accepted', 'rejected']

const statusTone = {
  applied: 'blue',
  screening: 'indigo',
  interview: 'amber',
  offer: 'green',
  accepted: 'green',
  rejected: 'rose'
}

function CustomStatusForm({ appId, currentStatus, customStatuses, onDone }) {
  const [status, setStatus] = useState('')
  const [from, setFrom] = useState(currentStatus || 'applied')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const fromOptions = [...CORE_STATUSES, ...Object.keys(customStatuses || {})]
    .filter((v, i, arr) => arr.indexOf(v) === i)

  const handleSubmit = async () => {
    if (!status.trim()) return
    setBusy(true)
    setError('')
    try {
      await registerCustomStatus(
        appId,
        status.trim(),
        from,
        next.split(',').map((s) => s.trim()).filter(Boolean)
      )
      setStatus('')
      setNext('')
      onDone()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-xl bg-slate-50/70 p-3">
      <div className="mb-2 text-xs font-medium text-slate-500">
        自定义状态：为特殊流程（如 offer_pending）注册一条可跳转路径
      </div>
      <div className="grid gap-2 sm:grid-cols-[1fr_auto_1fr_auto] sm:items-center">
        <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="新状态名，如 offer_pending" className={inputCls} />
        <select value={from} onChange={(e) => setFrom(e.target.value)} className={inputCls}>
          {fromOptions.map((o) => (
            <option key={o} value={o}>{o}{o === currentStatus ? '（当前）' : ''}</option>
          ))}
        </select>
        <input value={next} onChange={(e) => setNext(e.target.value)} placeholder="下一步（逗号分隔）" className={inputCls} />
        <Btn variant="dark" onClick={handleSubmit} disabled={busy || !status.trim()}>注册</Btn>
      </div>
      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
    </div>
  )
}

function JobFinder() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [busy, setBusy] = useState(false)
  const [busyUrl, setBusyUrl] = useState('')
  const [message, setMessage] = useState('')

  const handleSearch = async () => {
    if (!query.trim()) return
    setBusy(true)
    setMessage('')
    try {
      const data = await searchJobs(query, 6)
      setResults(data.results)
      if (data.results.length === 0) setMessage('没有搜到结果，换个关键词试试')
    } catch (e) {
      setMessage(`搜索失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleImport = async (url) => {
    setBusyUrl(url)
    try {
      const data = await createJD({ source: 'url', url })
      setMessage(`已收录：${data.company || '岗位'} ${data.title || ''}（可在「岗位 JD」页查看）`)
    } catch (e) {
      setMessage(`收录失败：${e.message}`)
    } finally {
      setBusyUrl('')
    }
  }

  return (
    <Panel
      title="发现可投递岗位"
      desc="联网搜索招聘信息，找到后可一键收录为 JD（免 Key 走 DuckDuckGo）"
      actions={
        <Btn onClick={handleSearch} disabled={busy || !query.trim()}>
          {busy ? '搜索中…' : '搜索'}
        </Btn>
      }
    >
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        placeholder="例如：Python 实习 北京"
        className={inputCls}
      />
      <div className="mt-3 space-y-2">
        {results.map((r) => (
          <div key={r.url} className="rounded-xl border border-slate-200 p-3">
            <a href={r.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-indigo-700 hover:underline">
              {r.title}
            </a>
            <p className="mt-1 line-clamp-2 text-xs text-slate-500">{r.content || r.url}</p>
            <div className="mt-2">
              <Btn size="sm" onClick={() => handleImport(r.url)} disabled={busyUrl === r.url}>
                {busyUrl === r.url ? '收录中…' : '收录为 JD'}
              </Btn>
            </div>
          </div>
        ))}
      </div>
      {message && <p className="mt-3 text-xs text-slate-500">{message}</p>}
    </Panel>
  )
}

export default function PipelinePanel() {
  const [applications, setApplications] = useState([])
  const [reminderIds, setReminderIds] = useState([])
  const [message, setMessage] = useState('')
  const [busyAppId, setBusyAppId] = useState('')
  const [openCustom, setOpenCustom] = useState({})

  const refresh = async () => {
    const [data, r] = await Promise.all([listApplications(), getReminders()])
    setApplications(data.applications)
    setReminderIds(r.reminders.map((x) => x.application_id))
  }

  useEffect(() => {
    refresh().catch((e) => setMessage(`加载失败：${e.message}`))
  }, [])

  const handleTransition = async (appId, target) => {
    setBusyAppId(appId)
    try {
      await transitionApplication(appId, target)
      await refresh()
    } catch (e) {
      setMessage(`状态变更失败：${e.message}`)
    } finally {
      setBusyAppId('')
    }
  }

  return (
    <div className="space-y-4">
      <JobFinder />

      {message && <p className="text-sm text-rose-600">{message}</p>}
      {applications.length === 0 && (
        <EmptyState
          title="还没有投递记录"
          desc="在「匹配与自荐信」页生成匹配后，点击结果卡片上的「记录投递」"
        />
      )}
      {applications.map((a) => {
        const reminded = reminderIds.includes(a.application_id)
        const expanded = !!openCustom[a.application_id]
        return (
          <Panel
            key={a.application_id}
            className={reminded ? 'ring-1 ring-amber-300' : ''}
            title={a.jd_name || a.match_id}
            desc="投递记录"
            actions={
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={statusTone[a.current_status] || 'slate'}>{a.current_status}</Chip>
                {reminded && <Chip tone="amber">待跟进</Chip>}
              </div>
            }
          >
            <div className="mb-3 text-xs tabular-nums text-slate-500">等待 {a.waiting_days} 天</div>
            {a.suggestion && (
              <div className="mb-3 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 8v4M12 16h.01" />
                </svg>
                {a.suggestion}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {a.allowed_next.map((t) => (
                <Btn
                  key={t}
                  variant="ghost"
                  size="sm"
                  onClick={() => handleTransition(a.application_id, t)}
                  disabled={busyAppId === a.application_id}
                >
                  {busyAppId === a.application_id ? '转换中…' : `转为 ${t}`}
                </Btn>
              ))}
            </div>
            {a.notes && <p className="mt-3 text-xs text-slate-500">备注：{a.notes}</p>}
            <div className="mt-3 border-t border-slate-100 pt-3">
              <button
                onClick={() => setOpenCustom((prev) => ({ ...prev, [a.application_id]: !prev[a.application_id] }))}
                className="text-xs font-medium text-slate-400 underline-offset-2 transition-colors hover:text-indigo-600 hover:underline"
              >
                {expanded ? '收起' : '自定义状态'}（高级）
              </button>
              {expanded && (
                <div className="mt-2">
                  <CustomStatusForm
                    appId={a.application_id}
                    currentStatus={a.current_status}
                    customStatuses={a.custom_statuses}
                    onDone={refresh}
                  />
                </div>
              )}
            </div>
          </Panel>
        )
      })}
    </div>
  )
}
