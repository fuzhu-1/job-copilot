import { useEffect, useState } from 'react'
import {
  createJD,
  createJDsBatch,
  deleteJDsBatch,
  generateCompanyResearch,
  generateMarketInsight,
  listJDs
} from '../api.js'
import { Btn, Chip, EmptyState, Panel, inputCls } from './ui.jsx'

export default function JDPanel({ onJDAdded }) {
  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [batchText, setBatchText] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [jds, setJds] = useState([])
  const [insight, setInsight] = useState(null)
  const [research, setResearch] = useState({})
  const [busyJdId, setBusyJdId] = useState('')
  const [selected, setSelected] = useState([])

  const refreshJds = async () => {
    const data = await listJDs()
    setJds(data.jds)
    setSelected([])
  }

  useEffect(() => {
    refreshJds().catch((e) => setMessage(`加载 JD 列表失败：${e.message}`))
  }, [])

  const handleAdd = async () => {
    setBusy(true)
    setMessage('')
    try {
      const payload = mode === 'url' ? { source: 'url', url } : { source: 'text', text }
      const data = await createJD(payload)
      onJDAdded(data.jd_id)
      setMessage(`已录入：${data.company} ${data.title}`)
      setText('')
      setUrl('')
      await refreshJds()
    } catch (e) {
      setMessage(`录入失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleBatch = async () => {
    const texts = batchText.split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean)
    if (texts.length === 0) {
      setMessage('请用空行分隔多条 JD')
      return
    }
    setBusy(true)
    setMessage('')
    try {
      const data = await createJDsBatch(texts)
      setMessage(`批量录入成功：${data.jd_ids.length} 条`)
      setBatchText('')
      await refreshJds()
    } catch (e) {
      setMessage(`批量录入失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleInsight = async () => {
    setBusy(true)
    setMessage('')
    try {
      const data = await generateMarketInsight()
      setInsight(data.report)
    } catch (e) {
      setMessage(`洞察生成失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleResearch = async (jdId) => {
    setBusyJdId(jdId)
    try {
      const data = await generateCompanyResearch(jdId)
      setResearch((prev) => ({ ...prev, [jdId]: data.report }))
    } catch (e) {
      setMessage(`企业研究失败：${e.message}`)
    } finally {
      setBusyJdId('')
    }
  }

  const handleToggle = (jdId) => {
    setSelected((prev) =>
      prev.includes(jdId) ? prev.filter((x) => x !== jdId) : [...prev, jdId]
    )
  }

  const handleSelectAll = () => {
    setSelected(selected.length === jds.length ? [] : jds.map((jd) => jd.jd_id))
  }

  const handleDeleteSelected = async () => {
    if (selected.length === 0) return
    if (!window.confirm(`确认删除选中的 ${selected.length} 条 JD？此操作不可恢复。`)) return
    setBusy(true)
    try {
      const data = await deleteJDsBatch(selected)
      setMessage(`已删除 ${data.deleted} 条 JD`)
      await refreshJds()
    } catch (e) {
      setMessage(`删除失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleDeleteOne = async (jdId) => {
    if (!window.confirm('确认删除这条 JD？此操作不可恢复。')) return
    setBusy(true)
    try {
      const data = await deleteJDsBatch([jdId])
      setMessage(`已删除 ${data.deleted} 条 JD`)
      await refreshJds()
    } catch (e) {
      setMessage(`删除失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const tabCls = (activeTab) =>
    'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-150 ' +
    (activeTab === mode ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700')

  return (
    <div className="space-y-4">
      <Panel title="录入岗位 JD" desc="粘贴文本或抓取公开 URL，结构化后自动入库">
        <div className="flex gap-1.5">
          <button onClick={() => setMode('text')} className={tabCls('text')}>粘贴文本</button>
          <button onClick={() => setMode('url')} className={tabCls('url')}>URL 抓取</button>
        </div>
        <div className="mt-4">
          {mode === 'text' ? (
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              placeholder="粘贴 JD 全文"
              className={inputCls}
            />
          ) : (
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
              className={inputCls}
            />
          )}
        </div>
        <div className="mt-4">
          <Btn onClick={handleAdd} disabled={busy || (mode === 'text' ? !text.trim() : !url.trim())}>
            {busy ? '录入中…' : '录入 JD'}
          </Btn>
        </div>
      </Panel>

      <Panel title="批量导入" desc="每条 JD 用空行分隔，一次录入多条">
        <textarea
          value={batchText}
          onChange={(e) => setBatchText(e.target.value)}
          rows={6}
          placeholder={'JD1 全文…\n\nJD2 全文…'}
          className={inputCls}
        />
        <div className="mt-4">
          <Btn onClick={handleBatch} disabled={busy}>
            {busy ? '批量录入中…' : '批量录入'}
          </Btn>
        </div>
      </Panel>

      <Panel
        title="市场洞察"
        desc="基于库内 JD 的确定性聚合：技能频次、薪资、城市与公司分布"
        actions={<Btn onClick={handleInsight} disabled={busy}>生成洞察报告</Btn>}
      >
        {insight ? (
          <div className="grid gap-3 text-sm sm:grid-cols-2">
            {insight.narrative && (
              <div className="rounded-xl bg-indigo-50/70 p-4 sm:col-span-2">
                <div className="text-xs font-medium text-indigo-600">市场解读</div>
                <p className="mt-1 text-sm leading-relaxed text-indigo-900">{insight.narrative}</p>
              </div>
            )}
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs font-medium text-slate-500">库内 JD</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{insight.total_jds} 条</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs font-medium text-slate-500">热门技能</div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {insight.top_skills.map((s) => (
                  <Chip key={s.skill} tone="indigo">{s.skill} × {s.count}</Chip>
                ))}
              </div>
            </div>
            {insight.salary_stats.median && (
              <div className="rounded-xl bg-slate-50 p-4">
                <div className="text-xs font-medium text-slate-500">薪资参考</div>
                <div className="mt-1 text-sm text-slate-700">
                  中位 <span className="font-semibold tabular-nums">{insight.salary_stats.median}k</span>
                  <span className="mx-1 text-slate-400">·</span>
                  区间 {insight.salary_stats.min}-{insight.salary_stats.max}k
                </div>
              </div>
            )}
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs font-medium text-slate-500">城市 / 公司分布</div>
              <div className="mt-1 text-xs leading-relaxed text-slate-600">
                <div>{JSON.stringify(insight.location_counts)}</div>
                <div className="mt-0.5">{JSON.stringify(insight.company_counts)}</div>
              </div>
            </div>
          </div>
        ) : (
          <EmptyState title="暂无洞察报告" desc="录入几条 JD 后点击「生成洞察报告」" />
        )}
      </Panel>

      <Panel
        title={`JD 列表（${jds.length}）`}
        desc="勾选后可批量删除，也可逐条生成企业研究"
        actions={
          <div className="flex items-center gap-2">
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-600">
              <input
                type="checkbox"
                checked={jds.length > 0 && selected.length === jds.length}
                onChange={handleSelectAll}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600"
              />
              全选
            </label>
            <Btn
              size="sm"
              variant="danger"
              onClick={handleDeleteSelected}
              disabled={selected.length === 0 || busy}
            >
              删除选中{selected.length > 0 ? `（${selected.length}）` : ''}
            </Btn>
          </div>
        }
      >
        {jds.length === 0 ? (
          <EmptyState title="暂无 JD" desc="先录入或批量导入岗位 JD" />
        ) : (
          <div className="space-y-2">
            {jds.map((jd) => (
              <div key={jd.jd_id} className={`rounded-xl border p-3.5 transition-colors ${selected.includes(jd.jd_id) ? 'border-indigo-300 bg-indigo-50/40' : 'border-slate-200 hover:border-indigo-200 hover:bg-indigo-50/30'}`}>
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={selected.includes(jd.jd_id)}
                    onChange={() => handleToggle(jd.jd_id)}
                    className="h-4 w-4 shrink-0 rounded border-slate-300 text-indigo-600"
                  />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-slate-800">
                      {jd.company || '（未识别公司）'} · {jd.title || '（未识别岗位）'}
                    </div>
                    <div className="mt-0.5 font-mono text-[11px] text-slate-400">{jd.jd_id}</div>
                  </div>
                  <div className="ml-auto flex shrink-0 items-center gap-2">
                    <Btn size="sm" variant="dark" onClick={() => handleResearch(jd.jd_id)} disabled={busyJdId === jd.jd_id}>
                      {busyJdId === jd.jd_id ? '研究中…' : '企业研究'}
                    </Btn>
                    <button
                      onClick={() => handleDeleteOne(jd.jd_id)}
                      disabled={busy}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                      title="删除"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6" />
                      </svg>
                    </button>
                  </div>
                </div>
                {research[jd.jd_id] && (
                  <div className="mt-3 space-y-1 rounded-lg bg-white p-3 text-xs text-slate-600 ring-1 ring-slate-100">
                    <div>面试流程：{research[jd.jd_id].interview_process || '（未知）'}</div>
                    <div>薪资参考：{research[jd.jd_id].salary_reference || '（未知）'}</div>
                    <div>团队背景：{research[jd.jd_id].team_background || '（未知）'}</div>
                    {research[jd.jd_id].source_note && (
                      <div className="text-amber-600">{research[jd.jd_id].source_note}</div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>

      {message && <p className="text-sm text-slate-600">{message}</p>}
    </div>
  )
}
