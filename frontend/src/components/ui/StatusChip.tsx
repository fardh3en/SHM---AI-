import type { InspectionStatus } from '../../api/inspections'
import type { AssetStatus } from '../../api/assets'
import styles from './StatusChip.module.css'

type Status = InspectionStatus | AssetStatus | 'healthy' | 'unknown'

const STATUS_CONFIG: Record<
  Status,
  { label: string; className: string }
> = {
  // Inspection statuses
  pending:    { label: 'Pending',    className: 'neutral'  },
  processing: { label: 'Processing', className: 'info'     },
  completed:  { label: 'Completed',  className: 'good'     },
  failed:     { label: 'Failed',     className: 'critical' },
  // Asset statuses
  active:             { label: 'Active',           className: 'good'    },
  inactive:           { label: 'Inactive',         className: 'neutral' },
  under_maintenance:  { label: 'In Maintenance',   className: 'warn'    },
  decommissioned:     { label: 'Decommissioned',   className: 'neutral' },
  // System
  healthy: { label: 'Healthy', className: 'good'    },
  unknown: { label: 'Unknown', className: 'neutral' },
}

interface StatusChipProps {
  status: Status
  size?: 'sm' | 'md'
}

export default function StatusChip({ status, size = 'md' }: StatusChipProps) {
  const config = STATUS_CONFIG[status] ?? { label: status, className: 'neutral' }
  return (
    <span
      className={[styles.chip, styles[config.className], styles[size]].join(' ')}
      role="status"
      aria-label={config.label}
    >
      <span className={styles.dot} aria-hidden="true" />
      {config.label}
    </span>
  )
}
