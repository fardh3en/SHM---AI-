import { Link } from 'react-router-dom'
import styles from './ProductPreview.module.css'

/** Schematic dashboard preview drawn in SVG — honest representation, not a screenshot */
function DashboardSchematic() {
  return (
    <svg
      viewBox="0 0 720 440"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={styles.schematic}
      role="img"
      aria-label="Schematic preview of the SHM-AI engineering workspace dashboard"
    >
      {/* Outer frame */}
      <rect width="720" height="440" rx="6" fill="#2C2530"/>
      {/* Nav bar */}
      <rect width="720" height="48" rx="0" fill="#403640"/>
      <rect x="16" y="14" width="80" height="20" rx="3" fill="rgba(182,189,168,0.3)"/>
      <circle cx="124" cy="24" r="5" fill="rgba(182,189,168,0.15)"/>
      <rect x="136" y="18" width="48" height="12" rx="2" fill="rgba(182,189,168,0.12)"/>
      <rect x="194" y="18" width="52" height="12" rx="2" fill="rgba(216,198,90,0.18)"/>
      <circle cx="698" cy="24" r="5" fill="rgba(90,158,110,0.6)"/>

      {/* Status bar */}
      <rect y="48" width="720" height="24" fill="#F3EFE7" fillOpacity="0.04"/>
      <rect x="16" y="56" width="60" height="8" rx="2" fill="rgba(182,189,168,0.3)"/>
      <rect x="88" y="56" width="1" height="8" fill="rgba(182,189,168,0.15)"/>
      <rect x="96" y="56" width="44" height="8" rx="2" fill="rgba(182,189,168,0.15)"/>
      <rect x="152" y="56" width="1" height="8" fill="rgba(182,189,168,0.15)"/>
      <rect x="160" y="56" width="60" height="8" rx="2" fill="rgba(182,189,168,0.15)"/>

      {/* Page header */}
      <rect y="72" width="720" height="56" fill="#F3EFE7" fillOpacity="0.03"/>
      <rect x="24" y="86" width="160" height="20" rx="2" fill="rgba(182,189,168,0.2)"/>
      <rect x="24" y="112" width="240" height="10" rx="2" fill="rgba(133,134,110,0.25)"/>
      {/* Gradient rule */}
      <rect y="126" width="280" height="2" fill="url(#heroGrad)" opacity="0.5"/>
      <defs>
        <linearGradient id="heroGrad" x1="0" y1="0" x2="280" y2="0">
          <stop offset="0%" stopColor="#D8C65A"/>
          <stop offset="40%" stopColor="#B6BDA8"/>
          <stop offset="100%" stopColor="transparent"/>
        </linearGradient>
      </defs>

      {/* Metrics strip — 4 cards */}
      {[0,1,2,3].map((i) => {
        const colors = ['#B6BDA8','#C0A9C5','#D8C65A','#85866E']
        const values = ['12','47','78.4','3']
        const labels = ['Assets','Inspections','Avg Score','Pending']
        return (
          <g key={i}>
            <rect x={24 + i * 172} y={142} width={158} height={72} rx="3"
              fill="#FAFAF8" fillOpacity="0.06" stroke="rgba(243,239,231,0.07)" strokeWidth="1"/>
            <rect x={24 + i * 172} y={142} width={3} height={72} rx="1" fill={colors[i]}/>
            <text x={36 + i * 172} y={164} fontSize="8" fill="rgba(133,134,110,0.7)"
              fontFamily="Inter,sans-serif" letterSpacing="0.06em" textDecoration="none">
              {labels[i].toUpperCase()}
            </text>
            <text x={36 + i * 172} y={195} fontSize="22" fill="rgba(182,189,168,0.8)"
              fontFamily="DM Serif Display, Georgia, serif">
              {values[i]}
            </text>
          </g>
        )
      })}

      {/* Inspections table */}
      <rect x="24" y="234" width="450" height="170" rx="3"
        fill="#FAFAF8" fillOpacity="0.04" stroke="rgba(243,239,231,0.06)" strokeWidth="1"/>
      {/* Table header */}
      <rect x="24" y="234" width="450" height="24" rx="3" fill="rgba(182,189,168,0.05)"/>
      {['Asset','Type','Status','Defects','Score','Date'].map((h, i) => (
        <text key={h} x={36 + i * 72} y={250} fontSize="7.5" fill="rgba(133,134,110,0.6)"
          fontFamily="Inter,sans-serif" letterSpacing="0.06em">{h.toUpperCase()}</text>
      ))}
      {/* Table rows */}
      {[0,1,2,3,4,5].map((i) => {
        const statusColors = ['#3D6B4A','#8A6020','#3D6B4A','#8B3030','#3D6B4A','#445E6E']
        return (
          <g key={i}>
            <rect x="24" y={258 + i * 22} width="450" height="22"
              fill={i % 2 === 0 ? 'rgba(182,189,168,0.02)' : 'transparent'}/>
            <line x1="24" y1={258 + i * 22} x2="474" y2={258 + i * 22}
              stroke="rgba(243,239,231,0.04)" strokeWidth="1"/>
            <rect x={36} y={265 + i * 22} width={60} height={8} rx="2" fill="rgba(182,189,168,0.2)"/>
            <rect x={108} y={266 + i * 22} width={36} height={6} rx="1" fill="rgba(133,134,110,0.2)"/>
            <rect x={180} y={264 + i * 22} width={42} height={10} rx="1"
              fill={`${statusColors[i]}22`} stroke={`${statusColors[i]}44`} strokeWidth="1"/>
            <rect x={270} y={266 + i * 22} width={16} height={6} rx="2" fill="rgba(138,96,32,0.25)"/>
            <rect x={342} y={266 + i * 22} width={24} height={6} rx="2" fill={`${statusColors[i]}40`}/>
            <rect x={414} y={266 + i * 22} width={44} height={6} rx="2" fill="rgba(133,134,110,0.15)"/>
          </g>
        )
      })}

      {/* Asset type chart */}
      <rect x="494" y="234" width="202" height="170" rx="3"
        fill="#FAFAF8" fillOpacity="0.04" stroke="rgba(243,239,231,0.06)" strokeWidth="1"/>
      {/* Bar chart */}
      {[['Bridge',0.8,'#B6BDA8'],['Building',0.55,'#C0A9C5'],['Tunnel',0.35,'#D8C65A'],['Road',0.22,'#85866E'],['Other',0.1,'#A77976']].map(([label, pct, color], i) => (
        <g key={label as string}>
          <text x={506} y={265 + i * 26} fontSize="8" fill="rgba(182,189,168,0.5)" fontFamily="Inter,sans-serif">{label}</text>
          <rect x={550} y={258 + i * 26} width={Math.round(120 * (pct as number))} height={12} rx="2" fill={color as string} opacity="0.55"/>
        </g>
      ))}

      {/* Bottom row: status bar + quick actions */}
      <rect x="24" y="424" width="690" height="4" rx="2" fill="rgba(133,134,110,0.1)"/>

      {/* Label */}
      <text x="360" y="434" textAnchor="middle"
        fill="rgba(182,189,168,0.2)" fontSize="8" fontFamily="ui-monospace,monospace">
        SHM-AI Engineering Workspace — Dashboard Preview
      </text>
    </svg>
  )
}

export default function ProductPreview() {
  return (
    <section className={styles.section} aria-labelledby="preview-heading">
      <div className={styles.inner}>
        <div className={styles.label} id="preview-heading">
          <span className={styles.labelDot} aria-hidden="true" />
          Engineering Workspace Preview
        </div>

        <h2 className={styles.title}>
          A purposeful engineering workspace,<br />not a generic dashboard.
        </h2>

        {/* Dashboard schematic */}
        <div className={styles.frameOuter}>
          <div className={styles.frameBar} aria-hidden="true">
            <span className={styles.frameDot} style={{ background: '#A77976' }} />
            <span className={styles.frameDot} style={{ background: '#D8C65A' }} />
            <span className={styles.frameDot} style={{ background: '#B6BDA8' }} />
            <span className={styles.frameUrl}>shm-ai / dashboard</span>
          </div>
          <DashboardSchematic />
        </div>

        <div className={styles.cta}>
          <Link to="/dashboard" className={styles.ctaLink}>
            Open the engineering workspace
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
          </Link>
        </div>
      </div>
    </section>
  )
}
