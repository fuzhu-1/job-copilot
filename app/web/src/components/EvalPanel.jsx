import { useEffect, useState } from 'react'
import { listEvalRuns, runEval, syncGoldenSet } from '../api.js'
import { Btn, Chip, EmptyState, Panel } from './ui.jsx'

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
    refresh().catch((e) => setMessage(`加载自检记录失败：${e.message}`))
  }, [])

  const handleRun = async () => {
    setBusy(true)
    setMessage('')
    try {
      const data = await runEval()
      await refresh()
      setMessage(`自检完成：通过 ${data.metrics.passed_cases}/${data.metrics.total_cases}`)
    } catch (e) {
      setMessage(`自检失败：${e.message}`)
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
      <Panel
        title="系统自检"
        desc="对匹配/自荐信/陪练等系统功能跑回归基线，任何改动合入前先自检"
        actions={
          <>
            <Btn variant="dark" onClick={handleSync} disabled={busy}>
              同步 golden set
            </Btn>
            <Btn onClick={handleRun} disabled={busy}>
              {busy ? '自检中…' : '运行自检'}
            </Btn>
          </>
        }
      >
        {message && <p className="text-sm text-slate-600">{message}</p>}
      </Panel>

      {latest ? (
          <Panel
          title="最近一次自检"
          desc={latest.created_at.slice(0, 19).replace('T', ' ')}
          actions={<Chip tone={latest.metrics.pass_rate >= 1 ? 'green' : 'amber'}>通过率 {latest.metrics.pass_rate * 100}%</Chip>}
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-indigo-50 p-4 text-center">
              <div className="text-3xl font-bold tabular-nums text-indigo-700">
                {latest.metrics.pass_rate * 100}%
              </div>
              <div className="mt-1 text-xs text-indigo-500">通过率</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4 text-center">
              <div className="text-3xl font-bold tabular-nums text-slate-800">
                {latest.metrics.passed_cases}/{latest.metrics.total_cases}
              </div>
              <div className="mt-1 text-xs text-slate-500">通过 / 总数</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4 text-center">
              <div className="text-3xl font-bold tabular-nums text-slate-800">
                {Object.keys(latest.metrics.by_type).length}
              </div>
              <div className="mt-1 text-xs text-slate-500">任务类型</div>
            </div>
          </div>
          {Object.entries(latest.metrics.by_type).map(([type, v]) => (
            <div key={type} className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
              <span className="font-medium text-slate-700">{type}</span>
              <span className="tabular-nums text-slate-500">
                {v.passed}/{v.total} · 平均分 {v.avg_score}
              </span>
            </div>
          ))}
        </Panel>
      ) : (
        <EmptyState title="暂无自检记录" desc="点击「运行自检」生成第一份报告" />
      )}

      <Panel title={`历史自检（${runs.length}）`}>
        {runs.length === 0 ? (
          <p className="text-xs text-slate-400">暂无记录</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {runs.map((r, i) => (
              <div key={r.run_id} className="flex items-center justify-between py-2.5 text-xs text-slate-600">
                <span className="font-medium" title={r.run_id}>评测记录 #{i + 1}</span>
                <span className="tabular-nums">
                  {r.created_at.slice(0, 19).replace('T', ' ')} · 通过率 {(r.metrics.pass_rate * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}
