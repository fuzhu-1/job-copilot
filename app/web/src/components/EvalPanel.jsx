import { useEffect, useState } from 'react'
import { listEvalRuns, runEval, syncGoldenSet } from '../api.js'

export default function EvalPanel() {
  const [runs, setRuns] = useState([])
  const [latest, setLatest] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const refresh = async () => {
    const data = await listEvalRuns()
    setRuns(data.runs)
    if (data.runs.length > 0) setLatest(data.runs[0])
  }

  useEffect(() => {
    refresh().catch((e) => setMessage(`加载评测记录失败：${e.message}`))
  }, [])

  const handleRun = async () => {
    setBusy(true)
    setMessage('')
    try {
      const data = await runEval()
      await refresh()
      setMessage(`评测完成：通过 ${data.metrics.passed_cases}/${data.metrics.total_cases}`)
    } catch (e) {
      setMessage(`评测失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleSync = async () => {
    setBusy(true)
    try {
      const data = await syncGoldenSet()
      setMessage(`golden set 同步完成：新增 ${data.added}，更新 ${data.updated}`)
    } catch (e) {
      setMessage(`同步失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-white border rounded-lg p-4 space-y-3">
        <div className="flex gap-2">
          <button onClick={handleRun} disabled={busy} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
            {busy ? '评测中…' : '运行评测'}
          </button>
          <button onClick={handleSync} disabled={busy} className="px-4 py-2 bg-slate-700 text-white rounded-lg disabled:opacity-50">
            同步 golden set
          </button>
        </div>
        {message && <p className="text-sm text-slate-600">{message}</p>}
      </div>

      {latest && (
        <div className="bg-white border rounded-lg p-4 space-y-3">
          <h2 className="text-sm font-semibold">最近一次评测 · {latest.created_at.slice(0, 19).replace('T', ' ')}</h2>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-slate-50 rounded p-3">
              <div className="text-2xl font-bold text-blue-600">{latest.metrics.pass_rate * 100}%</div>
              <div className="text-xs text-slate-500">通过率</div>
            </div>
            <div className="bg-slate-50 rounded p-3">
              <div className="text-2xl font-bold">{latest.metrics.passed_cases}/{latest.metrics.total_cases}</div>
              <div className="text-xs text-slate-500">通过/总数</div>
            </div>
            <div className="bg-slate-50 rounded p-3">
              <div className="text-2xl font-bold">{Object.keys(latest.metrics.by_type).length}</div>
              <div className="text-xs text-slate-500">任务类型</div>
            </div>
          </div>
          {Object.entries(latest.metrics.by_type).map(([type, v]) => (
            <div key={type} className="flex justify-between text-sm">
              <span>{type}：{v.passed}/{v.total}</span>
              <span className="text-slate-500">平均分 {v.avg_score}</span>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white border rounded-lg p-4 space-y-2">
        <h2 className="text-sm font-semibold">历史评测（{runs.length}）</h2>
        {runs.length === 0 && <p className="text-xs text-slate-500">暂无评测记录</p>}
        {runs.map((r) => (
          <div key={r.run_id} className="flex justify-between text-xs text-slate-600 border-t pt-2">
            <span className="font-mono">{r.run_id}</span>
            <span>{r.created_at.slice(0, 19).replace('T', ' ')} · 通过率 {(r.metrics.pass_rate * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}
