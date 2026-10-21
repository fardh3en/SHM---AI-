import styles from './LoadingState.module.css'

interface LoadingStateProps {
  rows?: number
  columns?: number
}

export default function LoadingState({ rows = 5, columns = 4 }: LoadingStateProps) {
  return (
    <div className={styles.container} role="status" aria-label="Loading…">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={styles.row}>
          {Array.from({ length: columns }).map((_, j) => (
            <span
              key={j}
              className={['skeleton', styles.cell].join(' ')}
              style={{ width: `${60 + (j * 17 + i * 11) % 35}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
