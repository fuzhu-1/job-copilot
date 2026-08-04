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
