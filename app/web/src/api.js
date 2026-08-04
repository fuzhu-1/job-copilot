async function parseError(res) {
  try {
    return (await res.json()).detail || res.statusText
  } catch {
    return res.statusText
  }
}

export async function uploadResume(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/resume/upload', { method: 'POST', body: form })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function confirmResume(resumeId, structured) {
  const res = await fetch(`/api/resume/${resumeId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ structured })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function createJD(payload) {
  const res = await fetch('/api/jds', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function runMatch(resumeId, jdIds) {
  const res = await fetch('/api/matches', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_id: resumeId, jd_ids: jdIds })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function generateCoverLetter(matchId, tone) {
  const res = await fetch(`/api/matches/${matchId}/cover-letter`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ match_id: matchId, tone })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function createApplication(matchId, notes = '') {
  const res = await fetch('/api/applications', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ match_id: matchId, notes })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function listApplications() {
  const res = await fetch('/api/applications')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function getReminders() {
  const res = await fetch('/api/applications/reminders')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function transitionApplication(appId, targetStatus, note = '') {
  const res = await fetch(`/api/applications/${appId}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_status: targetStatus, note })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function registerCustomStatus(appId, status, fromStatus, next) {
  const res = await fetch(`/api/applications/${appId}/custom-statuses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, from_status: fromStatus, next })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function createJDsBatch(texts) {
  const res = await fetch('/api/jds/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function listJDs() {
  const res = await fetch('/api/jds')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function generateCompanyResearch(jdId) {
  const res = await fetch(`/api/jds/${jdId}/research`, { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function generateMarketInsight() {
  const res = await fetch('/api/insights/market', { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function sendAgentMessage(message) {
  const res = await fetch('/api/agent/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function createInterviewSession(jdId, resumeId) {
  const res = await fetch('/api/interviews/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jd_id: jdId, resume_id: resumeId })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function respondInterview(sessionId, answer) {
  const res = await fetch(`/api/interviews/sessions/${sessionId}/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer })
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function getInterviewSession(sessionId) {
  const res = await fetch(`/api/interviews/sessions/${sessionId}`)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function runEval() {
  const res = await fetch('/api/eval/runs', { method: 'POST' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function listEvalRuns() {
  const res = await fetch('/api/eval/runs')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function syncGoldenSet(path = '') {
  const res = await fetch('/api/eval/golden/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(path ? { path } : {})
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
