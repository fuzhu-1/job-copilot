import { useEffect, useState } from 'react'
import {
  createApplication,
  generateCoverLetter,
  listJDs,
  runMatch
} from '../api.js'
import { Btn, Chip, EmptyState, Panel, inputCls, labelCls, plainText } from './ui.jsx'

const dimLabels = {
  skill_match: '技能匹配',
  experience_match: '经历相关',
  education_match: '教育背景',
  hard_requirements: '硬性条件'
}

export default function MatchPanel({ resumeId, resume, jdIds }) {
  const [availableJds, setAvailableJds] = useState([])
  const [selectedIds, setSelectedIds] = useState(jdIds)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState('')
  const [results, setResults] = useState([])
  const [cover, setCover] = useState(null)
  const [busyId, setBusyId] = useState('')
  const [tone, setTone] = useState('standard')

  useEffect(() => {
    listJDs().then((d) => {
      setAvailableJds(d.jds)
      const valid = new Set(d.jds.map((jd) => jd.jd_id))
      setSelectedIds((prev) => prev.filter((id) => valid.has(id)))
    }).catch(() => {})
  }, [])

  const handleToggleJd = (jdId) => {
    setSelectedIds((prev) =>
      prev.includes(jdId) ? prev.filter((x) => x !== jdId) : [...prev, jdId]
    )
  }

  const handleSelectAll = () => {
    setSelectedIds(selectedIds.length === availableJds.length
      ? []
      : availableJds.map((jd) => jd.jd_id))
  }

  const handleMatch = async () => {
    if (!resumeId || selectedIds.length === 0) {
      setProgress('请先确认简历并选择至少一个 JD')
      return
    }
    setBusy(true)
    setResults([])
    setCover(null)
    setProgress('发起匹配…')
    try {
      const { task_id } = await runMatch(resumeId, selectedIds)
      const es = new EventSource(`/api/matches/${task_id}/stream`)
      let transportErrors = 0
      es.addEventListener('match_progress', (e) => {
        const d = JSON.parse(e.data)
        const jd = availableJds.find((x) => x.jd_id === d.jd_id)
        setProgress(`正在匹配 ${d.index + 1}/${d.total}${jd ? ' · ' + jd.display_name : ''}…`)
      })
      es.addEventListener('match_result', (e) => {
        const d = JSON.parse(e.data)
        setResults((prev) => [...prev, d.result])
      })
      es.addEventListener('completed', () => {
        setProgress('匹配完成')
        setBusy(false)
        es.close()
      })
      es.addEventListener('error', (e) => {
        if (e.data) {
          let msg = '匹配出错，请检查服务端日志'
          try {
            msg = JSON.parse(e.data).message || msg
          } catch {}
          setProgress(`匹配出错：${msg}`)
          setBusy(false)
          es.close()
          return
        }
        // 无数据的 error 是连接层问题：让 EventSource 自动重连，容忍有限次
        transportErrors += 1
        if (transportErrors > 6) {
          setProgress('匹配连接中断，请重新发起匹配')
          setBusy(false)
          es.close()
        }
      })
    } catch (e) {
      setProgress(`发起匹配失败：${e.message}`)
      setBusy(false)
    }
  }

  const handleCover = async (matchId) => {
    setBusyId(matchId)
    try {
      const data = await generateCoverLetter(matchId, tone)
      setCover({ matchId, ...data })
    } catch (e) {
      setCover({ matchId, content: `生成失败：${e.message}`, judge_score: 0, revised: false })
    } finally {
      setBusyId('')
    }
  }

  const handleApply = async (matchId) => {
    setBusyId(matchId)
    try {
      const data = await createApplication(matchId)
      setProgress(`已记录投递 application_id=${data.application_id}`)
    } catch (e) {
      setProgress(`记录投递失败：${e.message}`)
    } finally {
      setBusyId('')
    }
  }

  return (
    <div className="space-y-4">
      <Panel title="发起匹配" desc="选择目标 JD 运行四维打分，SSE 实时推送进度">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-xs font-medium text-slate-500">简历</span>
            {resume ? (
              <>
                <span className="font-medium text-slate-800">{resume.name || '（未命名）'}</span>
                {(resume.skills || []).slice(0, 6).map((s) => <Chip key={s} tone="blue">{s}</Chip>)}
                {(resume.skills || []).length > 6 && (
                  <Chip tone="slate">+{(resume.skills || []).length - 6}</Chip>
                )}
              </>
            ) : (
              <span className="font-mono text-xs text-slate-700">{resumeId || '（未确认）'}</span>
            )}
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-xs font-medium text-slate-500">
                目标 JD（已选 {selectedIds.length} 个）
              </label>
              {availableJds.length > 0 && (
                <button
                  onClick={handleSelectAll}
                  className="text-xs font-medium text-indigo-600 hover:underline"
                >
                  {selectedIds.length === availableJds.length ? '取消全选' : '全选'}
                </button>
              )}
            </div>
            {availableJds.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50/60 px-4 py-6 text-center text-xs text-slate-400">
                还没有可选的 JD，请先到「岗位 JD」页录入
              </div>
            ) : (
              <div className="max-h-60 space-y-1.5 overflow-y-auto rounded-xl border border-slate-200 p-2">
                {availableJds.map((jd) => {
                  const checked = selectedIds.includes(jd.jd_id)
                  return (
                    <label
                      key={jd.jd_id}
                      className={
                        'flex cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ' +
                        (checked ? 'bg-indigo-50 text-indigo-900' : 'hover:bg-slate-50')
                      }
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => handleToggleJd(jd.jd_id)}
                        className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                      />
                      <span className="truncate">{jd.display_name || jd.jd_id}</span>
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-[200px_auto] sm:items-end">
            <div>
              <label className={labelCls}>自荐信语气</label>
              <select value={tone} onChange={(e) => setTone(e.target.value)} className={inputCls}>
                <option value="standard">标准</option>
                <option value="warm">热情</option>
                <option value="concise">简洁</option>
              </select>
            </div>
            <div className="flex items-center gap-3">
              <Btn onClick={handleMatch} disabled={busy}>
                {busy ? '匹配中…' : '开始匹配'}
              </Btn>
              {progress && <span className="text-sm text-slate-600">{progress}</span>}
            </div>
          </div>
        </div>
      </Panel>

      {results.length === 0 && !busy && (
        <EmptyState title="还没有匹配结果" desc="确认简历并选择 JD 后，点击「开始匹配」" />
      )}

      {results.map((r) => (
        <Panel
          key={r.match_id}
          title={`${r.summary || '匹配结果'} · ${r.total_score} 分`}
          desc={r.jd_name || `JD ${r.jd_id}`}
          actions={
            <div className="flex gap-2">
              <Btn size="sm" variant="success" onClick={() => handleCover(r.match_id)} disabled={busyId === r.match_id}>
                {busyId === r.match_id ? '生成中…' : '生成自荐信'}
              </Btn>
              <Btn size="sm" variant="dark" onClick={() => handleApply(r.match_id)} disabled={busyId === r.match_id}>
                记录投递
              </Btn>
            </div>
          }
        >
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-indigo-50 text-lg font-bold tabular-nums text-indigo-700">
              {r.total_score}
            </div>
            <div className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-4">
              {Object.entries(r.dimension_scores).map(([k, v]) => (
                <div key={k} className="rounded-lg bg-slate-50 px-3 py-2">
                  <div className="text-[11px] text-slate-500">{dimLabels[k] || k}</div>
                  <div className="text-sm font-semibold tabular-nums text-slate-800">{v}</div>
                </div>
              ))}
            </div>
          </div>
          {r.gaps.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-xs font-medium text-slate-500">差距与建议</div>
              {r.gaps.map((g) => (
                <div key={g} className="flex items-start gap-2 rounded-lg bg-amber-50/70 px-3 py-2 text-xs text-amber-800">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0">
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 8v4M12 16h.01" />
                  </svg>
                  {g}
                </div>
              ))}
            </div>
          )}
        </Panel>
      ))}

      {cover && (
        <Panel
          title="自荐信"
          desc={`${cover.matchId ? 'match ' + cover.matchId : ''} · 评审分 ${cover.judge_score}${cover.revised ? ' · 已按评审重写' : ''}`}
        >
          <pre className="whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">{plainText(cover.content)}</pre>
        </Panel>
      )}
    </div>
  )
}
