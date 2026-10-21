import { Info } from 'lucide-react'
import styles from './StatusLegend.module.css'

export default function StatusLegend() {
  return (
    <div className={styles.legendCard} role="region" aria-label="3D Component Status Legend">
      <div className={styles.header}>
        <h4 className={styles.title}>
          <Info size={14} color="#D8C65A" />
          <span>Structural Health Telemetry Legend</span>
        </h4>
        <span className={styles.badgeIllustrative}>ISO 16587 / AASHTO Standard Mapping</span>
      </div>

      <div className={styles.itemsGrid}>
        <div className={styles.item}>
          <div className={`${styles.swatch} ${styles.swatchFinding}`} />
          <div className={styles.itemContent}>
            <span className={styles.itemLabel}>Assessed — Findings Reported</span>
            <span className={styles.itemDescription}>
              Verified anomalies detected in computer vision inspection records.
            </span>
          </div>
        </div>

        <div className={styles.item}>
          <div className={`${styles.swatch} ${styles.swatchNominal}`} />
          <div className={styles.itemContent}>
            <span className={styles.itemLabel}>Assessed — Nominal Condition</span>
            <span className={styles.itemDescription}>
              Inspected structural members with zero detected defects in recent logs.
            </span>
          </div>
        </div>

        <div className={styles.item}>
          <div className={`${styles.swatch} ${styles.swatchNotAssessed}`} />
          <div className={styles.itemContent}>
            <span className={styles.itemLabel}>Not Assessed</span>
            <span className={styles.itemDescription}>
              No inspection telemetry or imagery currently logged for this member.
            </span>
          </div>
        </div>

        <div className={styles.item}>
          <div className={`${styles.swatch} ${styles.swatchIllustrative}`} />
          <div className={styles.itemContent}>
            <span className={styles.itemLabel}>Illustrative Reference</span>
            <span className={styles.itemDescription}>
              Secondary framing, expansion joints, or baseline geometry.
            </span>
          </div>
        </div>
      </div>

      <div className={styles.disclaimerBox}>
        <strong>Engineering Disclaimer:</strong> 3D models are representative parametric
        typologies generated from registry specifications. Defect highlights correspond to localized
        inspection findings. An unassessed state indicates an absence of inspection records, not
        certified structural integrity.
      </div>
    </div>
  )
}
