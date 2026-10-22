import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Asset } from '../../api/assets'
import type { Inspection } from '../../api/inspections'
import type { StructuralComponentData } from './models/types'
import { useAssetEvidence } from '../../hooks/useAssetEvidence'
import {
  X,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Camera,
  ExternalLink,
  Layers,
  ClipboardList,
} from 'lucide-react'
import styles from './ComponentDetailPanel.module.css'

interface ComponentDetailPanelProps {
  asset: Asset
  inspections?: Inspection[]
  component: StructuralComponentData | null
  onDeselect: () => void
}

export default function ComponentDetailPanel({
  asset,
  inspections = [],
  component,
  onDeselect,
}: ComponentDetailPanelProps) {
  const { data: evidenceItems = [] } = useAssetEvidence(asset.id)
  const [selectedPhoto, setSelectedPhoto] = useState<string | null>(null)

  const latestInspection = inspections[0]
  const hasDefects = Boolean(latestInspection && latestInspection.defect_count > 0)

  // Find evidence relevant to the selected component (if any) or asset evidence
  const relevantEvidence = component
    ? evidenceItems.filter((e) => {
        if (component.linkedEvidencePaths?.some((p) => e.file_path.includes(p.replace('/uploads/evidence/', '')))) {
          return true
        }
        if (e.component_description && component.name.toLowerCase().includes(e.component_description.toLowerCase())) {
          return true
        }
        return false
      })
    : []

  // Fallback to all asset evidence if no component-specific match
  const displayEvidence = relevantEvidence.length > 0 ? relevantEvidence : evidenceItems.slice(0, 4)

  if (!component) {
    return (
      <aside className={styles.panelContainer} aria-label="Asset Structural Overview">
        <div className={styles.overviewMode}>
          <div className={styles.assetSummaryHeader}>
            <span className={styles.componentId}>
              {asset.asset_type.toUpperCase()} • STRUCTURAL OVERVIEW
            </span>
            <h3 className={styles.assetTitle}>{asset.name}</h3>
            {asset.location && <span className={styles.assetLocation}>{asset.location}</span>}
          </div>

          {/* Asset-Level Findings & Telemetry Summary */}
          {latestInspection && (
            <div className={styles.specSection}>
              <h4 className={styles.sectionHeading}>
                <ClipboardList size={13} />
                <span>Asset Inspection Status</span>
              </h4>
              {hasDefects ? (
                <div className={styles.findingsCard}>
                  <h4 className={styles.findingsTitle}>
                    <AlertTriangle size={13} />
                    <span>
                      {latestInspection.defect_count} Defect(s) Logged on Asset
                    </span>
                  </h4>
                  <p className={styles.findingsText}>
                    {latestInspection.notes || 'Inspection detected anomalies requiring engineering review.'}
                  </p>
                </div>
              ) : (
                <div className={`${styles.statusBanner} ${styles.statusNominalBanner}`} role="status">
                  <CheckCircle2 size={15} />
                  <span>Latest Inspection: Nominal Condition (0 Defects)</span>
                </div>
              )}
            </div>
          )}

          <div className={styles.specSection}>
            <h4 className={styles.sectionHeading}>Asset Technical Profile</h4>
            <div className={styles.specGrid}>
              <div className={styles.specField}>
                <span className={styles.specLabel}>Primary Material</span>
                <span className={styles.specValue}>{asset.material || 'Engineered Composite'}</span>
              </div>
              <div className={styles.specField}>
                <span className={styles.specLabel}>Construction Year</span>
                <span className={styles.specValue}>{asset.construction_year || 'Historical'}</span>
              </div>
              <div className={styles.specField}>
                <span className={styles.specLabel}>Design Life</span>
                <span className={styles.specValue}>
                  {asset.design_life_years ? `${asset.design_life_years} Years` : 'Standard'}
                </span>
              </div>
              <div className={styles.specField}>
                <span className={styles.specLabel}>Operational Status</span>
                <span className={styles.specValue}>{asset.status.replace('_', ' ').toUpperCase()}</span>
              </div>
              <div className={`${styles.specField} ${styles.specRowFull}`}>
                <span className={styles.specLabel}>Structural Health Index</span>
                <span className={styles.specValue}>
                  {asset.latest_health_score !== null
                    ? `${asset.latest_health_score} / 100`
                    : 'Awaiting Initial Assessment'}
                </span>
              </div>
            </div>
          </div>

          {evidenceItems.length > 0 && (
            <div className={styles.evidenceSection}>
              <h4 className={styles.sectionHeading}>
                <Camera size={13} />
                <span>Field Evidence Archive ({evidenceItems.length})</span>
              </h4>
              <div className={styles.evidenceGrid}>
                {evidenceItems.slice(0, 4).map((item) => (
                  <div
                    key={item.id}
                    className={styles.evidenceThumbnailCard}
                    onClick={() => setSelectedPhoto(item.file_path)}
                    title={item.caption}
                  >
                    <img
                      src={item.file_path}
                      alt={item.caption}
                      className={styles.evidenceImg}
                      loading="lazy"
                    />
                    <div className={styles.evidenceOverlay}>{item.caption}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <Link
            to={`/inspections?assetId=${asset.id}`}
            className={styles.actionButton}
          >
            <span>Launch Inspection Studio</span>
            <ExternalLink size={13} />
          </Link>
        </div>
      </aside>
    )
  }

  return (
    <aside className={styles.panelContainer} aria-label={`Details for ${component.name}`}>
      {/* Header */}
      <div className={styles.panelHeader}>
        <div className={styles.headerTitleGroup}>
          <span className={styles.componentId}>{component.id}</span>
          <h3 className={styles.componentName}>{component.name}</h3>
        </div>
        <button
          type="button"
          className={styles.closeButton}
          onClick={onDeselect}
          title="Deselect member"
          aria-label="Close component details"
        >
          <X size={16} />
        </button>
      </div>

      <div className={styles.panelScrollContent}>
        {/* Status Indicator Banner */}
        {component.status === 'assessed_findings' && (
          <div className={`${styles.statusBanner} ${styles.statusFindingBanner}`} role="status">
            <AlertTriangle size={15} />
            <span>Active Structural Finding Reported ({component.findingsCount || 1} defect)</span>
          </div>
        )}
        {component.status === 'assessed_nominal' && (
          <div className={`${styles.statusBanner} ${styles.statusNominalBanner}`} role="status">
            <CheckCircle2 size={15} />
            <span>Assessed — Nominal Structural Condition</span>
          </div>
        )}
        {component.status === 'not_assessed' && (
          <div className={`${styles.statusBanner} ${styles.statusUnassessedBanner}`} role="status">
            <HelpCircle size={15} />
            <span>Not Assessed in Current Inspection Cycle</span>
          </div>
        )}
        {component.status === 'illustrative' && (
          <div className={`${styles.statusBanner} ${styles.statusIllustrativeBanner}`} role="status">
            <Layers size={15} />
            <span>Illustrative Framing Reference</span>
          </div>
        )}

        {/* Engineering Specifications */}
        <div className={styles.specSection}>
          <h4 className={styles.sectionHeading}>Engineering Specifications</h4>
          <div className={styles.specGrid}>
            <div className={styles.specField}>
              <span className={styles.specLabel}>Member Classification</span>
              <span className={styles.specValue}>{component.type.replace('_', ' ').toUpperCase()}</span>
            </div>
            <div className={styles.specField}>
              <span className={styles.specLabel}>Material Specification</span>
              <span className={styles.specValue}>{component.material}</span>
            </div>
            {component.dimensions && (
              <div className={`${styles.specField} ${styles.specRowFull}`}>
                <span className={styles.specLabel}>Physical Dimensions</span>
                <span className={styles.specValue}>{component.dimensions}</span>
              </div>
            )}
            <div className={`${styles.specField} ${styles.specRowFull}`}>
              <span className={styles.specLabel}>Structural Function</span>
              <span className={styles.specText}>{component.designFunction}</span>
            </div>
          </div>
        </div>

        {/* Anomaly & Findings Summary */}
        {component.status === 'assessed_findings' && (
          <div className={styles.findingsCard}>
            <h4 className={styles.findingsTitle}>
              <AlertTriangle size={13} />
              <span>Inspection Observation &amp; Defect Data</span>
            </h4>
            <p className={styles.findingsText}>
              {component.defectSummary || `${component.findingsCount || 1} defect(s) detected on this member.`}
            </p>
            {component.inspectionId && (
              <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(224, 86, 74, 0.2)', fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>
                  <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>INSPECTION ID: </span>
                  <Link to={`/vision?inspectionId=${component.inspectionId}`} style={{ color: 'var(--color-mineral)', textDecoration: 'underline', fontFamily: 'var(--font-mono)' }}>
                    {component.inspectionId.slice(0, 8)}... (View in Vision Studio)
                  </Link>
                </div>
                {component.inspectionDate && (
                  <div>
                    <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>INSPECTED ON: </span>
                    <span style={{ color: 'var(--text-body)', fontFamily: 'var(--font-mono)' }}>
                      {new Date(component.inspectionDate).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {component.status === 'assessed_nominal' && (
          <div className={styles.findingsCard} style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-base)' }}>
            <h4 className={styles.findingsTitle} style={{ color: 'var(--status-good)' }}>
              <CheckCircle2 size={13} color="var(--status-good)" />
              <span>Nominal Condition Verified</span>
            </h4>
            <p className={styles.findingsText}>
              Member surveyed in inspection cycle with zero defect anomalies detected.
            </p>
            {component.inspectionId && (
              <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)', fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>
                  <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>INSPECTION ID: </span>
                  <Link to={`/vision?inspectionId=${component.inspectionId}`} style={{ color: 'var(--color-mineral)', textDecoration: 'underline', fontFamily: 'var(--font-mono)' }}>
                    {component.inspectionId.slice(0, 8)}... (View in Vision Studio)
                  </Link>
                </div>
                {component.inspectionDate && (
                  <div>
                    <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>INSPECTED ON: </span>
                    <span style={{ color: 'var(--text-body)', fontFamily: 'var(--font-mono)' }}>
                      {new Date(component.inspectionDate).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {(component.status === 'not_assessed' || component.status === 'illustrative') && (
          <div className={styles.findingsCard} style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-base)' }}>
            <h4 className={styles.findingsTitle} style={{ color: 'var(--text-muted)' }}>
              <HelpCircle size={13} />
              <span>No Inspection Data Recorded</span>
            </h4>
            <p className={styles.findingsText}>
              No inspection data recorded for this structural component. This member is represented via parametric geometry for spatial reference only.
            </p>
          </div>
        )}

        {/* Linked Photographic Evidence */}
        {displayEvidence.length > 0 && (
          <div className={styles.evidenceSection}>
            <h4 className={styles.sectionHeading}>
              <Camera size={13} />
              <span>
                {relevantEvidence.length > 0 ? 'Member Photographic Evidence' : 'Asset Evidence Archive'}
              </span>
            </h4>
            <div className={styles.evidenceGrid}>
              {displayEvidence.map((item) => (
                <div
                  key={item.id}
                  className={styles.evidenceThumbnailCard}
                  onClick={() => setSelectedPhoto(item.file_path)}
                  title={`Click to expand: ${item.caption}`}
                >
                  <img
                    src={item.file_path}
                    alt={item.caption}
                    className={styles.evidenceImg}
                    loading="lazy"
                  />
                  <div className={styles.evidenceOverlay}>{item.caption}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Link to Inspections */}
        <Link
          to={`/inspections?assetId=${asset.id}`}
          className={styles.actionButton}
        >
          <span>Run Inspection on this Asset</span>
          <ExternalLink size={13} />
        </Link>
      </div>

      {/* Lightbox Modal */}
      {selectedPhoto && (
        <div
          className={styles.lightboxOverlay}
          onClick={() => setSelectedPhoto(null)}
          role="dialog"
          aria-modal="true"
        >
          <div className={styles.lightboxModal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.lightboxImageWrapper}>
              <img src={selectedPhoto} alt="Structural Evidence" className={styles.lightboxImage} />
            </div>
            <div className={styles.lightboxFooter}>
              <span>{component.name} — Field Inspection Evidence</span>
              <button
                type="button"
                className={styles.closeButton}
                onClick={() => setSelectedPhoto(null)}
                aria-label="Close modal"
              >
                <X size={16} />
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
