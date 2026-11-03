export const tok = {
  get: () => localStorage.getItem('token'),
  set: (t) => localStorage.setItem('token', t),
  clear: () => localStorage.removeItem('token'),
}

export async function api(path, { method = 'GET', body, form, raw } = {}) {
  const headers = {}
  if (tok.get()) headers.Authorization = `Bearer ${tok.get()}`
  let payload
  if (form) payload = form
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  let res
  try { res = await fetch('/api' + path, { method, headers, body: payload }) }
  catch { throw new Error('Cannot reach the server. Is the backend running on port 8000?') }
  if (res.status === 401 && !path.startsWith('/auth/')) { tok.clear(); window.location.href = '/login'; throw new Error('Session expired') }
  if (!res.ok) {
    let d = res.statusText
    try { const j = await res.json(); d = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch {}
    throw new Error(d)
  }
  return raw ? res : res.json()
}

export async function fetchBlobUrl(path) {
  const res = await api(path, { raw: true })
  return URL.createObjectURL(await res.blob())
}

export async function downloadPdf(id) {
  const url = await fetchBlobUrl(`/interviews/${id}/report.pdf`)
  const a = document.createElement('a'); a.href = url; a.download = `interview_report_${id}.pdf`; a.click()
}
