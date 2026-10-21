import { useInspections } from '../../hooks/useInspections'
import type { InspectionStatus } from '../../api/inspections'
import styles from './InspectionStatusBar.module.css'

const STATUS_CONFIG: Record<InspectionStatus, { label: string; className: string }> = {
  completed:  { label: 'Completed',  className: styles.completed  },
  pending:    { label: 'Pending',    className: styles.pending    },
  processing: { label: 'Processing', className: styles.processing },
  failed:     { label: 'Failed',     className: styles.failed     },
}

export default function InspectionStatusBar() {
  const { data, isLoading } = useInspections(1, 100)

  if (isLoading) {
    return (
      <div className={styles.container}>
        <div className={[styles.bar, 'skeleton'].join(' ')} style={{ height: 24 }} />
      </div>
    )
  }

  const items = data?.items ?? []
  const total = items.length

  if (total === 0) {
    return (
      <div className={styles.empty}>
        <span>No inspections recorded.</span>
      </div>
    )
  }

  const counts = items.reduce(
    (acc, i) => {
      acc[i.status] = (acc[i.status] ?? 0) + 1
      return acc
    },
    {} as Record<InspectionStatus, number>
  )

  const statusOrder: InspectionStatus[] = ['completed', 'pending', 'processing', 'failed']

  return (
    <div className={styles.container}>
      {/* Segmented bar */}
      <div className={styles.bar} role="img" aria-label="Inspection status distribution">
        {statusOrder.map((status) => {
          const count = counts[status] ?? 0
          if (count === 0) return null
          const pct = (count / total) * 100
          return (
            <div
              key={status}
              className={[styles.segment, STATUS_CONFIG[status].className].join(' ')}
              style={{ width: `${pct}%` }}
              title={`${STATUS_CONFIG[status].label}: ${count} (${pct.toFixed(0)}%)`}
            />
          )
        })}
      </div>

      {/* Legend */}
      <ul className={styles.legend} role="list">
        {statusOrder.map((status) => {
          const count = counts[status] ?? 0
          const pct = total > 0 ? ((count / total) * 100).toFixed(0) : '0'
          return (
            <li key={status} className={styles.legendItem}>
              <span className={[styles.legendDot, STATUS_CONFIG[status].className].join(' ')} aria-hidden="true" />
              <span className={styles.legendLabel}>{STATUS_CONFIG[status].label}</span>
              <span className={styles.legendCount}>{count}</span>
              <span className={styles.legendPct}>({pct}%)</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
