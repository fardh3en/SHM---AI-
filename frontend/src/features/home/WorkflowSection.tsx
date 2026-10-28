import styles from './WorkflowSection.module.css'

interface Step {
  number: string
  title: string
  description: string
  color: 'sage' | 'lilac' | 'mineral' | 'neutral'
}

const STEPS: Step[] = [
  {
    number: '01',
    title: 'Inspection',
    description: 'Image or video input from on-site inspection, drone survey, or camera feed.',
    color: 'neutral',
  },
  {
    number: '02',
    title: 'Detection',
    description: 'YOLO11 computer vision pipeline identifies and measures structural defects.',
    color: 'sage',
  },
  {
    number: '03',
    title: 'Health Assessment',
    description: 'Engineering rules engine computes health scores, severity, and risk levels.',
    color: 'sage',
  },
  {
    number: '04',
    title: 'Defect Mapping & Cataloging',
    description: 'Evidence ledger and localized defect mapping associate findings directly with asset components.',
    color: 'lilac',
  },
  {
    number: '05',
    title: 'Recommendation',
    description: 'Decision engine produces prioritised maintenance actions and cost estimates.',
    color: 'mineral',
  },
]

/** Small inline SVG icon per step */
function StepIcon({ step }: { step: Step }) {
  const icons: Record<string, React.ReactNode> = {
    '01': (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2"/>
        <path d="M3 9h18M9 21V9"/>
      </svg>
    ),
    '02': (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8"/>
        <path d="m21 21-4.35-4.35M11 8v6M8 11h6"/>
      </svg>
    ),
    '03': (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </svg>
    ),
    '04': (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    ),
    '05': (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/>
        <line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
    ),
  }
  return <>{icons[step.number]}</>
}

export default function WorkflowSection() {
  return (
    <section className={styles.section} aria-label="Analysis workflow">
      <div className={styles.inner}>
        <div className={styles.intro}>
          <h2 className={styles.title}>
            From raw inspection data<br />to actionable decisions.
          </h2>
          <p className={styles.description}>
            Five modular stages, each independently testable,{' '}
            deterministic, and grounded in structural engineering principles.
          </p>
        </div>

        <div className={styles.steps} role="list">
          {STEPS.map((step, i) => (
            <div key={step.number} className={styles.stepWrapper} role="listitem">
              {/* Connector line */}
              {i < STEPS.length - 1 && (
                <div className={styles.connector} aria-hidden="true" />
              )}

              <div className={[styles.step, styles[`step-${step.color}`]].join(' ')}>
                <div className={styles.stepHeader}>
                  <span className={styles.stepIcon}>
                    <StepIcon step={step} />
                  </span>
                  <span className={styles.stepNumber}>{step.number}</span>
                </div>
                <h3 className={styles.stepTitle}>{step.title}</h3>
                <p className={styles.stepDescription}>{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
