// Date filters take epoch ms, inclusive. A local day runs from 00:00:00.000 to 23:59:59.999.
export const dayStart = (s) => (s ? new Date(`${s}T00:00:00.000`).getTime() : undefined)
export const dayEnd = (s) => (s ? new Date(`${s}T23:59:59.999`).getTime() : undefined)

export async function api(path, params = {}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, v)
  })
  const res = await fetch(`/api${path}${qs.size ? `?${qs}` : ''}`)
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch { /* keep generic message */ }
    throw new Error(detail)
  }
  return res.json()
}
