import { AlertCircle, RefreshCw } from 'lucide-react'
import Button from './Button'
import styles from './ErrorState.module.css'

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
}

export default function ErrorState({
  message = 'Unable to load data. Check that the backend is running.',
  onRetry,
}: ErrorStateProps) {
  return (
    <div className={styles.container} role="alert">
      <AlertCircle size={32} strokeWidth={1.5} className={styles.icon} />
      <p className={styles.message}>{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw size={14} />
          Retry
        </Button>
      )}
    </div>
  )
}
