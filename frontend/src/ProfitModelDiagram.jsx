import { money, pct, times } from './format.js'

const W = 150
const H = 84

// Box positions (top-left) in the SVG coordinate space, laid out like the
// Strategic Profit Model figure: ratios flow left-to-right into raw figures.
const BOXES = {
  spread: { x: 20, y: 440, label: ['Equity', 'Spread'], fmt: pct, key: 'equity_spread' },
  roe: { x: 250, y: 330, label: ['Return', 'on Equity'], fmt: pct, key: 'return_on_equity' },
  coe: { x: 250, y: 560, label: ['Cost of', 'Equity Capital'], fmt: pct, key: 'cost_of_equity' },
  fl: { x: 460, y: 330, label: ['Financial', 'Leverage'], fmt: times, key: 'financial_leverage' },
  roa: { x: 670, y: 330, label: ['Return', 'on Assets'], fmt: pct, key: 'return_on_assets' },
  pm: { x: 900, y: 200, label: ['Profit', 'Margin'], fmt: pct, key: 'profit_margin' },
  at: { x: 900, y: 470, label: ['Asset', 'Turnover'], fmt: times, key: 'asset_turnover' },
  ni: { x: 1100, y: 80, label: ['Net', 'Income'], fmt: money, key: 'net_income' },
  ns: { x: 1100, y: 330, label: ['', 'Net Sales'], fmt: money, key: 'net_sales' },
  ta: { x: 1100, y: 590, label: ['Total', 'Assets'], fmt: money, key: 'total_assets' },
  te: { x: 670, y: 570, label: ['Total', 'Equity'], fmt: money, key: 'total_equity' },
  se: { x: 670, y: 790, label: ["Shareholders'", 'Equity'], fmt: money, key: 'shareholders_equity' },
}

// Connector polylines and the operator glyphs that sit beside them.
const LINES = [
  // Equity Spread = ROE − Cost of Equity
  [[170, 482], [215, 482]],
  [[215, 372], [215, 602]],
  [[215, 372], [250, 372]],
  [[215, 602], [250, 602]],
  // ROE = FL × ROA
  [[400, 372], [460, 372]],
  [[610, 372], [670, 372]],
  // ROA = PM × AT
  [[820, 372], [865, 372]],
  [[865, 242], [865, 512]],
  [[865, 242], [900, 242]],
  [[865, 512], [900, 512]],
  // PM = NI ÷ NS
  [[1050, 242], [1075, 242]],
  [[1075, 122], [1075, 355]],
  [[1075, 122], [1100, 122]],
  [[1075, 355], [1100, 355]],
  // AT = NS ÷ TA
  [[1050, 512], [1075, 512]],
  [[1075, 395], [1075, 632]],
  [[1075, 395], [1100, 395]],
  [[1075, 632], [1100, 632]],
  // FL = Total Equity ÷ Shareholders' Equity
  [[535, 414], [535, 700]],
  [[535, 700], [635, 700]],
  [[635, 612], [635, 832]],
  [[635, 612], [670, 612]],
  [[635, 832], [670, 832]],
]

const OPERATORS = [
  ['=', 192, 474],
  ['−', 230, 500],
  ['=', 430, 364],
  ['×', 640, 364],
  ['=', 838, 364],
  ['×', 882, 362],
  ['=', 1062, 234],
  ['÷', 1088, 262],
  ['=', 1062, 504],
  ['÷', 1088, 532],
  ['=', 550, 440],
  ['÷', 650, 722],
]

function Box({ box, top, bottom, currency }) {
  const { x, y, label, fmt } = box
  const cx = x + W / 2
  return (
    <g>
      <text x={cx} y={y - 34} className="spm-label">{label[0]}</text>
      <text x={cx} y={y - 12} className="spm-label">{label[1]}</text>
      <rect x={x} y={y} width={W} height={H} className="spm-box" />
      <text x={cx} y={y + 34} className="spm-value">{fmt(top, currency)}</text>
      <text x={cx} y={y + 66} className="spm-value">{fmt(bottom, currency)}</text>
    </g>
  )
}

export default function ProfitModelDiagram({ start, end, currency }) {
  return (
    <svg viewBox="0 0 1270 900" className="spm" role="img" aria-label="Strategic profit model">
      <text x={40} y={60} className="spm-label spm-year-heading">Year</text>
      <line x1={40} y1={66} x2={88} y2={66} className="spm-line" />
      <text x={40} y={102} className="spm-value spm-year">{end.year}</text>
      <text x={40} y={134} className="spm-value spm-year">{start.year}</text>

      {LINES.map(([[x1, y1], [x2, y2]], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} className="spm-line" />
      ))}
      {OPERATORS.map(([glyph, x, y], i) => (
        <text key={i} x={x} y={y} className="spm-op">{glyph}</text>
      ))}
      {Object.entries(BOXES).map(([id, box]) => (
        <Box key={id} box={box} top={end[box.key]} bottom={start[box.key]} currency={currency} />
      ))}
    </svg>
  )
}
