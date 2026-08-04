import { useState } from 'react'
import { sendAgentMessage } from '../api.js'

export default function AgentPanel() {
  const [message, setMessage] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  const handleSend = async () => {
    if (!message.trim()) return
    setBusy(true)
    try {
      setResult(await sendAgentMessage(message))
    } catch (e) {
      setResult({ intent: 'error', message: e.message, payload: {} })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-white border rounded-lg p-4 space-y-3">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={4}
          placeholder="例如：分析近期岗位趋势 / 查一下这家公司的面试流程 / 我要上传简历"
          className="w-full border rounded-lg p-3 text-sm"
        />
        <button
          onClick={handleSend}
          disabled={busy || !message.trim()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
        >
          {busy ? '处理中…' : '发送'}
        </button>
      </div>
      {result && (
        <div className="bg-white border rounded-lg p-4 space-y-2">
          <p className="text-sm">
            意图：<span className="font-mono text-blue-600">{result.intent}</span>
          </p>
          <p className="text-sm">{result.message}</p>
          {result.payload && Object.keys(result.payload).length > 0 && (
            <pre className="whitespace-pre-wrap text-xs bg-slate-50 rounded-lg p-3">
              {JSON.stringify(result.payload, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
