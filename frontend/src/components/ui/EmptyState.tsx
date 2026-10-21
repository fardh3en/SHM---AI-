import { Inbox } from 'lucide-react'
import Button from './Button'
import styles from './EmptyState.module.css'

interface EmptyStateProps {
  title?: string
  description?: string
  action?: { label: string; onClick: () => void }
}

export default function EmptyState({
  title = 'No records found',
  description = 'There is nothing here yet. Records will appear once data is available.',
  action,
}: EmptyStateProps) {
  return (
    <div className={styles.container}>
      <div className={styles.iconWrap} aria-hidden="true">
        <Inbox size={36} strokeWidth={1} />
      </div>
      <h3 className={styles.title}>{title}</h3>
      <p className={styles.description}>{description}</p>
      {action && (
        <Button variant="secondary" size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  )
}
