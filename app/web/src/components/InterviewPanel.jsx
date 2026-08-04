import { useEffect, useState } from 'react'
import {
  createInterviewSession,
  getInterviewSession,
  listInterviewSessions,
  listJDs,
  respondInterview
} from '../api.js'
import { Btn, Chip, Panel, inputCls, labelCls } from './ui.jsx'

function CalendarView({ sessions }) {
  const now = new Date()
  const [ym, setYm] = useState({ y: now.getFullYear(), m: now.getMonth() })
  const [selected, setSelected] = useState(null)

  const byDate = {}
  for (const s of sessions) {
    const d = new Date(s.created_at)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    ;(byDate[key] = byDate[key] || []).push(s)
  }

  const offset = new Date(ym.y, ym.m, 1).getDay()
  const daysInMonth = new Date(ym.y, ym.m + 1, 0).getDate()
  const cells = [...Array(offset).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]
  const dayKey = (d) => `${ym.y}-${String(ym.m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  const daySessions = selected ? byDate[selected] || [] : []

  return (
    <Panel
      title="面试日历"
      desc="按日期查看已完成的陪练会话（绿点为有记录的日期）"
      actions={
        <div className="flex items-center gap-1">
          <button
            onClick={() => setYm((p) => (p.m === 0 ? { y: p.y - 1, m: 11 } : { y: p.y, m: p.m - 1 }))}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
          >
            ‹
          </button>
          <span className="w-28 text-center text-sm font-semibold text-slate-800">{ym.y} 年 {ym.m + 1} 月</span>
          <button
            onClick={() => setYm((p) => (p.m === 11 ? { y: p.y + 1, m: 0 } : { y: p.y, m: p.m + 1 }))}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
          >
            ›
          </button>
        </div>
      }
    >
      <div className="grid grid-cols-7 gap-1 text-center">
        {weekdays.map((w) => (
          <div key={w} className="py-1 text-[11px] font-medium text-slate-400">{w}</div>
        ))}
        {cells.map((d, i) => {
          if (d === null) return <div key={`e${i}`} />
          const k = dayKey(d)
          const count = (byDate[k] || []).length
          const isToday = ym.y === now.getFullYear() && ym.m === now.getMonth() && d === now.getDate()
          return (
            <button
              key={k}
              onClick={() => setSelected(selected === k ? null : k)}
              className={
                'relative flex h-10 flex-col items-center justify-center rounded-lg text-sm transition-colors ' +
                (selected === k
                  ? 'bg-indigo-600 text-white'
                  : isToday
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-700 hover:bg-slate-100')
              }
            >
              <span className="tabular-nums">{d}</span>
              {count > 0 && (
                <span className={`mt-0.5 h-1.5 w-1.5 rounded-full ${selected === k ? 'bg-white' : 'bg-emerald-500'}`} />
              )}
            </button>
          )
        })}
      </div>

      <div className="mt-4 border-t border-slate-100 pt-3">
        {selected ? (
          daySessions.length === 0 ? (
            <p className="text-xs text-slate-400">这一天没有面试记录</p>
          ) : (
            <div className="space-y-2">
              {daySessions.map((s) => (
                <div key={s.session_id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                  <div>
                    <div className="font-medium text-slate-800">{s.jd_name || s.jd_id}</div>
                    <div className="text-xs text-slate-400">
                      {new Date(s.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                      {' · '}{s.status}
                    </div>
                  </div>
                  {s.overall_score > 0 && (
                    <Chip tone="green">总分 {s.overall_score}</Chip>
                  )}
                </div>
              ))}
            </div>
          )
        ) : (
          <p className="text-xs text-slate-400">点击有记录的日期查看当天会话</p>
        )}
      </div>
    </Panel>
  )
}

export default function InterviewPanel({ resumeId, resume }) {
  const [view, setView] = useState('practice')
  const [sessions, setSessions] = useState([])
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
    listInterviewSessions().then((d) => setSessions(d.sessions)).catch(() => {})
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
      const d = await listInterviewSessions()
      setSessions(d.sessions)
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
      if (result.completed) {
        setMessage('面试完成，已生成总结')
        const d = await listInterviewSessions()
        setSessions(d.sessions)
      }
    } catch (e) {
      setMessage(`回答提交失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const tabCls = (activeTab) =>
    'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-150 ' +
    (view === activeTab ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700')

  return (
    <div className="space-y-4">
      <div className="flex gap-1.5">
        <button onClick={() => setView('practice')} className={tabCls('practice')}>模拟面试</button>
        <button onClick={() => setView('calendar')} className={tabCls('calendar')}>面试日历</button>
      </div>

      {view === 'calendar' ? (
        <CalendarView sessions={sessions} />
      ) : !session ? (
        <Panel title="开始模拟面试" desc="面试官会基于 JD 与你的简历定制提问，最多 5 轮">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <div>
              <label className={labelCls}>目标岗位</label>
              <select value={jdId} onChange={(e) => setJdId(e.target.value)} className={inputCls}>
                {jds.map((jd) => (
                  <option key={jd.jd_id} value={jd.jd_id}>{jd.display_name || jd.company || jd.jd_id}</option>
                ))}
              </select>
            </div>
            <div>
              <Btn onClick={handleStart} disabled={busy} className="w-full sm:w-auto">
                {busy ? '创建中…' : '开始模拟面试'}
              </Btn>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>当前简历：</span>
            {resume ? (
              <>
                <span className="font-medium text-slate-700">{resume.name || '（未命名）'}</span>
                {(resume.skills || []).slice(0, 5).map((s) => <Chip key={s} tone="blue">{s}</Chip>)}
              </>
            ) : (
              <span className="font-mono">{resumeId || '（未确认）'}</span>
            )}
          </div>
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
