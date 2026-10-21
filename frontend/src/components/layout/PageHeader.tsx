import { Link } from 'react-router-dom'
import styles from './PageHeader.module.css'

interface PageHeaderProps {
  title: string
  description?: string
  breadcrumb?: Array<{ label: string; href?: string; to?: string }>
  action?: React.ReactNode
}

export default function PageHeader({ title, description, breadcrumb, action }: PageHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        {breadcrumb && breadcrumb.length > 0 && (
          <nav className={styles.breadcrumb} aria-label="Breadcrumb">
            {breadcrumb.map((crumb, i) => (
              <span key={i} className={styles.crumbItem}>
                {i > 0 && <span className={styles.crumbSep} aria-hidden="true">/</span>}
                {crumb.to ? (
                  <Link to={crumb.to} className={styles.crumbLink}>{crumb.label}</Link>
                ) : crumb.href ? (
                  <a href={crumb.href} className={styles.crumbLink}>{crumb.label}</a>
                ) : (
                  <span className={styles.crumbCurrent} aria-current="page">{crumb.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}
        <div className={styles.row}>
          <div className={styles.text}>
            <h1 className={styles.title}>{title}</h1>
            {description && <p className={styles.description}>{description}</p>}
          </div>
          {action && <div className={styles.action}>{action}</div>}
        </div>
      </div>
      <div className={styles.rule} aria-hidden="true" />
    </header>
  )
}
