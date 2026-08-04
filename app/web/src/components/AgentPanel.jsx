import { useState } from 'react'
import { sendAgentMessage } from '../api.js'
import { Btn, Chip, Panel, inputCls, labelCls } from './ui.jsx'

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

  const suggestions = [
    '分析近期岗位趋势',
    '查一下这家公司的面试流程',
    '我要上传简历',
    '帮我加一条 JD'
  ]

  return (
    <div className="space-y-4">
      <Panel title="助手" desc="Supervisor 识别你的意图并路由到对应功能">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={4}
          placeholder="例如：分析近期岗位趋势 / 查一下这家公司的面试流程 / 我要上传简历"
          className={inputCls}
        />
        <div className="mt-3 flex items-center gap-3">
          <Btn onClick={handleSend} disabled={busy || !message.trim()}>
            {busy ? '处理中…' : '发送'}
          </Btn>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => setMessage(s)}
              className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600 transition-colors hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
            >
              {s}
            </button>
          ))}
        </div>
      </Panel>

      {result && (
        <Panel
          title="助手回复"
          actions={<Chip tone={result.intent === 'error' ? 'rose' : 'indigo'}>{result.intent}</Chip>}
        >
          <p className="text-sm text-slate-700">{result.message}</p>
          {result.payload && Object.keys(result.payload).length > 0 && (
            <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 font-mono text-xs leading-relaxed text-slate-600">
              {JSON.stringify(result.payload, null, 2)}
            </pre>
          )}
        </Panel>
      )}
    </div>
  )
}
