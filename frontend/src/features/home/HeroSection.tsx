import { Link } from 'react-router-dom'
import XRayBuildingViewer from './XRayBuildingViewer'
import styles from './HeroSection.module.css'

export default function HeroSection() {
  return (
    <section className={styles.hero} aria-label="SHM-AI platform introduction">
      {/* Left column — typography & actions */}
      <div className={styles.left}>
        <div className={styles.eyebrow}>
          <span className={styles.eyebrowDot} aria-hidden="true" />
          Structural Health Monitoring &amp; AI
        </div>

        <h1 className={styles.heading}>
          See the damage.{' '}
          <span className={styles.headingAccent}>Understand the structure.</span>
        </h1>

        <p className={styles.subheading}>
          AI-assisted structural inspections that turn photographic evidence into
          localized defect detections and traceable inspection records.
        </p>

        <div className={styles.actions}>
          <Link to="/dashboard" className={styles.ctaPrimary}>
            Open Dashboard
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </Link>

          <a href="#workflow" className={styles.ctaSecondary}>
            Explore the Platform
          </a>
        </div>
      </div>

      {/* Right column — Interactive 3D X-Ray Building Digital Twin */}
      <div
        className={styles.right}
        role="region"
        aria-label="Interactive 3D X-Ray Building Digital Twin"
      >
        <XRayBuildingViewer />
      </div>
    </section>
  )
}
