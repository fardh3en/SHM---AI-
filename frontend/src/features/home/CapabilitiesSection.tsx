import styles from './CapabilitiesSection.module.css'

interface Capability {
  title: string
  metric?: string
  metricLabel?: string
  description: string
}

/** Grounded in actual backend phases — no invented capabilities */
const CAPABILITIES: Capability[] = [
  {
    title: 'YOLO11 Crack Detection',
    metric: '640×640',
    metricLabel: 'slice resolution',
    description:
      'Sliced inference pipeline detects surface cracks in large-format structural images. Segmentation masks enable precise crack geometry extraction.',
  },
  {
    title: 'Geometric Measurement',
    metric: 'px → mm',
    metricLabel: 'calibrated output',
    description:
      'Crack width, length, and depth measured from detection masks. Topology graph analysis characterises branching and crack network complexity.',
  },
  {
    title: 'Structural Health Scoring',
    metric: '0–100',
    metricLabel: 'health index',
    description:
      'Engineering rules engine computes composite health scores from defect severity, density, and crack characteristics. Risk levels: Low, Moderate, High, Critical.',
  },
  {
    title: '3D Structural Health',
    metric: 'Spatial Twin',
    metricLabel: 'interactive telemetry',
    description:
      'Parametric 3D structural models map localized inspection findings, defect severity, and photographic evidence directly to individual structural members.',
  },
  {
    title: 'Maintenance Recommendations',
    metric: '4-tier',
    metricLabel: 'action escalation',
    description:
      'Decision engine maps structural health intelligence to Monitor, Inspect, Repair, or Emergency Intervention with a full audit trace.',
  },
  {
    title: 'Cost Estimation & Reports',
    metric: 'HTML/PDF',
    metricLabel: 'export formats',
    description:
      'Jinja2-templated engineering reports include defect inventory, health assessment, inspection imagery, and estimated intervention cost ranges.',
  },
]

export default function CapabilitiesSection() {
  return (
    <section className={styles.section} aria-labelledby="capabilities-heading">
      <div className={styles.inner}>

        {/* Left — editorial intro column */}
        <div className={styles.intro}>
          <h2 id="capabilities-heading" className={styles.title}>
            Deterministic engineering,<br />
            <em>not</em> black-box prediction.
          </h2>
          <p className={styles.description}>
            Every component is independently testable, strongly typed,
            and grounded in published structural engineering standards.
            No hallucinated sensor values. No invented accuracy claims.
          </p>
        </div>

        {/* Right — capability list */}
        <ul className={styles.list} role="list">
          {CAPABILITIES.map((cap) => (
            <li key={cap.title} className={styles.item}>
              <div className={styles.itemHeader}>
                <div className={styles.itemMeta}>
                  {cap.metric && (
                    <span className={styles.itemMetric}>
                      {cap.metric}
                      {cap.metricLabel && (
                        <span className={styles.itemMetricLabel}> / {cap.metricLabel}</span>
                      )}
                    </span>
                  )}
                </div>
                <h3 className={styles.itemTitle}>{cap.title}</h3>
              </div>
              <p className={styles.itemDescription}>{cap.description}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
