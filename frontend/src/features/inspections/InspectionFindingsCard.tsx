import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CheckCircle2,
  AlertTriangle,
  Clock,
  RotateCcw,
  ExternalLink,
  ShieldAlert,
  Play,
  Copy,
  Check,
  FileText,
  Activity,
  Layers,
  UploadCloud,
} from 'lucide-react'
import StatusChip from '../../components/ui/StatusChip'
import Button from '../../components/ui/Button'
import type { Inspection } from '../../api/inspections'
import type { Asset } from '../../api/assets'
import styles from './InspectionFindingsCard.module.css'

interface InspectionFindingsCardProps {
  inspection: Inspection
  asset: Asset
  onReset: () => void
  onRunVision?: () => Promise<void>
  isRunningVision?: boolean
  onRetryWithEvidence?: () => void
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

export default function InspectionFindingsCard({
  inspection,
  asset,
  onReset,
  onRunVision,
  isRunningVision = false,
  onRetryWithEvidence,
}: InspectionFindingsCardProps) {
  const [copiedId, setCopiedId] = useState(false)

  const handleCopyId = () => {
    navigator.clipboard.writeText(inspection.id)
    setCopiedId(true)
    setTimeout(() => setCopiedId(false), 2000)
  }

  const isFailed = inspection.status === 'failed'
  const isCompleted = inspection.status === 'completed'
  const isProcessing = inspection.status === 'processing'
  const isPending = inspection.status === 'pending'

  return (
    <div className={styles.container}>
      {/* ── Status Banner ── */}
      {isCompleted && (
        <div className={`${styles.banner} ${styles.bannerCompleted}`}>
          <CheckCircle2 size={24} className={styles.bannerIcon} />
          <div className={styles.bannerContent}>
            <div className={styles.bannerTitle}>Inspection Workflow Completed</div>
            <div className={styles.bannerDescription}>
              Structural diagnostics and defect quantification completed successfully. Records
              have been appended to the asset lifecycle ledger.
            </div>
          </div>
        </div>
      )}

      {isFailed && (
        <div className={`${styles.banner} ${styles.bannerFailed}`}>
          <AlertTriangle size={24} className={styles.bannerIcon} />
          <div className={styles.bannerContent}>
            <div className={styles.bannerTitle}>Automated Vision Pipeline Failure</div>
            <div className={styles.bannerDescription}>
              The backend vision service processed the request and recorded a failure status.
              Inspection telemetry and error details are preserved below for diagnostic review.
            </div>
          </div>
        </div>
      )}

      {isPending && (
        <div className={`${styles.banner} ${styles.bannerPending}`}>
          <Clock size={24} className={styles.bannerIcon} />
          <div className={styles.bannerContent}>
            <div className={styles.bannerTitle}>Inspection Registered (Pending Execution)</div>
            <div className={styles.bannerDescription}>
              This inspection record has been stored in the database. You can trigger the automated
              vision pipeline below or keep this record as a manual observation entry.
            </div>
          </div>
        </div>
      )}

      {isProcessing && (
        <div className={`${styles.banner} ${styles.bannerProcessing}`}>
          <Activity size={24} className={styles.bannerIcon} />
          <div className={styles.bannerContent}>
            <div className={styles.bannerTitle}>Processing In Progress</div>
            <div className={styles.bannerDescription}>
              The inspection record is currently marked as processing.
            </div>
          </div>
        </div>
      )}

      {/* ── Metric Telemetry Cards ── */}
      <div className={styles.metricsGrid}>
        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Pipeline Status</span>
          <div style={{ marginTop: '4px' }}>
            <StatusChip status={inspection.status} size="md" />
          </div>
          <span className={styles.metricSubtitle}>Backend lifecycle state</span>
        </div>

        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Defect Count</span>
          <div className={styles.metricValue}>
            {inspection.defect_count}
            <span className={styles.metricUnit}>defects</span>
          </div>
          <span className={styles.metricSubtitle}>Segmented structural defects</span>
        </div>

        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Health Score</span>
          <div className={styles.metricValue}>
            {inspection.health_score !== null ? inspection.health_score.toFixed(1) : '—'}
            {inspection.health_score !== null && <span className={styles.metricUnit}>/ 100</span>}
          </div>
          <span className={styles.metricSubtitle}>
            {inspection.health_score !== null ? 'Evaluated integrity score' : 'No score computed'}
          </span>
        </div>

        <div className={styles.metricCard}>
          <span className={styles.metricLabel}>Latency</span>
          <div className={styles.metricValue}>
            {inspection.processing_time_ms !== null ? inspection.processing_time_ms : '—'}
            {inspection.processing_time_ms !== null && (
              <span className={styles.metricUnit}>ms</span>
            )}
          </div>
          <span className={styles.metricSubtitle}>Inference execution time</span>
        </div>
      </div>

      {/* ── Error Diagnostics Callout (if failed) ── */}
      {isFailed && inspection.error_message && (
        <div className={styles.errorBox}>
          <div className={styles.errorBoxTitle}>
            <ShieldAlert size={16} /> Backend Pipeline Error Diagnostic
          </div>
          <div className={styles.errorBoxMsg}>{inspection.error_message}</div>
          <div className={styles.errorBoxNote}>
            {!inspection.input_path || inspection.error_message.toLowerCase().includes('evidence') ? (
              <>
                <strong>Actionable Guidance:</strong> Automated computer vision defect segmentation requires a high-resolution photograph or drone survey image. No photographic evidence was attached to this inspection record. Click <strong>Attach Evidence &amp; Retry</strong> below to upload or select a photograph for this asset.
              </>
            ) : inspection.error_message.toLowerCase().includes('weight') || inspection.error_message.toLowerCase().includes('model') ? (
              <>
                <strong>Model Provisioning Guidance:</strong> Configured YOLO11 weights are not provisioned on disk. Automatic download is disabled to prevent unconsented large file transfers. To provision model weights locally, execute: <code>python scripts/download_weights.py</code> in the project directory, then click <strong>Retry Vision Pipeline</strong> below.
              </>
            ) : (
              <>
                <strong>Technical Note:</strong> The backend pipeline recorded a failure during processing. Inspection telemetry and diagnostic error details are preserved server-side for debugging.
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Detailed Record Dossier ── */}
      <div className={styles.panel}>
        <div className={styles.panelHeader}>
          <h4 className={styles.panelTitle}>
            <FileText size={16} /> Inspection Record Dossier
          </h4>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Database ID: #{inspection.id.slice(0, 8)}
          </span>
        </div>

        <div className={styles.tableGrid}>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Inspection ID</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className={styles.monoCode}>{inspection.id}</span>
              <button
                type="button"
                onClick={handleCopyId}
                title="Copy full Inspection UUID"
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '2px',
                }}
              >
                {copiedId ? <Check size={14} color="var(--color-sage)" /> : <Copy size={14} />}
              </button>
            </div>
          </div>

          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Assigned Asset</span>
            <div className={styles.fieldValue}>
              <Link
                to={`/assets/${asset.id}`}
                style={{
                  color: 'var(--color-mineral)',
                  textDecoration: 'none',
                  fontWeight: 500,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                {asset.name} <ExternalLink size={12} />
              </Link>{' '}
              <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                ({asset.asset_type})
              </span>
            </div>
          </div>

          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Capture Source</span>
            <div className={styles.fieldValue} style={{ textTransform: 'capitalize' }}>
              {inspection.source.replace('_', ' ')}
            </div>
          </div>

          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Evidence Input Path</span>
            <div className={styles.fieldValue}>
              {inspection.input_path ? (
                <span className={styles.monoCode}>{inspection.input_path}</span>
              ) : (
                <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  No input path recorded
                </span>
              )}
            </div>
          </div>

          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Created Timestamp</span>
            <div className={styles.fieldValue}>{formatDate(inspection.created_at)}</div>
          </div>

          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>Updated Timestamp</span>
            <div className={styles.fieldValue}>{formatDate(inspection.updated_at)}</div>
          </div>
        </div>

        {/* Notes */}
        <div className={styles.fieldRow}>
          <span className={styles.fieldLabel}>Inspector / Field Observations</span>
          <div className={styles.notesBox}>
            {inspection.notes?.trim() || (
              <span style={{ fontStyle: 'italic', color: 'var(--text-muted)' }}>
                No textual observations provided for this inspection.
              </span>
            )}
          </div>
        </div>

        {/* Transparent Capability Note */}
        <div className={styles.transparentNotice}>
          <div className={styles.transparentTitle}>Engineering Telemetry Assurance</div>
          <div className={styles.transparentDesc}>
            All metrics, status indicators, and counts rendered in this workspace originate directly
            from the FastAPI endpoints (<code>/api/v1/inspections/*</code>). Confidence intervals,
            defect geometry polygons, and automated severity ratings are only displayed when
            produced by the validated backend segmentation model.
          </div>
        </div>
      </div>

      {/* ── Action Buttons ── */}
      <div className={styles.actionsBar}>
        <div className={styles.actionsGroup}>
          <Button variant="secondary" onClick={onReset}>
            <RotateCcw size={16} /> Run Another Inspection
          </Button>

          {isFailed && (!inspection.input_path || inspection.error_message?.toLowerCase().includes('evidence')) && onRetryWithEvidence && (
            <Button
              variant="primary"
              onClick={onRetryWithEvidence}
            >
              <UploadCloud size={16} /> Attach Evidence &amp; Retry
            </Button>
          )}

          {isFailed && inspection.input_path && onRunVision && (
            <Button
              variant="primary"
              onClick={onRunVision}
              disabled={isRunningVision}
            >
              <RotateCcw size={16} /> {isRunningVision ? 'Running Pipeline...' : 'Retry Vision Pipeline'}
            </Button>
          )}

          {isPending && onRunVision && (
            <Button
              variant="primary"
              onClick={onRunVision}
              disabled={isRunningVision}
            >
              <Play size={16} /> {isRunningVision ? 'Running Pipeline...' : 'Execute Vision Pipeline'}
            </Button>
          )}
        </div>

        <div className={styles.actionsGroup}>
          <Link to={`/assets/${asset.id}`} style={{ textDecoration: 'none' }}>
            <Button variant="ghost">
              <Layers size={16} /> Asset Dossier
            </Button>
          </Link>
          <Link to="/dashboard" style={{ textDecoration: 'none' }}>
            <Button variant="ghost">
              Dashboard
            </Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
