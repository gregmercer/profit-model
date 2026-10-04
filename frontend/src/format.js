const DASH = '—'

export function money(value, currency = 'USD') {
  if (value == null) return DASH
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(value / 1e6)
}

export function pct(value) {
  return value == null ? DASH : `${(value * 100).toFixed(1)}%`
}

export function times(value) {
  return value == null ? DASH : value.toFixed(2)
}
