import { useSystemHealth, useSystemInfo } from '../../hooks/useSystemHealth'
import styles from './SystemStatusBar.module.css'

export default function SystemStatusBar() {
  const { data: health, isError, isLoading } = useSystemHealth()
  const { data: info } = useSystemInfo()

  const statusLabel = isError
    ? 'API Offline'
    : isLoading
    ? 'Connecting…'
    : health?.status === 'healthy'
    ? 'API Online'
    : 'Degraded'

  const statusClass = isError
    ? styles.offline
    : isLoading
    ? styles.connecting
    : styles.online

  return (
    <div className={[styles.bar, statusClass].join(' ')} role="status">
      <div className={styles.inner}>
        <div className={styles.group}>
          <span className={styles.dot} aria-hidden="true" />
          <span className={styles.label}>{statusLabel}</span>
        </div>

        {info && (
          <>
            <span className={styles.sep} aria-hidden="true" />
            <span className={styles.item}>
              <span className={styles.key}>Env</span>
              <span className={styles.val}>{info.environment}</span>
            </span>
            <span className={styles.sep} aria-hidden="true" />
            <span className={styles.item}>
              <span className={styles.key}>Version</span>
              <span className={styles.val}>v{info.version}</span>
            </span>
            <span className={styles.sep} aria-hidden="true" />
            <span className={styles.item}>
              <span className={styles.key}>Model</span>
              <span className={styles.val}>{info.default_model}</span>
            </span>
            <span className={styles.sep} aria-hidden="true" />
            <span className={styles.item}>
              <span className={styles.key}>Device</span>
              <span className={styles.val}>{info.inference_device}</span>
            </span>
          </>
        )}

        {health?.timestamp && (
          <>
            <span className={styles.sep} aria-hidden="true" />
            <span className={styles.item}>
              <span className={styles.key}>Last check</span>
              <span className={styles.val}>
                {new Date(health.timestamp).toLocaleTimeString()}
              </span>
            </span>
          </>
        )}
      </div>
    </div>
  )
}
