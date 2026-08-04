import { useState } from 'react'
import { confirmResume, uploadResume } from '../api.js'

export default function ResumePanel({ onResumeReady }) {
  const [file, setFile] = useState(null)
  const [uploadedId, setUploadedId] = useState('')
  const [edited, setEdited] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  const handleUpload = async () => {
    if (!file) return
    setBusy(true)
    setMessage('')
    try {
      const data = await uploadResume(file)
      setUploadedId(data.resume_id)
      setEdited(JSON.stringify(data.structured, null, 2))
      setMessage('解析完成，请核对下方结构化结果后确认')
    } catch (e) {
      setMessage(`解析失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleConfirm = async () => {
    let structured
    try {
      structured = JSON.parse(edited)
    } catch {
      setMessage('结构化结果不是合法 JSON，请修正后再确认')
      return
    }
    setBusy(true)
    try {
      await confirmResume(uploadedId, structured)
      onResumeReady(uploadedId)
      setMessage('已确认并入库，可以开始录入 JD 了')
    } catch (e) {
      setMessage(`确认失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-3 items-end">
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files[0])}
          className="text-sm"
        />
        <button
          onClick={handleUpload}
          disabled={busy || !file}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50"
        >
          {busy ? '解析中…' : '上传并解析'}
        </button>
      </div>
      {message && <p className="text-sm text-slate-600">{message}</p>}
      {edited && (
        <div className="space-y-3">
          <textarea
            value={edited}
            onChange={(e) => setEdited(e.target.value)}
            rows={18}
            className="w-full font-mono text-xs border rounded-lg p-3"
          />
          <button
            onClick={handleConfirm}
            disabled={busy || !uploadedId}
            className="px-4 py-2 bg-green-600 text-white rounded-lg disabled:opacity-50"
          >
            确认并入库
          </button>
        </div>
      )}
    </div>
  )
}
