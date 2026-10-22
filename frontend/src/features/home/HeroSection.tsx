import { Link } from 'react-router-dom'
import XRayBuildingViewer from './XRayBuildingViewer'
import styles from './HeroSection.module.css'

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

      {/* Right column — 3D Interactive X-Ray Building Digital Twin */}
      <div className={styles.right} role="region" aria-label="Interactive 3D X-Ray Building Digital Twin">
        <XRayBuildingViewer />
      </div>
    </section>
  )
}
