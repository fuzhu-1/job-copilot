import { useState } from 'react'
import { createJD } from '../api.js'

export default function JDPanel({ onJDAdded }) {
  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

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
    } catch (e) {
      setMessage(`录入失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const tabClass = (active) =>
    `px-4 py-2 rounded-lg text-sm ${active ? 'bg-blue-600 text-white' : 'bg-slate-100 hover:bg-slate-200'}`

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button onClick={() => setMode('text')} className={tabClass(mode === 'text')}>
          粘贴文本
        </button>
        <button onClick={() => setMode('url')} className={tabClass(mode === 'url')}>
          URL 抓取
        </button>
      </div>
      {mode === 'text' ? (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          placeholder="粘贴 JD 全文"
          className="w-full border rounded-lg p-3 text-sm"
        />
      ) : (
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
          className="w-full border rounded-lg p-3 text-sm"
        />
      )}
      <button
        onClick={handleAdd}
        disabled={busy || (mode === 'text' ? !text.trim() : !url.trim())}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
      >
        {busy ? '录入中…' : '录入 JD'}
      </button>
      {message && <p className="text-sm text-slate-600">{message}</p>}
    </div>
  )
}
