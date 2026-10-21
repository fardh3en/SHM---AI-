import { Link } from 'react-router-dom'
import {
  Layers,
  ClipboardList,
  Box,
  ScanLine,
  FileText,
  ArrowRight,
  type LucideIcon,
} from 'lucide-react'
import styles from './QuickActionsPanel.module.css'

interface ActionItem {
  icon: LucideIcon
  label: string
  description: string
  href: string
  available: boolean
}

const ACTIONS: ActionItem[] = [
  {
    icon: Layers,
    label: 'Asset Registry',
    description: 'Register and manage monitored structures.',
    href: '/assets',
    available: true,
  },
  {
    icon: ClipboardList,
    label: 'Run Inspection',
    description: 'Submit images to the vision pipeline.',
    href: '/inspections',
    available: true,
  },
  {
    icon: Box,
    label: '3D Structural Health',
    description: 'Interactive spatial twin and condition telemetry.',
    href: '/structural-health',
    available: true,
  },
  {
    icon: ScanLine,
    label: 'Vision Analysis',
    description: 'Review crack detections and measurements.',
    href: '/vision',
    available: true,
  },
  {
    icon: FileText,
    label: 'Reports',
    description: 'Generate and export engineering reports.',
    href: '/reports',
    available: true,
  },
]

export default function QuickActionsPanel() {
  return (
    <ul className={styles.list} role="list" aria-label="Application modules">
      {ACTIONS.map(({ icon: Icon, label, description, href, available }) => (
        <li key={href}>
          {available ? (
            <Link to={href} className={styles.item}>
              <span className={styles.iconWrap}>
                <Icon size={16} strokeWidth={1.75} />
              </span>
              <span className={styles.text}>
                <span className={styles.label}>{label}</span>
                <span className={styles.description}>{description}</span>
              </span>
              <ArrowRight size={14} className={styles.arrow} />
            </Link>
          ) : (
            <div className={styles.item} aria-disabled="true">
              <span className={styles.iconWrap}>
                <Icon size={16} strokeWidth={1.75} />
              </span>
              <span className={styles.text}>
                <span className={styles.label}>{label}</span>
                <span className={styles.description}>{description}</span>
              </span>
              <span className={styles.soon}>Next phase</span>
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}
