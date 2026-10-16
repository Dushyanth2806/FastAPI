import { useEffect, useMemo, useState } from 'react'
import { api, dayEnd, dayStart } from './api.js'

const PAGE = 20
const fmtDate = (ms) => new Date(ms).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
const num = (v, d = 0) => (v === null || v === undefined ? '–' : Number(v).toLocaleString('en-GB', { maximumFractionDigits: d }))

function Bars({ title, rows }) {
  const max = Math.max(1, ...rows.map((r) => r.count))
  return (
    <section className="card">
      <h3>{title}</h3>
      {rows.map((r) => (
        <div className="bar" key={r.name}>
          <span className="bar-label">{r.name}</span>
          <span className="bar-track"><span className="bar-fill" style={{ width: `${(r.count / max) * 100}%` }} /></span>
          <span className="bar-n">{r.count}</span>
        </div>
      ))}
    </section>
  )
}

function Stat({ label, value, hint }) {
  return (
    <div className="stat">
      <div className="stat-v">{value}</div>
      <div className="stat-l">{label}</div>
      {hint && <div className="stat-h">{hint}</div>}
    </div>
  )
}

function Detail({ id, onClose }) {
  const [t, setT] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api(`/tickets/${id}`).then(setT).catch((e) => setErr(e.message)) }, [id])
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="close" onClick={onClose} aria-label="Close">×</button>
        {err && <p className="error">{err}</p>}
        {!t && !err && <p>Loading…</p>}
        {t && (
          <>
            <h2>Ticket #{t._id}</h2>
            <p className="meta">{t.staff} · {t.staffRole} · {t.store} · {fmtDate(t.createdAt)}</p>
            <p className="meta"><span className="pill">{t.dept}</span> <span className="pill alt">{t.status}</span></p>
            <p className="body">{t.text}</p>
            {t.product && <p className="meta">Product: {Object.entries(t.product).map(([k, v]) => `${k}: ${v}`).join(', ')}</p>}
            <p className="meta">Routing latency: {num(t.latency)} · Cost: {t.cost ?? '–'}</p>
            <h3>Replies ({t.replies.length})</h3>
            {t.replies.length === 0 && <p className="meta">No replies yet.</p>}
            {t.replies.map((r, i) => (
              <div className="reply" key={i}>
                <div className="meta">{r.from} · {fmtDate(r.at)}</div>
                <div>{r.text}</div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [opts, setOpts] = useState({ dept: [], store: [], status: [], staffRole: [] })
  const [f, setF] = useState({ q: '', dept: '', store: '', status: '', staff_role: '', from: '', to: '' })
  const [sort, setSort] = useState('desc')
  const [period, setPeriod] = useState('day')
  const [page, setPage] = useState(0)
  const [list, setList] = useState({ total: 0, items: [] })
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(null)

  const params = useMemo(() => ({
    q: f.q, dept: f.dept, store: f.store, status: f.status, staff_role: f.staff_role,
    date_from: dayStart(f.from), date_to: dayEnd(f.to),
  }), [f])

  useEffect(() => { api('/filters').then(setOpts).catch((e) => setError(e.message)) }, [])

  useEffect(() => {
    const h = setTimeout(() => {
      setError('')
      api('/tickets', { ...params, sort, skip: page * PAGE, limit: PAGE }).then(setList).catch((e) => setError(e.message))
    }, 250)
    return () => clearTimeout(h)
  }, [params, sort, page])

  useEffect(() => {
    api('/stats', { ...params, period }).then(setStats).catch((e) => setError(e.message))
  }, [params, period])

  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setPage(0) }
  const pages = Math.max(1, Math.ceil(list.total / PAGE))
  const t = stats?.totals

  const select = (k, label, options) => (
    <select value={f[k]} onChange={set(k)} aria-label={label}>
      <option value="">{label}</option>
      {options.map((o) => <option key={o}>{o}</option>)}
    </select>
  )

  return (
    <main>
      <h1>Helpdesk</h1>
      {error && <p className="error">{error}</p>}

      <div className="filters">
        <input placeholder="Search text, staff, store" value={f.q} onChange={set('q')} />
        {select('dept', 'All departments', opts.dept)}
        {select('store', 'All stores', opts.store)}
        {select('staff_role', 'All roles', opts.staffRole)}
        {select('status', 'All statuses', opts.status)}
        <label>From <input type="date" value={f.from} onChange={set('from')} /></label>
        <label>To <input type="date" value={f.to} onChange={set('to')} /></label>
      </div>

      {t && (
        <>
          <div className="stats">
            <Stat label="Tickets" value={num(t.total)} />
            <Stat label="Avg latency" value={num(t.avgLatency, 0)} hint={`max ${num(t.maxLatency)} · ${t.latencyCount} with data`} />
            <Stat label="Total cost" value={num(t.totalCost, 6)} hint={`avg ${num(t.avgCost, 6)} · ${t.costCount} with data`} />
            <Stat label="Replies" value={num(t.totalReplies)} hint={`${t.noReply} tickets with no reply`} />
          </div>
          <div className="grid">
            <Bars title="By department" rows={stats.byDept} />
            <Bars title="By store" rows={stats.byStore} />
            <Bars title="By staff role" rows={stats.byStaffRole} />
            <section className="card">
              <h3>Per {period} <button className="link" onClick={() => setPeriod(period === 'day' ? 'week' : 'day')}>switch to {period === 'day' ? 'week' : 'day'}</button></h3>
              <div className="scroll"><Bars title="" rows={stats.byPeriod} /></div>
            </section>
          </div>
        </>
      )}

      <section className="card">
        <h3>
          Tickets ({list.total}){' '}
          <button className="link" onClick={() => { setSort(sort === 'desc' ? 'asc' : 'desc'); setPage(0) }}>
            {sort === 'desc' ? 'Newest first ↓' : 'Oldest first ↑'}
          </button>
        </h3>
        <table>
          <thead><tr><th>#</th><th>Date</th><th>Message</th><th>Staff</th><th>Store</th><th>Dept</th><th>Replies</th></tr></thead>
          <tbody>
            {list.items.map((x) => (
              <tr key={x._id} onClick={() => setOpen(x._id)}>
                <td>{x._id}</td>
                <td>{fmtDate(x.createdAt)}</td>
                <td className="clip">{x.text}</td>
                <td>{x.staff}</td>
                <td>{x.store}</td>
                <td><span className="pill">{x.dept}</span></td>
                <td>{x.replyCount}</td>
              </tr>
            ))}
            {list.items.length === 0 && <tr><td colSpan="7" className="meta">No tickets match.</td></tr>}
          </tbody>
        </table>
        <div className="pager">
          <button disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
          <span>Page {page + 1} of {pages}</span>
          <button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      </section>

      {open !== null && <Detail id={open} onClose={() => setOpen(null)} />}
    </main>
  )
}
