import { useEffect, useState } from 'react'
import {
  createInterviewSession,
  getInterviewSession,
  listJDs,
  respondInterview
} from '../api.js'
import { Btn, Chip, EmptyState, Panel, inputCls, labelCls } from './ui.jsx'

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
        <Panel title="开始模拟面试" desc="面试官会基于 JD 与你的简历定制提问，最多 5 轮">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <div>
              <label className={labelCls}>目标岗位</label>
              <select value={jdId} onChange={(e) => setJdId(e.target.value)} className={inputCls}>
                {jds.map((jd) => (
                  <option key={jd.jd_id} value={jd.jd_id}>{jd.company} · {jd.title}</option>
                ))}
              </select>
            </div>
            <div>
              <Btn onClick={handleStart} disabled={busy} className="w-full sm:w-auto">
                {busy ? '创建中…' : '开始模拟面试'}
              </Btn>
            </div>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            当前简历：<span className="font-mono">{resumeId || '（未确认）'}</span>
          </p>
          {message && <p className="mt-3 text-sm text-slate-600">{message}</p>}
        </Panel>
      ) : (
        <>
          <Panel
            title={`面试会话 · ${session.status === 'active' ? '进行中' : '已完成'}`}
            desc={`${session.session_id} · 每轮回答都会收到评分与 STAR 反馈`}
            actions={<Chip tone={session.status === 'active' ? 'blue' : 'green'}>{session.status}</Chip>}
          >
            <div className="space-y-3">
              {session.messages.map((m, i) => (
                <div
                  key={i}
                  className={
                    'max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-relaxed ' +
                    (m.role === 'assistant'
                      ? 'rounded-tl-sm bg-slate-100 text-slate-800'
                      : 'ml-auto rounded-tr-sm bg-indigo-600 text-white')
                  }
                >
                  <div className={'mb-1 text-[11px] font-medium ' + (m.role === 'assistant' ? 'text-slate-400' : 'text-indigo-200')}>
                    {m.role === 'assistant' ? '面试官' : '我'}
                  </div>
                  <p className="whitespace-pre-wrap">{m.content}</p>
                  {m.feedback && (
                    <div className={'mt-2 text-xs ' + (m.role === 'assistant' ? 'text-slate-500' : 'text-indigo-100')}>
                      评分 {m.score} · {m.feedback}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Panel>

          {session.status === 'active' && (
            <Panel title="你的回答" desc="尽量使用 STAR 结构：情境-任务-行动-结果">
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={4}
                placeholder="输入你的回答…"
                className={inputCls}
              />
              <div className="mt-3">
                <Btn onClick={handleRespond} disabled={busy || !answer.trim()}>
                  {busy ? '提交中…' : '提交回答'}
                </Btn>
              </div>
              {message && <p className="mt-3 text-sm text-slate-600">{message}</p>}
            </Panel>
          )}

          {session.summary && Object.keys(session.summary).length > 0 && (
            <Panel
              title={`面试总结 · 总分 ${session.summary.overall_score}`}
              desc="面试复盘：优势、不足与改进计划"
            >
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl bg-emerald-50 p-4">
                  <div className="text-xs font-medium text-emerald-700">优势</div>
                  <div className="mt-1 text-sm text-emerald-900">{session.summary.strengths.join('、') || '—'}</div>
                </div>
                <div className="rounded-xl bg-rose-50 p-4">
                  <div className="text-xs font-medium text-rose-700">不足</div>
                  <div className="mt-1 text-sm text-rose-900">{session.summary.weaknesses.join('、') || '—'}</div>
                </div>
                <div className="rounded-xl bg-indigo-50 p-4">
                  <div className="text-xs font-medium text-indigo-700">改进计划</div>
                  <div className="mt-1 text-sm text-indigo-900">{session.summary.improvement_plan.join('；') || '—'}</div>
                </div>
              </div>
            </Panel>
          )}
        </>
      )}
    </div>
  )
}
