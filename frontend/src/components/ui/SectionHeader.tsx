import styles from './SectionHeader.module.css'

interface SectionHeaderProps {
  title: string
  description?: string
  action?: React.ReactNode
  ruled?: boolean
}

export default function SectionHeader({
  title,
  description,
  action,
  ruled = true,
}: SectionHeaderProps) {
  return (
    <div className={styles.header}>
      <div className={styles.text}>
        <h2 className={styles.title}>{title}</h2>
        {description && <p className={styles.description}>{description}</p>}
      </div>
      {action && <div className={styles.action}>{action}</div>}
      {ruled && <hr className={styles.rule} aria-hidden="true" />}
    </div>
  )
}
