import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, Layers, ClipboardList, ScanLine, Box, FileText, Info } from 'lucide-react'
import { useSystemHealth } from '../../hooks/useSystemHealth'
import styles from './AppNavBar.module.css'

interface NavLinkItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  comingSoon?: boolean
}

const NAV_LINKS: NavLinkItem[] = [
  { to: '/dashboard',         label: 'Dashboard',  icon: LayoutDashboard },
  { to: '/assets',            label: 'Assets',     icon: Layers },
  { to: '/inspections',       label: 'Inspections',icon: ClipboardList },
  { to: '/vision',            label: 'Vision',     icon: ScanLine },
  { to: '/structural-health', label: '3D Health',  icon: Box },
  { to: '/reports',           label: 'Reports',    icon: FileText },
]

export default function AppNavBar() {
  const location = useLocation()
  const { data: health, isError } = useSystemHealth()

  const statusLabel = isError
    ? 'Offline'
    : health?.status === 'healthy'
    ? 'Online'
    : 'Connecting'

  const statusClass = isError
    ? styles.statusOffline
    : health?.status === 'healthy'
    ? styles.statusOnline
    : styles.statusConnecting

  return (
    <nav className={styles.nav} aria-label="Application navigation">
      <div className={styles.inner}>
        {/* Brand */}
        <Link to="/dashboard" className={styles.brand} aria-label="SHM-AI Platform home">
          <svg width="24" height="24" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <rect width="32" height="32" rx="4" fill="#B6BDA8" fillOpacity="0.15"/>
            <rect x="4" y="13" width="24" height="6" rx="1" fill="#B6BDA8"/>
            <rect x="6" y="10" width="20" height="3" rx="1" fill="#B6BDA8"/>
            <rect x="6" y="19" width="20" height="3" rx="1" fill="#B6BDA8"/>
            <path d="M14 10 L15.5 13 L14.5 16 L16 19" stroke="#D8C65A" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <span className={styles.brandName}>SHM<span className={styles.brandAccent}>-AI</span></span>
        </Link>

        {/* Nav links */}
        <ul className={styles.links} role="list">
          {NAV_LINKS.map(({ to, label, icon: Icon, comingSoon }) => {
            const isActive = location.pathname === to
            return (
              <li key={to}>
                <Link
                  to={to}
                  className={[styles.link, isActive ? styles.active : ''].join(' ')}
                  aria-current={isActive ? 'page' : undefined}
                  aria-disabled={comingSoon}
                  onClick={comingSoon ? (e) => e.preventDefault() : undefined}
                  title={comingSoon ? `${label} — coming in next phase` : label}
                >
                  <Icon size={15} strokeWidth={1.75} />
                  <span>{label}</span>
                  {comingSoon && (
                    <span className={styles.soon} aria-label="Coming soon">·</span>
                  )}
                </Link>
              </li>
            )
          })}
        </ul>

        {/* Right side: system status + info */}
        <div className={styles.right}>
          <span className={[styles.status, statusClass].join(' ')} role="status">
            <span className={styles.statusDot} aria-hidden="true" />
            <span className={styles.statusLabel}>
              {statusLabel}
              {health?.version && <span className={styles.statusVersion}> v{health.version}</span>}
            </span>
          </span>
          <Link to="/" className={styles.homeLink} title="Homepage">
            <Info size={15} strokeWidth={1.75} />
          </Link>
        </div>
      </div>
    </nav>
  )
}
