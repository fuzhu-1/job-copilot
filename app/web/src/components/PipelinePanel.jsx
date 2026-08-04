import { useEffect, useState } from 'react'
import {
  getReminders,
  listApplications,
  registerCustomStatus,
  transitionApplication
} from '../api.js'

function CustomStatusForm({ appId, onDone }) {
  const [status, setStatus] = useState('')
  const [from, setFrom] = useState('applied')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

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
    <div className="flex gap-2 flex-wrap items-center text-xs">
      <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="新状态名，如 offer_pending" className="border rounded px-2 py-1" />
      <select value={from} onChange={(e) => setFrom(e.target.value)} className="border rounded px-2 py-1">
        <option value="applied">applied</option>
        <option value="screening">screening</option>
        <option value="interview">interview</option>
        <option value="offer">offer</option>
      </select>
      <input value={next} onChange={(e) => setNext(e.target.value)} placeholder="下一步（逗号分隔）" className="border rounded px-2 py-1" />
      <button onClick={handleSubmit} disabled={busy} className="px-3 py-1 bg-slate-700 text-white rounded disabled:opacity-50">
        注册
      </button>
      {error && <span className="text-red-600">{error}</span>}
    </div>
  )
}

export default function PipelinePanel() {
  const [applications, setApplications] = useState([])
  const [reminderIds, setReminderIds] = useState([])
  const [message, setMessage] = useState('')

  const refresh = async () => {
    const [data, r] = await Promise.all([listApplications(), getReminders()])
    setApplications(data.applications)
    setReminderIds(r.reminders.map((x) => x.application_id))
  }

  useEffect(() => {
    refresh().catch((e) => setMessage(`加载失败：${e.message}`))
  }, [])

  const handleTransition = async (appId, target) => {
    try {
      await transitionApplication(appId, target)
      await refresh()
    } catch (e) {
      setMessage(`状态变更失败：${e.message}`)
    }
  }

  return (
    <div className="space-y-4">
      {message && <p className="text-sm text-red-600">{message}</p>}
      {applications.length === 0 && (
        <p className="text-sm text-slate-500">还没有投递记录，去「匹配与自荐信」页生成匹配后点击「记录投递」。</p>
      )}
      {applications.map((a) => (
        <div key={a.application_id} className={`bg-white border rounded-lg p-4 space-y-2 ${reminderIds.includes(a.application_id) ? 'border-amber-400' : ''}`}>
          <div className="flex justify-between items-center">
            <div>
              <span className="font-mono text-xs text-slate-500">{a.match_id}</span>
              <span className="ml-2 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{a.current_status}</span>
              {reminderIds.includes(a.application_id) && (
                <span className="ml-2 px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs">提醒</span>
              )}
            </div>
            <span className="text-xs text-slate-500">等待 {a.waiting_days} 天</span>
          </div>
          {a.suggestion && <p className="text-sm text-amber-700">{a.suggestion}</p>}
          <div className="flex gap-2 flex-wrap">
            {a.allowed_next.map((t) => (
              <button key={t} onClick={() => handleTransition(a.application_id, t)} className="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded text-sm">
                转为 {t}
              </button>
            ))}
          </div>
          {a.notes && <p className="text-xs text-slate-500">备注：{a.notes}</p>}
          <CustomStatusForm appId={a.application_id} onDone={refresh} />
        </div>
      ))}
    </div>
  )
}
