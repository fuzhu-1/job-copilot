import { useEffect, useState } from 'react'
import {
  createInterviewSession,
  getInterviewSession,
  listJDs,
  respondInterview
} from '../api.js'

export default function InterviewPanel({ resumeId }) {
  const [jds, setJds] = useState([])
  const [jdId, setJdId] = useState('')
  const [session, setSession] = useState(null)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    listJDs().then((d) => {
      setJds(d.jds)
      if (d.jds.length > 0) setJdId(d.jds[0].jd_id)
    }).catch((e) => setMessage(`加载 JD 列表失败：${e.message}`))
  }, [])

  const handleStart = async () => {
    if (!jdId || !resumeId) {
      setMessage('请先确认简历并至少录入一条 JD')
      return
    }
    setBusy(true)
    setMessage('')
    try {
      const data = await createInterviewSession(jdId, resumeId)
      setSession(data)
      setAnswer('')
    } catch (e) {
      setMessage(`开始失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleRespond = async () => {
    if (!answer.trim() || !session) return
    setBusy(true)
    try {
      const result = await respondInterview(session.session_id, answer)
      const updated = await getInterviewSession(session.session_id)
      setSession(updated)
      setAnswer('')
      if (result.completed) setMessage('面试完成，已生成总结')
    } catch (e) {
      setMessage(`回答提交失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {!session ? (
        <div className="bg-white border rounded-lg p-4 space-y-3">
          <div className="text-sm">当前简历：<span className="font-mono">{resumeId || '（未确认）'}</span></div>
          <select value={jdId} onChange={(e) => setJdId(e.target.value)} className="w-full border rounded-lg p-2 text-sm">
            {jds.map((jd) => (
              <option key={jd.jd_id} value={jd.jd_id}>{jd.company} · {jd.title}</option>
            ))}
          </select>
          <button onClick={handleStart} disabled={busy} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
            {busy ? '创建中…' : '开始模拟面试'}
          </button>
          {message && <p className="text-sm text-slate-600">{message}</p>}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="bg-white border rounded-lg p-4 space-y-3">
            <div className="flex justify-between text-xs text-slate-500">
              <span>会话：{session.session_id}</span>
              <span>状态：{session.status}</span>
            </div>
            {session.messages.map((m, i) => (
              <div key={i} className={`rounded-lg p-3 text-sm ${m.role === 'assistant' ? 'bg-blue-50' : 'bg-slate-50'}`}>
                <div className="font-semibold mb-1">{m.role === 'assistant' ? '面试官' : '我'}</div>
                <p className="whitespace-pre-wrap">{m.content}</p>
                {m.feedback && (
                  <div className="mt-2 text-xs text-slate-600">
                    评分：{m.score} · 反馈：{m.feedback}
                  </div>
                )}
              </div>
            ))}
          </div>
          {session.status === 'active' && (
            <div className="bg-white border rounded-lg p-4 space-y-3">
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={4}
                placeholder="输入你的回答…"
                className="w-full border rounded-lg p-3 text-sm"
              />
              <button onClick={handleRespond} disabled={busy || !answer.trim()} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
                {busy ? '提交中…' : '提交回答'}
              </button>
              {message && <p className="text-sm text-slate-600">{message}</p>}
            </div>
          )}
          {session.summary && Object.keys(session.summary).length > 0 && (
            <div className="bg-white border rounded-lg p-4 space-y-2">
              <h2 className="text-sm font-semibold">面试总结 · 总分 {session.summary.overall_score}</h2>
              <p className="text-sm">优势：{session.summary.strengths.join('、')}</p>
              <p className="text-sm">不足：{session.summary.weaknesses.join('、')}</p>
              <p className="text-sm">改进计划：{session.summary.improvement_plan.join('；')}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
