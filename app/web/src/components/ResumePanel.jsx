import { useState } from 'react'
import { confirmResume, uploadResume } from '../api.js'
import { Btn, Chip, EmptyState, Panel, inputCls } from './ui.jsx'

function InfoRow({ label, value }) {
  if (!value) return null
  return (
    <div>
      <div className="text-[11px] font-medium text-slate-400">{label}</div>
      <div className="text-sm text-slate-800">{value}</div>
    </div>
  )
}

function ItemList({ title, items, fields }) {
  if (!items || items.length === 0) return null
  return (
    <div>
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{title}</div>
      <div className="space-y-2">
        {items.map((item, i) => (
          <div key={i} className="rounded-lg bg-slate-50 px-3 py-2.5 text-sm">
            {fields.map((f) => (
              <div key={f.key} className={f.className || ''}>
                {f.label && <span className="text-slate-400">{f.label}</span>}
                {item[f.key] || '—'}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function ResumeView({ resume }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <InfoRow label="姓名" value={resume.name} />
        <InfoRow label="邮箱" value={resume.email} />
        <InfoRow label="电话" value={resume.phone} />
        <InfoRow label="城市" value={resume.city} />
      </div>
      <ItemList
        title="教育经历"
        items={resume.education}
        fields={[
          { key: 'school', label: '' },
          { key: 'major', label: ' · ' },
          { key: 'degree', label: ' · ' },
          { key: 'years', label: '（' }
        ]}
      />
      <ItemList
        title="工作 / 实习经历"
        items={resume.experience}
        fields={[
          { key: 'company', label: '' },
          { key: 'role', label: ' · ' },
          { key: 'years', label: ' · ' }
        ]}
      />
      <ItemList
        title="项目经历"
        items={resume.projects}
        fields={[
          { key: 'name', label: '' },
          { key: 'tech', label: ' · ' },
          { key: 'description', label: ' · ' }
        ]}
      />
      {resume.skills && resume.skills.length > 0 && (
        <div>
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">技能</div>
          <div className="flex flex-wrap gap-1.5">
            {resume.skills.map((s) => <Chip key={s} tone="indigo">{s}</Chip>)}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ResumePanel({ onResumeReady }) {
  const [file, setFile] = useState(null)
  const [uploadedId, setUploadedId] = useState('')
  const [resume, setResume] = useState(null)
  const [confirmed, setConfirmed] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [editedJson, setEditedJson] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [saved, setSaved] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('jc_resume_structured') || 'null')
    } catch {
      return null
    }
  })

  const handleUpload = async () => {
    if (!file) return
    setBusy(true)
    setMessage('')
    try {
      const data = await uploadResume(file)
      setUploadedId(data.resume_id)
      setResume(data.structured)
      setConfirmed(false)
      setEditMode(false)
      setMessage('解析完成，请核对下方内容后确认')
    } catch (e) {
      setMessage(`解析失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const handleConfirm = async () => {
    let structured = resume
    if (editMode) {
      try {
        structured = JSON.parse(editedJson)
      } catch {
        setMessage('JSON 格式有误，请修正后再确认')
        return
      }
    }
    setBusy(true)
    try {
      await confirmResume(uploadedId, structured)
      setResume(structured)
      setConfirmed(true)
      setSaved(structured)
      localStorage.setItem('jc_resume_structured', JSON.stringify(structured))
      onResumeReady(uploadedId, structured)
      setMessage('已确认并入库，可以开始录入 JD 了')
    } catch (e) {
      setMessage(`确认失败：${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const startOver = () => {
    setFile(null)
    setUploadedId('')
    setResume(null)
    setConfirmed(false)
    setEditMode(false)
    setMessage('')
  }

  return (
    <div className="space-y-4">
      {saved && (
        <Panel
          title="已确认简历"
          desc={saved.name ? `候选人：${saved.name}` : '已入库'}
          actions={
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              已确认
            </span>
          }
        >
          <ResumeView resume={saved} />
        </Panel>
      )}

      {!resume ? (
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
      ) : (
        <Panel
          title={confirmed ? '简历已确认' : '解析结果'}
          desc={confirmed ? '已入库，可开始录入 JD' : '请核对内容，有误可编辑后确认'}
          actions={
            confirmed ? (
              <Btn variant="ghost" size="sm" onClick={startOver}>重新上传</Btn>
            ) : (
              <>
                <Btn variant="ghost" size="sm" onClick={() => {
                  if (!editMode) setEditedJson(JSON.stringify(resume, null, 2))
                  setEditMode(!editMode)
                }}>
                  {editMode ? '返回预览' : '编辑'}
                </Btn>
                <Btn variant="success" onClick={handleConfirm} disabled={busy}>
                  {busy ? '确认中…' : '确认并入库'}
                </Btn>
              </>
            )
          }
        >
          {editMode ? (
            <textarea
              value={editedJson}
              onChange={(e) => setEditedJson(e.target.value)}
              rows={18}
              spellCheck={false}
              className={`${inputCls} font-mono text-xs leading-relaxed`}
            />
          ) : (
            <ResumeView resume={resume} />
          )}
          {message && <p className="mt-3 text-sm text-slate-600">{message}</p>}
        </Panel>
      )}
    </div>
  )
}
