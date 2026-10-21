import { Link } from 'react-router-dom'
import styles from './HomeFooter.module.css'

export default function HomeFooter() {
  const year = new Date().getFullYear()

  return (
    <footer className={styles.footer} role="contentinfo">
      <div className={styles.inner}>
        {/* Brand column */}
        <div className={styles.brand}>
          <div className={styles.brandRow}>
            <svg width="22" height="22" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <rect width="32" height="32" rx="4" fill="rgba(182,189,168,0.15)"/>
              <rect x="4" y="13" width="24" height="6" rx="1" fill="#B6BDA8"/>
              <rect x="6" y="10" width="20" height="3" rx="1" fill="#B6BDA8"/>
              <rect x="6" y="19" width="20" height="3" rx="1" fill="#B6BDA8"/>
              <path d="M14 10 L15.5 13 L14.5 16 L16 19" stroke="#D8C65A" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <span className={styles.brandName}>SHM-AI</span>
          </div>
          <p className={styles.brandDescription}>
            AI-Directed Predictive Maintenance &amp; Structural Health Monitoring.
            A modular engineering intelligence platform.
          </p>
        </div>

        {/* Platform links */}
        <div className={styles.linksGroup}>
          <h3 className={styles.groupTitle}>Platform</h3>
          <ul role="list">
            <li><Link to="/dashboard" className={styles.footerLink}>Engineering Dashboard</Link></li>
            <li><Link to="/" className={styles.footerLink}>About SHM-AI</Link></li>
          </ul>
        </div>
      </div>

      <div className={styles.bottom}>
        <span className={styles.copy}>© {year} SHM-AI Platform.</span>
        <span className={styles.tech}>
          React · TypeScript · FastAPI · SQLAlchemy · PyTorch · YOLO11
        </span>
      </div>
    </footer>
  )
}
