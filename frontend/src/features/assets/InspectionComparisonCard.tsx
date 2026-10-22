import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { Inspection } from '../../api/inspections'
import { inspectionsApi } from '../../api/inspections'
import {
  ArrowRight,
  TrendingDown,
  TrendingUp,
  Minus,
  AlertTriangle,
  Layers,
  ShieldAlert,
  Info,
} from 'lucide-react'
import styles from './InspectionComparisonCard.module.css'

interface InspectionComparisonCardProps {
  assetId: string
  inspections: Inspection[]
}

function formatDateShort(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export default function InspectionComparisonCard({
  assetId,
  inspections,
}: InspectionComparisonCardProps) {
  // Sort inspections chronologically ascending
  const chronological = useMemo(() => {
    return [...inspections].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    )
  }, [inspections])

  // Default base to penultimate, target to latest
  const defaultBaseId = chronological.length >= 2 ? chronological[chronological.length - 2].id : ''
  const defaultTargetId = chronological.length >= 1 ? chronological[chronological.length - 1].id : ''

  const [baseId, setBaseId] = useState<string>(defaultBaseId)
  const [targetId, setTargetId] = useState<string>(defaultTargetId)

  // Sync if selections become empty or invalid
  const effectiveBaseId = baseId || defaultBaseId
  const effectiveTargetId = targetId || defaultTargetId

  const {
    data: comparison,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['inspection-comparison', assetId, effectiveBaseId, effectiveTargetId],
    queryFn: () => inspectionsApi.compareInspections(assetId, effectiveBaseId, effectiveTargetId),
    enabled: Boolean(assetId && effectiveBaseId && effectiveTargetId && effectiveBaseId !== effectiveTargetId),
    staleTime: 30_000,
  })

  if (inspections.length < 2) {
    return (
      <div className={styles.comparisonContainer} role="region" aria-label="Inspection Comparison">
        <div className={styles.headerRow}>
          <div className={styles.titleGroup}>
            <Layers size={18} color="var(--color-mineral)" />
            <h3 className={styles.title}>Comparative Structural Change Tracking</h3>
          </div>
        </div>
        <div className={styles.emptyNotice}>
          <Info size={16} style={{ margin: '0 auto 6px', display: 'block', color: 'var(--text-dim)' }} />
          <span>
            Comparative change tracking requires at least two inspection events for this asset. Only {inspections.length} inspection event recorded to date.
          </span>
        </div>
      </div>
    )
  }

  return (
    <section className={styles.comparisonContainer} aria-labelledby="comparison-title">
      <div className={styles.headerRow}>
        <div className={styles.titleGroup}>
          <Layers size={18} color="var(--color-mineral)" />
          <div>
            <h3 id="comparison-title" className={styles.title}>
              Comparative Structural Change Tracking
            </h3>
            <span className={styles.subtitle}>
              Deterministic defect class evolution, condition delta, and engineering comparability disclosures.
            </span>
          </div>
        </div>
      </div>

      {/* Selectors Bar */}
      <div className={styles.selectorsBar}>
        <div className={styles.selectGroup}>
          <label htmlFor="base-inspection-select" className={styles.selectLabel}>
            Base Event (Baseline)
          </label>
          <select
            id="base-inspection-select"
            className={styles.selectInput}
            value={effectiveBaseId}
            onChange={(e) => setBaseId(e.target.value)}
          >
            {chronological.map((insp) => (
              <option key={insp.id} value={insp.id}>
                {formatDateShort(insp.created_at)} — {insp.defect_count} defects ({insp.health_score !== null ? `${insp.health_score.toFixed(1)}/100` : 'Not Assessed'})
              </option>
            ))}
          </select>
        </div>

        <div className={styles.arrowDivider}>
          <ArrowRight size={18} />
        </div>

        <div className={styles.selectGroup}>
          <label htmlFor="target-inspection-select" className={styles.selectLabel}>
            Target Event (Subsequent)
          </label>
          <select
            id="target-inspection-select"
            className={styles.selectInput}
            value={effectiveTargetId}
            onChange={(e) => setTargetId(e.target.value)}
          >
            {chronological.map((insp) => (
              <option key={insp.id} value={insp.id}>
                {formatDateShort(insp.created_at)} — {insp.defect_count} defects ({insp.health_score !== null ? `${insp.health_score.toFixed(1)}/100` : 'Not Assessed'})
              </option>
            ))}
          </select>
        </div>
      </div>

      {effectiveBaseId === effectiveTargetId && (
        <div className={styles.emptyNotice}>
          Please select two distinct inspection events to compute structural change tracking.
        </div>
      )}

      {isLoading && (
        <div className={styles.emptyNotice}>
          Computing differential condition metrics and defect class evolution...
        </div>
      )}

      {isError && (
        <div className={styles.emptyNotice} style={{ color: 'var(--status-critical)' }}>
          Failed to compute comparative metrics: {(error as Error)?.message || 'Comparison request failed.'}
        </div>
      )}

      {comparison && (
        <>
          {/* Key Metric Strip */}
          <div className={styles.metricsGrid}>
            {/* Health Score Delta */}
            <div className={styles.metricCard}>
              <span className={styles.metricLabel}>Health Score Delta</span>
              <div
                className={[
                  styles.metricValue,
                  comparison.health_score_delta !== null
                    ? comparison.health_score_delta > 0
                      ? styles.deltaImproved
                      : comparison.health_score_delta < 0
                      ? styles.deltaDegraded
                      : styles.deltaNeutral
                    : styles.deltaNeutral,
                ].join(' ')}
              >
                {comparison.health_score_delta !== null ? (
                  <>
                    {comparison.health_score_delta > 0 && <TrendingUp size={18} />}
                    {comparison.health_score_delta < 0 && <TrendingDown size={18} />}
                    {comparison.health_score_delta === 0 && <Minus size={18} />}
                    <span>
                      {comparison.health_score_delta > 0 ? '+' : ''}
                      {comparison.health_score_delta.toFixed(1)} pts
                    </span>
                  </>
                ) : (
                  <span>N/A</span>
                )}
              </div>
              <span className={styles.metricSubtext}>
                {comparison.base_inspection.health_score !== null && comparison.target_inspection.health_score !== null
                  ? `${comparison.base_inspection.health_score.toFixed(1)} → ${comparison.target_inspection.health_score.toFixed(1)}`
                  : 'Requires assessed scores in both events'}
              </span>
            </div>

            {/* Defect Count Delta */}
            <div className={styles.metricCard}>
              <span className={styles.metricLabel}>Defect Count Delta</span>
              <div
                className={[
                  styles.metricValue,
                  comparison.defect_count_delta > 0
                    ? styles.deltaDegraded
                    : comparison.defect_count_delta < 0
                    ? styles.deltaImproved
                    : styles.deltaNeutral,
                ].join(' ')}
              >
                {comparison.defect_count_delta > 0 ? '+' : ''}
                {comparison.defect_count_delta}
              </div>
              <span className={styles.metricSubtext}>
                {comparison.base_inspection.defect_count} base → {comparison.target_inspection.defect_count} target
              </span>
            </div>

            {/* Pixel Area Delta */}
            <div className={styles.metricCard}>
              <span className={styles.metricLabel}>Defect Pixel Area Delta</span>
              <div className={styles.metricValue}>
                {comparison.total_pixel_area_delta !== null
                  ? `${comparison.total_pixel_area_delta > 0 ? '+' : ''}${comparison.total_pixel_area_delta.toLocaleString()} px²`
                  : '—'}
              </div>
              <span className={styles.metricSubtext}>
                Pixel space bounding geometry delta
              </span>
            </div>
          </div>

          {/* Change Summary */}
          <div className={styles.summaryText}>
            <strong>Engineering Change Summary:</strong> {comparison.change_summary}
          </div>

          {/* Defect Class Evolution Badges */}
          <div className={styles.classesSection}>
            <span className={styles.sectionHeading}>Defect Class Transitions</span>
            <div className={styles.badgeGrid}>
              {comparison.common_defect_classes.map((cls) => (
                <span key={cls} className={`${styles.badge} ${styles.badgeCommon}`}>
                  Common: {cls}
                </span>
              ))}

              {comparison.new_defect_classes.map((cls) => (
                <span key={cls} className={`${styles.badge} ${styles.badgeNew}`}>
                  <AlertTriangle size={11} />
                  Newly Detected: {cls}
                </span>
              ))}

              {comparison.absent_defect_classes.map((cls) => (
                <span key={cls} className={`${styles.badge} ${styles.badgeAbsent}`}>
                  Absent in Target: {cls}
                </span>
              ))}

              {comparison.common_defect_classes.length === 0 &&
                comparison.new_defect_classes.length === 0 &&
                comparison.absent_defect_classes.length === 0 && (
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-dim)' }}>
                    No defect classifications recorded in either inspection event.
                  </span>
                )}
            </div>
          </div>

          {/* Traceable Engineering Disclosures */}
          <div className={styles.disclosuresCard}>
            <div className={styles.disclosuresTitle}>
              <ShieldAlert size={14} />
              <span>Mandatory Engineering Comparability Disclosures</span>
            </div>
            <ul className={styles.disclosuresList}>
              {comparison.engineering_disclosures.map((disc, idx) => (
                <li key={idx} className={styles.disclosureItem}>
                  {disc}
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </section>
  )
}
