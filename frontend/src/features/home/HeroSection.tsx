import { Link } from 'react-router-dom'
import styles from './HeroSection.module.css'

/** Inline SVG engineering diagram — structural cross-section with crack annotation */
function StructuralDiagram() {
  return (
    <svg
      viewBox="0 0 420 340"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={styles.diagram}
      role="img"
      aria-label="Structural engineering cross-section diagram with crack detection annotation"
    >
      {/* Background grid — subtle engineering paper feel */}
      <defs>
        <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(243,239,231,0.06)" strokeWidth="0.5"/>
        </pattern>
        <marker id="arrowRight" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M 0 0 L 6 3 L 0 6 Z" fill="rgba(243,239,231,0.5)"/>
        </marker>
        <marker id="arrowLeft" markerWidth="6" markerHeight="6" refX="1" refY="3" orient="auto">
          <path d="M 6 0 L 0 3 L 6 6 Z" fill="rgba(243,239,231,0.5)"/>
        </marker>
      </defs>
      <rect width="420" height="340" fill="url(#grid)"/>

      {/* Main structural beam — I-section profile */}
      {/* Top flange */}
      <rect x="60" y="90" width="300" height="32" rx="2" fill="rgba(182,189,168,0.25)" stroke="rgba(182,189,168,0.5)" strokeWidth="1.5"/>
      {/* Web */}
      <rect x="176" y="122" width="68" height="96" fill="rgba(182,189,168,0.18)" stroke="rgba(182,189,168,0.4)" strokeWidth="1.5"/>
      {/* Bottom flange */}
      <rect x="60" y="218" width="300" height="32" rx="2" fill="rgba(182,189,168,0.25)" stroke="rgba(182,189,168,0.5)" strokeWidth="1.5"/>

      {/* Crack — drawn as a jagged path on the top flange */}
      <path
        d="M 195 90 L 202 100 L 197 112 L 205 122"
        stroke="#D8C65A"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Crack extent annotation lines */}
      <line x1="180" y1="86" x2="180" y2="126" stroke="rgba(216,198,90,0.4)" strokeWidth="0.75" strokeDasharray="3,3"/>
      <line x1="215" y1="86" x2="215" y2="126" stroke="rgba(216,198,90,0.4)" strokeWidth="0.75" strokeDasharray="3,3"/>
      {/* Width arrow */}
      <line x1="180" y1="80" x2="215" y2="80"
        stroke="rgba(216,198,90,0.7)" strokeWidth="1"
        markerStart="url(#arrowLeft)" markerEnd="url(#arrowRight)"/>
      <text x="197" y="76" textAnchor="middle"
        fill="rgba(216,198,90,0.9)" fontSize="9" fontFamily="ui-monospace, monospace">
        1.4 mm
      </text>

      {/* Depth annotation */}
      <line x1="219" y1="90" x2="219" y2="122"
        stroke="rgba(216,198,90,0.7)" strokeWidth="1"
        markerStart="url(#arrowLeft)" markerEnd="url(#arrowRight)"/>
      <text x="238" y="110" textAnchor="start"
        fill="rgba(216,198,90,0.9)" fontSize="9" fontFamily="ui-monospace, monospace">
        32 mm
      </text>

      {/* Dimension lines — overall height */}
      <line x1="46" y1="90" x2="46" y2="250"
        stroke="rgba(243,239,231,0.3)" strokeWidth="0.75"
        markerStart="url(#arrowLeft)" markerEnd="url(#arrowRight)"/>
      <text x="34" y="172" textAnchor="middle" transform="rotate(-90, 34, 172)"
        fill="rgba(243,239,231,0.45)" fontSize="9" fontFamily="ui-monospace, monospace">
        420 mm
      </text>

      {/* Overall width */}
      <line x1="60" y1="274" x2="360" y2="274"
        stroke="rgba(243,239,231,0.3)" strokeWidth="0.75"
        markerStart="url(#arrowLeft)" markerEnd="url(#arrowRight)"/>
      <text x="210" y="286" textAnchor="middle"
        fill="rgba(243,239,231,0.45)" fontSize="9" fontFamily="ui-monospace, monospace">
        850 mm
      </text>

      {/* AI detection bounding box */}
      <rect x="185" y="84" width="36" height="44" rx="2"
        stroke="rgba(192,169,197,0.7)" strokeWidth="1.25" strokeDasharray="4,2"
        fill="rgba(192,169,197,0.06)"/>
      <text x="222" y="82" textAnchor="start"
        fill="rgba(192,169,197,0.85)" fontSize="8.5" fontFamily="ui-monospace, monospace">
        crack — 0.94
      </text>

      {/* Health score badge */}
      <rect x="300" y="94" width="70" height="44" rx="3"
        fill="rgba(64,54,64,0.7)" stroke="rgba(182,189,168,0.3)" strokeWidth="1"/>
      <text x="335" y="112" textAnchor="middle"
        fill="rgba(243,239,231,0.5)" fontSize="8" fontFamily="Inter, sans-serif" fontWeight="500"
        textDecoration="none" letterSpacing="0.05em">
        HEALTH
      </text>
      <text x="335" y="128" textAnchor="middle"
        fill="#D8C65A" fontSize="20" fontFamily="DM Serif Display, Georgia, serif">
        72
      </text>

      {/* Labels */}
      <text x="60" y="310" fill="rgba(243,239,231,0.3)" fontSize="8.5" fontFamily="ui-monospace, monospace">
        SHM-AI · Structural Assessment · Reinforced Concrete Section
      </text>

      {/* Corner tick marks — engineering drawing style */}
      {[[60,90],[360,90],[60,250],[360,250]].map(([x,y], i) => (
        <g key={i}>
          <line x1={x - 6} y1={y} x2={x + 6} y2={y} stroke="rgba(243,239,231,0.2)" strokeWidth="0.75"/>
          <line x1={x} y1={y - 6} x2={x} y2={y + 6} stroke="rgba(243,239,231,0.2)" strokeWidth="0.75"/>
        </g>
      ))}
    </svg>
  )
}

export default function HeroSection() {
  return (
    <section className={styles.hero} aria-label="SHM-AI platform introduction">
      {/* Left column — typography */}
      <div className={styles.left}>
        <div className={styles.eyebrow}>
          <span className={styles.eyebrowDot} aria-hidden="true" />
          Structural Health Monitoring &amp; AI
        </div>

        <h1 className={styles.heading}>
          Inspection evidence,{' '}
          <span className={styles.headingAccent}>turned into</span>{' '}
          engineering intelligence.
        </h1>

        <p className={styles.subheading}>
          SHM-AI combines computer vision, interactive 3D spatial twins, and
          structural health assessment to automate civil infrastructure inspection
          and generate evidence-based maintenance recommendations.
        </p>

        <div className={styles.actions}>
          <Link to="/dashboard" className={styles.ctaPrimary}>
            Open Dashboard
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
          </Link>
        </div>
      </div>

      {/* Right column — diagram */}
      <div className={styles.right} aria-hidden="true">
        <StructuralDiagram />
      </div>
    </section>
  )
}
