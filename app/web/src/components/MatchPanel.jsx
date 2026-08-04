import { useState } from 'react'
import { createApplication, generateCoverLetter, runMatch } from '../api.js'
import { Btn, Chip, EmptyState, Panel, inputCls, labelCls } from './ui.jsx'

export default function MatchPanel({ resumeId, jdIds }) {
  const [extraIds, setExtraIds] = useState('')
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState('')
  const [results, setResults] = useState([])
  const [cover, setCover] = useState(null)
  const [busyId, setBusyId] = useState('')
  const [tone, setTone] = useState('standard')

  const handleMatch = async () => {
    const ids = [...jdIds, ...extraIds.split(',').map((s) => s.trim()).filter(Boolean)]
    if (!resumeId || ids.length === 0) {
      setProgress('请先确认简历并录入至少一个 JD')
      return
    }
    setBusy(true)
    setResults([])
    setCover(null)
    setProgress('发起匹配…')
    try {
      const { task_id } = await runMatch(resumeId, ids)
      const es = new EventSource(`/api/matches/${task_id}/stream`)
      es.addEventListener('match_progress', (e) => {
        const d = JSON.parse(e.data)
        setProgress(`正在匹配 ${d.index + 1}/${d.total}…`)
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
      es.addEventListener('error', () => {
        setProgress('匹配出错，请检查服务端日志')
        setBusy(false)
        es.close()
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

  const dimLabels = {
    skill_match: '技能匹配',
    experience_match: '经历相关',
    education_match: '教育背景',
    hard_requirements: '硬性条件'
  }

  return (
    <div className="space-y-4">
      <Panel title="发起匹配" desc="对已确认简历与所选 JD 运行四维打分，SSE 实时推送进度">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-xs font-medium text-slate-500">简历</span>
            <span className="font-mono text-xs text-slate-700">{resumeId || '（未确认）'}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-xs font-medium text-slate-500">目标 JD</span>
            {jdIds.length === 0 ? (
              <span className="text-xs text-slate-400">（无，可手动补充 ID）</span>
            ) : (
              jdIds.map((id) => <Chip key={id} tone="blue">{id}</Chip>)
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <div>
              <label className={labelCls}>补充 JD ID（逗号分隔，可选）</label>
              <input value={extraIds} onChange={(e) => setExtraIds(e.target.value)} placeholder="jd_id1, jd_id2" className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>自荐信语气</label>
              <select value={tone} onChange={(e) => setTone(e.target.value)} className={inputCls}>
                <option value="standard">标准</option>
                <option value="warm">热情</option>
                <option value="concise">简洁</option>
              </select>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Btn onClick={handleMatch} disabled={busy}>
              {busy ? '匹配中…' : '开始匹配'}
            </Btn>
            {progress && <span className="text-sm text-slate-600">{progress}</span>}
          </div>
        </div>
      </Panel>

      {results.length === 0 && !busy && (
        <EmptyState title="还没有匹配结果" desc="确认简历并录入 JD 后，点击「开始匹配」" />
      )}

      {results.map((r) => (
        <Panel
          key={r.match_id}
          title={`${r.summary || '匹配结果'} · ${r.total_score} 分`}
          desc={`JD ${r.jd_id}`}
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
          desc={`match ${cover.matchId} · 评审分 ${cover.judge_score}${cover.revised ? ' · 已按评审重写' : ''}`}
        >
          <pre className="whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">{cover.content}</pre>
        </Panel>
      )}
    </div>
  )
}
