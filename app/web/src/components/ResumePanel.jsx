import { useState } from 'react'
import { confirmResume, uploadResume } from '../api.js'
import { Btn, EmptyState, Panel, inputCls } from './ui.jsx'

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

  if (!edited) {
    return (
      <Panel title="上传简历" desc="支持 PDF 格式，解析结果需人工确认后入库">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <label className="group flex w-full cursor-pointer items-center justify-center gap-3 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/60 px-4 py-8 transition-colors hover:border-indigo-400 hover:bg-indigo-50/40 sm:max-w-md">
            <input
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => setFile(e.target.files[0])}
            />
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400 transition-colors group-hover:text-indigo-500">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <path d="M17 8l-5-5-5 5M12 3v12" />
            </svg>
            <div className="text-left">
              <div className="text-sm font-medium text-slate-700">
                {file ? file.name : '点击选择简历 PDF'}
              </div>
              <div className="mt-0.5 text-xs text-slate-400">
                {file ? '已选择文件' : '拖拽或点击选择均可'}
              </div>
            </div>
          </label>
          <Btn onClick={handleUpload} disabled={busy || !file} className="shrink-0">
            {busy ? '解析中…' : '上传并解析'}
          </Btn>
        </div>
        {message && <p className="mt-4 text-sm text-slate-600">{message}</p>}
      </Panel>
    )
  }

  return (
    <div className="space-y-4">
      <Panel
        title="结构化结果"
        desc="LLM 提取内容可能有偏差，请核对后确认入库"
        actions={
          <Btn variant="success" onClick={handleConfirm} disabled={busy || !uploadedId}>
            确认并入库
          </Btn>
        }
      >
        <textarea
          value={edited}
          onChange={(e) => setEdited(e.target.value)}
          rows={18}
          spellCheck={false}
          className={`${inputCls} font-mono text-xs leading-relaxed`}
        />
        {message && <p className="mt-3 text-sm text-slate-600">{message}</p>}
      </Panel>
    </div>
  )
}
