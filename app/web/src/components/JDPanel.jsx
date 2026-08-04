import { useEffect, useState } from 'react'
import {
  createJD,
  createJDsBatch,
  generateCompanyResearch,
  generateMarketInsight,
  listJDs
} from '../api.js'

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

  const refreshJds = async () => {
    const data = await listJDs()
    setJds(data.jds)
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
      setMessage(`已录入：${data.company} ${data.title}（${data.jd_id}）`)
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

  const tabClass = (active) =>
    `px-4 py-2 rounded-lg text-sm ${active ? 'bg-blue-600 text-white' : 'bg-slate-100 hover:bg-slate-200'}`

  return (
    <div className="space-y-6">
      <div className="bg-white border rounded-lg p-4 space-y-3">
        <div className="flex gap-2">
          <button onClick={() => setMode('text')} className={tabClass(mode === 'text')}>粘贴文本</button>
          <button onClick={() => setMode('url')} className={tabClass(mode === 'url')}>URL 抓取</button>
        </div>
        {mode === 'text' ? (
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} placeholder="粘贴 JD 全文" className="w-full border rounded-lg p-3 text-sm" />
        ) : (
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" className="w-full border rounded-lg p-3 text-sm" />
        )}
        <button onClick={handleAdd} disabled={busy || (mode === 'text' ? !text.trim() : !url.trim())} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
          {busy ? '录入中…' : '录入 JD'}
        </button>
      </div>

      <div className="bg-white border rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold">批量导入（空行分隔多条 JD）</h2>
        <textarea value={batchText} onChange={(e) => setBatchText(e.target.value)} rows={8} placeholder="JD1 全文…&#10;&#10;JD2 全文…" className="w-full border rounded-lg p-3 text-sm" />
        <button onClick={handleBatch} disabled={busy} className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
          {busy ? '批量录入中…' : '批量录入'}
        </button>
      </div>

      <div className="bg-white border rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">市场洞察</h2>
          <button onClick={handleInsight} disabled={busy} className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50">
            生成洞察报告
          </button>
        </div>
        {insight && (
          <div className="text-xs space-y-2">
            <p>共 {insight.total_jds} 条 JD</p>
            <p>热门技能：{insight.top_skills.map((s) => `${s.skill}(${s.count})`).join('、')}</p>
            {insight.salary_stats.median && (
              <p>薪资参考：中位 {insight.salary_stats.median}k / 区间 {insight.salary_stats.min}-{insight.salary_stats.max}k</p>
            )}
            <p>城市分布：{JSON.stringify(insight.location_counts)}</p>
            <p>公司分布：{JSON.stringify(insight.company_counts)}</p>
          </div>
        )}
      </div>

      <div className="bg-white border rounded-lg p-4 space-y-2">
        <h2 className="text-sm font-semibold">JD 列表（{jds.length}）</h2>
        {jds.length === 0 && <p className="text-xs text-slate-500">暂无 JD</p>}
        {jds.map((jd) => (
          <div key={jd.jd_id} className="border rounded-lg p-3 space-y-2">
            <div className="flex justify-between items-center">
              <div>
                <span className="font-semibold text-sm">{jd.company} · {jd.title}</span>
                <span className="ml-2 font-mono text-xs text-slate-400">{jd.jd_id}</span>
              </div>
              <button onClick={() => handleResearch(jd.jd_id)} disabled={busyJdId === jd.jd_id} className="px-3 py-1 bg-slate-700 text-white rounded text-xs disabled:opacity-50">
                {busyJdId === jd.jd_id ? '研究中…' : '企业研究'}
              </button>
            </div>
            {research[jd.jd_id] && (
              <div className="text-xs bg-slate-50 rounded p-3 space-y-1">
                <p>面试流程：{research[jd.jd_id].interview_process || '（未知）'}</p>
                <p>薪资参考：{research[jd.jd_id].salary_reference || '（未知）'}</p>
                <p>团队背景：{research[jd.jd_id].team_background || '（未知）'}</p>
                {research[jd.jd_id].source_note && <p className="text-amber-600">{research[jd.jd_id].source_note}</p>}
              </div>
            )}
          </div>
        ))}
      </div>

      {message && <p className="text-sm text-slate-600">{message}</p>}
    </div>
  )
}
