import { useState } from 'react'
import { generateCoverLetter, runMatch } from '../api.js'

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

  return (
    <div className="space-y-4">
      <div className="bg-white border rounded-lg p-4 text-sm space-y-2">
        <p>简历 ID：<span className="font-mono">{resumeId || '（未确认）'}</span></p>
        <p>已录入 JD：{jdIds.length === 0 ? '（无）' : jdIds.map((id) => <span key={id} className="inline-block bg-slate-100 rounded px-2 py-0.5 mr-1 font-mono text-xs">{id}</span>)}</p>
        <input
          value={extraIds}
          onChange={(e) => setExtraIds(e.target.value)}
          placeholder="补充 JD ID（逗号分隔，可选）"
          className="w-full border rounded-lg p-2 text-sm"
        />
        <div className="flex gap-2 items-center">
          <select value={tone} onChange={(e) => setTone(e.target.value)} className="border rounded-lg p-2 text-sm">
            <option value="standard">自荐信语气：标准</option>
            <option value="warm">自荐信语气：热情</option>
            <option value="concise">自荐信语气：简洁</option>
          </select>
          <button
            onClick={handleMatch}
            disabled={busy}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
          >
            {busy ? '匹配中…' : '开始匹配'}
          </button>
        </div>
        {progress && <p className="text-slate-600">{progress}</p>}
      </div>

      {results.map((r) => (
        <div key={r.match_id} className="bg-white border rounded-lg p-4 space-y-2">
          <div className="flex justify-between">
            <span className="font-mono text-xs">{r.jd_id}</span>
            <span className="text-lg font-bold text-blue-600">{r.total_score} 分</span>
          </div>
          <p className="text-sm">{r.summary}</p>
          <div className="grid grid-cols-4 gap-2 text-xs">
            {Object.entries(r.dimension_scores).map(([k, v]) => (
              <div key={k} className="bg-slate-50 rounded p-2">
                <div className="text-slate-500">{k}</div>
                <div className="font-semibold">{v}</div>
              </div>
            ))}
          </div>
          {r.gaps.length > 0 && (
            <ul className="text-xs text-slate-600 list-disc pl-4">
              {r.gaps.map((g) => <li key={g}>{g}</li>)}
            </ul>
          )}
          <button
            onClick={() => handleCover(r.match_id)}
            disabled={busyId === r.match_id}
            className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm disabled:opacity-50"
          >
            {busyId === r.match_id ? '生成中…' : '生成自荐信'}
          </button>
        </div>
      ))}

      {cover && (
        <div className="bg-white border rounded-lg p-4 space-y-2">
          <div className="text-sm text-slate-600">
            match {cover.matchId} · 评审分 {cover.judge_score} {cover.revised ? '· 已按评审重写' : ''}
          </div>
          <pre className="whitespace-pre-wrap text-sm bg-slate-50 rounded-lg p-4">{cover.content}</pre>
        </div>
      )}
    </div>
  )
}
