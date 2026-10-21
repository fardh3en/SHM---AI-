import { Link } from 'react-router-dom'
import { useState } from 'react'
import { Menu, X } from 'lucide-react'
import styles from './HomeNav.module.css'

const NAV_LINKS = [
  { href: '#capabilities', label: 'Capabilities' },
  { href: '#workflow', label: 'How It Works' },
  { href: '#preview', label: 'Platform' },
]

export default function HomeNav() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <header className={styles.header}>
      <nav className={styles.nav} aria-label="Site navigation">
        <div className={styles.inner}>
          {/* Brand */}
          <Link to="/" className={styles.brand} aria-label="SHM-AI Home">
            <svg width="26" height="26" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <rect width="32" height="32" rx="4" fill="#403640"/>
              <rect x="4" y="13" width="24" height="6" rx="1" fill="#B6BDA8"/>
              <rect x="6" y="10" width="20" height="3" rx="1" fill="#B6BDA8"/>
              <rect x="6" y="19" width="20" height="3" rx="1" fill="#B6BDA8"/>
              <path d="M14 10 L15.5 13 L14.5 16 L16 19" stroke="#D8C65A" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <span className={styles.brandName}>
              SHM<span className={styles.brandAccent}>-AI</span>
            </span>
          </Link>

          {/* Desktop links */}
          <ul className={styles.links} role="list">
            {NAV_LINKS.map(({ href, label }) => (
              <li key={href}>
                <a href={href} className={styles.link}>{label}</a>
              </li>
            ))}
          </ul>

          {/* CTA */}
          <div className={styles.right}>
            <Link to="/dashboard" className={styles.cta}>
              Open Dashboard
            </Link>
            {/* Mobile toggle */}
            <button
              className={styles.mobileToggle}
              onClick={() => setMobileOpen((v) => !v)}
              aria-expanded={mobileOpen}
              aria-label={mobileOpen ? 'Close menu' : 'Open menu'}
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className={styles.mobileMenu} role="dialog" aria-label="Mobile navigation">
            <ul role="list">
              {NAV_LINKS.map(({ href, label }) => (
                <li key={href}>
                  <a
                    href={href}
                    className={styles.mobileLink}
                    onClick={() => setMobileOpen(false)}
                  >
                    {label}
                  </a>
                </li>
              ))}
              <li>
                <Link
                  to="/dashboard"
                  className={styles.mobileCta}
                  onClick={() => setMobileOpen(false)}
                >
                  Open Dashboard
                </Link>
              </li>
            </ul>
          </div>
        )}
      </nav>
    </header>
  )
}
