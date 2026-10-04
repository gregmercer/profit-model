import { useState } from 'react'
import ProfitModelDiagram from './ProfitModelDiagram.jsx'
import { pct, times } from './format.js'

const CURRENCY_SYMBOL = { USD: '$', JPY: '¥', EUR: '€', GBP: '£' }

// [abbreviation, meaning, formula]
const LEGEND = [
  ['NS', 'Net Sales', ''],
  ['NI', 'Net Income', ''],
  ['PM', 'Profit Margin', 'NI / NS'],
  ['TA', 'Total Assets', ''],
  ['AT', 'Asset Turnover', 'NS / TA'],
  ['SE', "Shareholders' Equity", ''],
  ['FL', 'Financial Leverage', 'TA / SE'],
  ['ROA', 'Return on Assets', 'PM × AT = NI / TA'],
  ['ROE', 'Return on Equity', 'FL × ROA = NI / SE'],
  ['CoE', 'Cost of Equity Capital', 'Risk-free rate + Beta × Market risk premium'],
  ['ES', 'Equity Spread', 'ROE − CoE'],
]

async function fetchModel({ symbol, start, end, refresh }) {
  const params = new URLSearchParams({ symbol, start, end, refresh })
  const resp = await fetch(`/api/model?${params}`)
  const body = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error(body.detail ?? `Request failed (${resp.status})`)
  return body
}

// Cost of equity is CAPM (r_f + β × MRP) unless the user typed an override.
function CollectedData({ symbol, fetchedAt, dataFile }) {
  const [json, setJson] = useState(null)
  const [error, setError] = useState('')
  const [loadedFor, setLoadedFor] = useState(null)

  // Get the file when the section opens; get it again after a refresh.
  async function onToggle(e) {
    if (!e.currentTarget.open || loadedFor === fetchedAt) return
    setError('')
    try {
      const resp = await fetch(`/api/data/${encodeURIComponent(symbol)}`)
      const body = await resp.json()
      if (!resp.ok) throw new Error(body.detail ?? `Request failed (${resp.status})`)
      setJson(JSON.stringify(body, null, 2))
      setLoadedFor(fetchedAt)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <details className="panel collected" onToggle={onToggle}>
      <summary>
        Collected data <code>backend/{dataFile}</code>
      </summary>
      {error && <div className="error">{error}</div>}
      {loadedFor === fetchedAt ? <pre>{json}</pre> : !error && <p className="hint">Loading…</p>}
    </details>
  )
}

function withCostOfEquity(year, mrp, override) {
  const coe =
    override !== ''
      ? Number(override) / 100
      : year.risk_free_rate == null
        ? null
        : year.risk_free_rate + year.beta * mrp
  const spread =
    coe == null || year.return_on_equity == null ? null : year.return_on_equity - coe
  return { ...year, cost_of_equity: coe, equity_spread: spread }
}

function Takeaway({ year, name, currency }) {
  if (year.return_on_equity == null) return null
  const sym = CURRENCY_SYMBOL[currency] ?? `${currency} `
  const roeCents = (year.return_on_equity * 100).toFixed(1)
  const spread = year.equity_spread
  return (
    <p className="takeaway">
      In {year.year}, {name} earned {roeCents}¢ for every {sym}1 of shareholders' equity
      {spread != null && (
        <>
          {' '}and generated {spread < 0 ? 'a negative' : 'an'} equity spread of{' '}
          {(Math.abs(spread) * 100).toFixed(1)}¢ on behalf of the shareholders
        </>
      )}
      .
    </p>
  )
}

export default function App() {
  const [form, setForm] = useState({ symbol: 'WMT', start: '2015', end: '2025' })
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [mrp, setMrp] = useState('5.5')
  const [overrides, setOverrides] = useState({ start: '', end: '' })

  async function load(refresh = false) {
    setLoading(true)
    setError('')
    try {
      setData(await fetchModel({ ...form, refresh }))
      setOverrides({ start: '', end: '' })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(e) {
    e.preventDefault()
    load(false)
  }

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value })
  const mrpValue = Number(mrp) / 100 || 0
  const years = data && {
    start: withCostOfEquity(data.start, mrpValue, overrides.start),
    end: withCostOfEquity(data.end, mrpValue, overrides.end),
  }

  return (
    <main>
      <header>
        <h1>Strategic Profit Model</h1>
        <form onSubmit={onSubmit} className="controls">
          <label>
            Stock symbol
            <input value={form.symbol} onChange={update('symbol')} required maxLength={10} />
          </label>
          <label>
            Start year
            <input type="number" value={form.start} onChange={update('start')} required min={1900} max={2100} />
          </label>
          <label>
            End year
            <input type="number" value={form.end} onChange={update('end')} required min={1900} max={2100} />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? 'Loading…' : 'Build model'}
          </button>
        </form>
      </header>

      <p className="acknowledgement">
        This model is based on the Strategic Profit Model in <cite>The Manager's Guide to Financial
        Statement Analysis</cite>, Second Edition,
        <br />
        by Stephen F. Jablonsky and Noah P. Barsky (John Wiley &amp; Sons, 2001).
      </p>

      {error && <div className="error">{error}</div>}

      {data && years && (
        <>
          <section className="figure">
            <h2>
              {data.name} ({data.symbol})
              <span>
                Fiscal years {years.start.year} and {years.end.year} — amounts in millions
                {data.currency !== 'USD' && ` of ${data.currency}`}
              </span>
            </h2>
            <ProfitModelDiagram start={years.start} end={years.end} currency={data.currency} />
            <Takeaway year={years.end} name={data.name} currency={data.currency} />
            <Takeaway year={years.start} name={data.name} currency={data.currency} />
          </section>

          <section className="panels">
            <div className="panel">
              <h3>Cost of equity capital (CAPM)</h3>
              <label className="inline">
                Market risk premium
                <input type="number" step="0.1" value={mrp} onChange={(e) => setMrp(e.target.value)} />%
              </label>
              <table>
                <thead>
                  <tr>
                    <th>Year</th>
                    <th>Risk-free rate</th>
                    <th>Beta</th>
                    <th>CAPM cost</th>
                    <th>Override %</th>
                  </tr>
                </thead>
                <tbody>
                  {['end', 'start'].map((k) => {
                    const y = data[k]
                    const capmCost = withCostOfEquity(y, mrpValue, '').cost_of_equity
                    return (
                      <tr key={k}>
                        <td>{y.year}</td>
                        <td>{pct(y.risk_free_rate)}</td>
                        <td>
                          {times(y.beta)}
                          {y.beta_estimated && <span className="note" title="Not enough price history; beta assumed to be 1.00">*</span>}
                        </td>
                        <td>{pct(capmCost)}</td>
                        <td>
                          <input
                            type="number"
                            step="0.1"
                            placeholder="—"
                            value={overrides[k]}
                            onChange={(e) => setOverrides({ ...overrides, [k]: e.target.value })}
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <p className="hint">
                Risk-free rate = average 10-year Treasury yield over the fiscal year. Beta = 60 monthly
                returns against the S&amp;P 500.
              </p>
            </div>

            <div className="panel">
              <h3>Data</h3>
              <table>
                <tbody>
                  {['end', 'start'].map((k) => (
                    <tr key={k}>
                      <td>{data[k].year}</td>
                      <td>Fiscal year ended {data[k].fiscal_year_end}</td>
                      <td>{data[k].source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="hint">
                Saved in <code>backend/{data.data_file}</code>, fetched {new Date(data.fetched_at).toLocaleString()}.
                Years available: {data.available_years[0]}–{data.available_years.at(-1)}.
              </p>
              <button type="button" className="refresh" onClick={() => load(true)} disabled={loading}>
                Refresh data
              </button>
            </div>
          </section>

          <CollectedData symbol={data.symbol} fetchedAt={data.fetched_at} dataFile={data.data_file} />
        </>
      )}

      <section className="panel legend">
        <h3>Legend</h3>
        <table>
          <tbody>
            {LEGEND.map(([abbr, meaning, formula]) => (
              <tr key={abbr}>
                <th scope="row">{abbr}</th>
                <td>{meaning}</td>
                <td>{formula && `= ${formula}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  )
}
