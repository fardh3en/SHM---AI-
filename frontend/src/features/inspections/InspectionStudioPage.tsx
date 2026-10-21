import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import {
  Layers,
  UploadCloud,
  FileCheck,
  ChevronRight,
  ArrowLeft,
  History,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import Button from '../../components/ui/Button'
import StatusChip from '../../components/ui/StatusChip'
import EmptyState from '../../components/ui/EmptyState'
import AssetSelector from './AssetSelector'
import EvidenceUploader, { type SelectedMediaFile } from './EvidenceUploader'
import InspectionFindingsCard from './InspectionFindingsCard'
import { useAsset } from '../../hooks/useAssets'
import { useAssetInspections } from '../../hooks/useAssetInspections'
import {
  useCreateInspection,
  useUpdateInspection,
  useRunInspection,
} from '../../hooks/useInspections'
import type { Asset } from '../../api/assets'
import type { Inspection, InspectionSource } from '../../api/inspections'
import styles from './InspectionStudioPage.module.css'

type Step = 1 | 2 | 3 | 4

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}

export default function InspectionStudioPage() {
  const [searchParams] = useSearchParams()
  const initialAssetId = searchParams.get('asset_id')
  const initialEvidencePath = searchParams.get('evidence_path')

  // Step state
  const [step, setStep] = useState<Step>(1)
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null)
  const [source, setSource] = useState<InspectionSource>('image')
  const [notes, setNotes] = useState<string>('')
  const [mediaFile, setMediaFile] = useState<SelectedMediaFile | null>(null)
  const [triggerVisionPipeline, setTriggerVisionPipeline] = useState<boolean>(true)
  const [retryInspectionId, setRetryInspectionId] = useState<string | null>(null)

  // Result state
  const [completedInspection, setCompletedInspection] = useState<Inspection | null>(null)
  const [submissionError, setSubmissionError] = useState<string | null>(null)

  // Mutations
  const createMutation = useCreateInspection()
  const updateMutation = useUpdateInspection()
  const runMutation = useRunInspection()

  // Queries
  const { data: preloadedAsset } = useAsset(initialAssetId ?? undefined)
  const { data: assetInspections, isLoading: inspectionsLoading } = useAssetInspections(
    selectedAsset?.id
  )

  // If asset_id or evidence_path was provided in URL, pre-populate
  useEffect(() => {
    if (preloadedAsset && !selectedAsset) {
      setSelectedAsset(preloadedAsset)
      if (initialEvidencePath) {
        setMediaFile({
          previewUrl: initialEvidencePath,
          formattedSize: 'Archived',
          isSampleEvidence: true,
          caption: initialEvidencePath.split('/').pop(),
        })
        setStep(2)
      }
    }
  }, [preloadedAsset, selectedAsset, initialEvidencePath])

  const isSubmitting =
    createMutation.isPending || updateMutation.isPending || runMutation.isPending

  // Handle Form Submission
  const handleSubmitInspection = async () => {
    if (!selectedAsset) return
    setSubmissionError(null)

    try {
      let currentInspection: Inspection

      if (retryInspectionId) {
        // Updating existing inspection with newly attached evidence
        const inputPath = mediaFile
          ? (mediaFile.isSampleEvidence
              ? mediaFile.previewUrl
              : `/uploads/${mediaFile.file ? mediaFile.file.name : 'upload.jpg'}`)
          : undefined

        currentInspection = await updateMutation.mutateAsync({
          id: retryInspectionId,
          data: {
            input_path: inputPath,
            status: 'pending',
            error_message: null,
            notes: notes.trim() || undefined,
          },
        })
      } else {
        // 1. Create base inspection record
        const created = await createMutation.mutateAsync({
          asset_id: selectedAsset.id,
          source,
          notes: notes.trim() || undefined,
        })

        currentInspection = created

        // 2. If a media file was staged, record its input_path
        if (mediaFile) {
          const inputPath = mediaFile.isSampleEvidence
            ? mediaFile.previewUrl
            : `/uploads/${mediaFile.file ? mediaFile.file.name : 'upload.jpg'}`

          currentInspection = await updateMutation.mutateAsync({
            id: created.id,
            data: { input_path: inputPath },
          })
        }
      }

      // 3. Trigger vision pipeline if selected
      if (triggerVisionPipeline) {
        try {
          const runResult = await runMutation.mutateAsync(currentInspection.id)
          currentInspection = runResult
        } catch (err: unknown) {
          // If the run endpoint threw an HTTP error rather than returning 200 with failed status,
          // capture it so the user sees real diagnostics
          const errorMsg = err instanceof Error ? err.message : String(err)
          currentInspection = {
            ...currentInspection,
            status: 'failed',
            error_message: errorMsg,
          }
        }
      }

      setCompletedInspection(currentInspection)
      setRetryInspectionId(null)
      setStep(4)
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to register inspection record.'
      setSubmissionError(errorMsg)
    }
  }

  // Handle standalone vision execution from Findings card (e.g. if skipped initially)
  const handleRunVisionPipelineOnCompleted = async () => {
    if (!completedInspection) return
    try {
      const updated = await runMutation.mutateAsync(completedInspection.id)
      setCompletedInspection(updated)
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : String(err)
      setCompletedInspection({
        ...completedInspection,
        status: 'failed',
        error_message: errorMsg,
      })
    }
  }

  // Handle return to evidence step for an existing inspection
  const handleRetryWithEvidence = () => {
    if (!completedInspection || !selectedAsset) return
    setRetryInspectionId(completedInspection.id)
    setSubmissionError(null)
    setStep(2)
  }

  // Reset entire studio workflow
  const handleResetWorkflow = () => {
    setStep(1)
    setNotes('')
    setMediaFile(null)
    setCompletedInspection(null)
    setSubmissionError(null)
    setRetryInspectionId(null)
  }

  return (
    <div className={styles.container}>
      <PageHeader
        title="Inspection Studio"
        description="Structural health diagnostic pipeline: assign asset, ingest sensor or imagery evidence, and execute vision intelligence."
        breadcrumb={[
          { label: 'Dashboard', to: '/dashboard' },
          { label: 'Inspection Studio' },
        ]}
      />

      <main className={styles.content}>
        {/* ── Stepper Header ── */}
        <nav className={styles.stepper} aria-label="Inspection Workflow Steps">
          <button
            type="button"
            className={`${styles.stepItem} ${step === 1 ? styles.stepActive : ''} ${
              step > 1 ? styles.stepCompleted : ''
            }`}
            onClick={() => step > 1 && setStep(1)}
            disabled={step === 4 || isSubmitting}
          >
            <span className={styles.stepNumber}>{step > 1 ? '✓' : '1'}</span>
            <span>Target Asset</span>
          </button>

          <div className={styles.stepDivider} aria-hidden="true" />

          <button
            type="button"
            className={`${styles.stepItem} ${step === 2 ? styles.stepActive : ''} ${
              step > 2 ? styles.stepCompleted : ''
            }`}
            onClick={() => step > 2 && setStep(2)}
            disabled={step === 4 || !selectedAsset || isSubmitting}
          >
            <span className={styles.stepNumber}>{step > 2 ? '✓' : '2'}</span>
            <span>Evidence & Details</span>
          </button>

          <div className={styles.stepDivider} aria-hidden="true" />

          <button
            type="button"
            className={`${styles.stepItem} ${step === 3 ? styles.stepActive : ''} ${
              step > 3 ? styles.stepCompleted : ''
            }`}
            onClick={() => step > 3 && setStep(3)}
            disabled={step === 4 || !selectedAsset || isSubmitting}
          >
            <span className={styles.stepNumber}>{step > 3 ? '✓' : '3'}</span>
            <span>Review & Run</span>
          </button>

          <div className={styles.stepDivider} aria-hidden="true" />

          <div
            className={`${styles.stepItem} ${step === 4 ? styles.stepActive : ''}`}
            aria-current={step === 4 ? 'step' : undefined}
          >
            <span className={styles.stepNumber}>4</span>
            <span>Diagnostic Findings</span>
          </div>
        </nav>

        {/* ── Step 1: Select Asset ── */}
        {step === 1 && (
          <div className={styles.workspace}>
            <div className={styles.stepCard}>
              <div className={styles.stepHeader}>
                <h2 className={styles.stepTitle}>Step 1: Select Registered Asset</h2>
                <p className={styles.stepSubtitle}>
                  Choose the structural infrastructure unit from the verified asset registry to
                  associate with this inspection session.
                </p>
              </div>

              <AssetSelector
                selectedAsset={selectedAsset}
                onSelectAsset={(asset) => setSelectedAsset(asset)}
              />

              <div className={styles.stepFooter}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  {selectedAsset
                    ? `Selected: ${selectedAsset.name} (${selectedAsset.id})`
                    : 'Select an asset from the list above to proceed.'}
                </span>

                <Button
                  variant="primary"
                  disabled={!selectedAsset}
                  onClick={() => setStep(2)}
                >
                  Configure Evidence <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ── Step 2: Evidence & Configuration ── */}
        {step === 2 && selectedAsset && (
          <div className={styles.workspace}>
            <div className={styles.stepCard}>
              <div className={styles.stepHeader}>
                <h2 className={styles.stepTitle}>Step 2: Evidence Upload & Capture Parameters</h2>
                <p className={styles.stepSubtitle}>
                  Target asset:{' '}
                  <strong style={{ color: 'var(--text-primary)' }}>{selectedAsset.name}</strong>{' '}
                  ({selectedAsset.asset_type}). Ingest high-resolution photographic evidence or
                  configure manual field observations.
                </p>
              </div>

              <EvidenceUploader
                assetId={selectedAsset.id}
                source={source}
                onChangeSource={setSource}
                notes={notes}
                onChangeNotes={setNotes}
                mediaFile={mediaFile}
                onSelectMediaFile={setMediaFile}
              />

              <div className={styles.stepFooter}>
                <Button variant="ghost" onClick={() => setStep(1)}>
                  <ArrowLeft size={16} /> Back to Asset Selection
                </Button>

                <Button variant="primary" onClick={() => setStep(3)}>
                  Review & Submit <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ── Step 3: Review Before Submit ── */}
        {step === 3 && selectedAsset && (
          <div className={styles.workspace}>
            <div className={styles.stepCard}>
              <div className={styles.stepHeader}>
                <h2 className={styles.stepTitle}>Step 3: Verification & Pipeline Dispatch</h2>
                <p className={styles.stepSubtitle}>
                  Verify telemetry parameters and choose execution mode before committing this
                  inspection record to the structural database.
                </p>
              </div>

              {submissionError && (
                <div
                  style={{
                    background: 'rgba(224, 86, 74, 0.1)',
                    border: '1px solid rgba(224, 86, 74, 0.35)',
                    padding: 'var(--space-4)',
                    borderRadius: 'var(--radius-sm)',
                    color: '#ff8b80',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    fontSize: '0.875rem',
                  }}
                >
                  <AlertCircle size={18} />
                  <span>{submissionError}</span>
                </div>
              )}

              <div className={styles.reviewGrid}>
                {/* Asset Summary */}
                <div className={styles.reviewSection}>
                  <div className={styles.reviewSectionTitle}>
                    <Layers size={14} /> Structural Asset Summary
                  </div>
                  <div className={styles.reviewFieldList}>
                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Asset Name</span>
                      <span className={styles.reviewValue} style={{ fontWeight: 600 }}>
                        {selectedAsset.name}
                      </span>
                    </div>
                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Category / Type</span>
                      <span className={styles.reviewValue}>{selectedAsset.asset_type}</span>
                    </div>
                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Location</span>
                      <span className={styles.reviewValue}>
                        {selectedAsset.location || 'Unspecified'}
                      </span>
                    </div>
                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Primary Material</span>
                      <span className={styles.reviewValue}>
                        {selectedAsset.material || 'Unspecified'}
                      </span>
                    </div>
                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Asset Status</span>
                      <div>
                        <StatusChip status={selectedAsset.status} size="sm" />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Evidence & Parameters */}
                <div className={styles.reviewSection}>
                  <div className={styles.reviewSectionTitle}>
                    <UploadCloud size={14} /> Evidence & Survey Parameters
                  </div>
                  <div className={styles.reviewFieldList}>
                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Data Capture Source</span>
                      <span className={styles.reviewValue} style={{ textTransform: 'capitalize' }}>
                        {source.replace('_', ' ')}
                      </span>
                    </div>

                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Attached Media File</span>
                      <span className={styles.reviewValue}>
                        {mediaFile ? (
                          <>
                            <code>
                              {mediaFile.caption ?? (mediaFile.file ? mediaFile.file.name : 'Staged Evidence')}
                            </code>{' '}
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              ({mediaFile.isSampleEvidence ? 'Archived Photograph' : 'Local File Upload'}
                              {mediaFile.width && mediaFile.height
                                ? ` • ${mediaFile.width}×${mediaFile.height}px`
                                : ''}
                              )
                            </span>
                          </>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                            None attached (Observation notes only)
                          </span>
                        )}
                      </span>
                    </div>

                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Field Notes</span>
                      <span
                        className={styles.reviewValue}
                        style={{
                          color: notes.trim() ? 'var(--text-primary)' : 'var(--text-muted)',
                          fontStyle: notes.trim() ? 'normal' : 'italic',
                          maxHeight: '80px',
                          overflowY: 'auto',
                        }}
                      >
                        {notes.trim() || 'No field notes entered.'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Execution Options */}
              <label className={styles.executionOption}>
                <input
                  type="checkbox"
                  checked={triggerVisionPipeline}
                  onChange={(e) => setTriggerVisionPipeline(e.target.checked)}
                />
                <div className={styles.executionText}>
                  <div className={styles.executionTitle}>
                    Execute Computer Vision Inference Pipeline (POST /api/v1/inspections/{'{id}'}/run)
                  </div>
                  <div className={styles.executionDesc}>
                    When checked, the backend will trigger automated defect segmentation and health
                    score evaluation immediately following registration. If model weights are
                    unprovisioned on the backend, the pipeline will capture and surface the true
                    error without fabricating fake scores.
                  </div>
                </div>
              </label>

              {triggerVisionPipeline && !mediaFile && (
                <div
                  style={{
                    background: 'rgba(216, 198, 90, 0.1)',
                    border: '1px solid rgba(216, 198, 90, 0.35)',
                    padding: 'var(--space-4)',
                    borderRadius: 'var(--radius-sm)',
                    color: '#e2d37c',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    fontSize: '0.875rem',
                    marginTop: 'var(--space-4)',
                  }}
                >
                  <AlertCircle size={20} style={{ flexShrink: 0 }} />
                  <div>
                    <strong>Photographic Evidence Missing:</strong> Automated computer vision defect segmentation requires an uploaded image or archived photograph.
                    Please <button type="button" onClick={() => setStep(2)} style={{ background: 'none', border: 'none', color: 'var(--color-ivory)', textDecoration: 'underline', cursor: 'pointer', padding: 0, font: 'inherit' }}>return to Step 2 to attach evidence</button>, or uncheck automated vision inference above to register this inspection as a manual observation.
                  </div>
                </div>
              )}

              <div className={styles.stepFooter}>
                <Button
                  variant="ghost"
                  onClick={() => setStep(2)}
                  disabled={isSubmitting}
                >
                  <ArrowLeft size={16} /> Edit Evidence & Notes
                </Button>

                <Button
                  variant="primary"
                  onClick={handleSubmitInspection}
                  disabled={isSubmitting || (triggerVisionPipeline && !mediaFile)}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 size={16} className="spin" style={{ animation: 'spin 1s linear infinite' }} />{' '}
                      {retryInspectionId ? 'Updating & Analyzing...' : 'Registering & Analyzing...'}
                    </>
                  ) : (
                    <>
                      <FileCheck size={16} />{' '}
                      {retryInspectionId ? 'Update Evidence & Execute Inspection' : 'Submit & Execute Inspection'}
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ── Step 4: Diagnostic Findings ── */}
        {step === 4 && completedInspection && selectedAsset && (
          <div className={styles.workspace}>
            <InspectionFindingsCard
              inspection={completedInspection}
              asset={selectedAsset}
              onReset={handleResetWorkflow}
              onRunVision={
                completedInspection.status === 'pending' || completedInspection.status === 'failed'
                  ? handleRunVisionPipelineOnCompleted
                  : undefined
              }
              isRunningVision={runMutation.isPending}
              onRetryWithEvidence={handleRetryWithEvidence}
            />
          </div>
        )}

        {/* ── Asset Historical Inspection Ledger ── */}
        {selectedAsset && step < 4 && (
          <section className={styles.historySection} aria-label="Asset Historical Ledger">
            <div className={styles.historyHeader}>
              <h3 className={styles.historyTitle}>
                <History size={16} /> Prior Inspections for {selectedAsset.name}
              </h3>
              <Link
                to={`/assets/${selectedAsset.id}`}
                style={{
                  fontSize: '0.8125rem',
                  color: 'var(--color-mineral)',
                  textDecoration: 'none',
                }}
              >
                View Asset Dossier →
              </Link>
            </div>

            {inspectionsLoading ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                Loading inspection history...
              </div>
            ) : !assetInspections || assetInspections.length === 0 ? (
              <EmptyState
                title="No prior inspection records"
                description="This asset does not yet have historical inspection records in the database."
              />
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className={styles.historyTable}>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Inspection ID</th>
                      <th>Source</th>
                      <th>Status</th>
                      <th>Defects</th>
                      <th>Health Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assetInspections.map((insp) => (
                      <tr key={insp.id}>
                        <td>{formatDate(insp.created_at)}</td>
                        <td>
                          <code
                            style={{
                              fontFamily: 'var(--font-mono)',
                              fontSize: '0.75rem',
                              color: 'var(--color-mineral)',
                            }}
                          >
                            {insp.id.slice(0, 8)}...
                          </code>
                        </td>
                        <td style={{ textTransform: 'capitalize' }}>
                          {insp.source.replace('_', ' ')}
                        </td>
                        <td>
                          <StatusChip status={insp.status} size="sm" />
                        </td>
                        <td>{insp.defect_count}</td>
                        <td>
                          {insp.health_score !== null ? (
                            <span
                              style={{
                                fontWeight: 600,
                                color:
                                  insp.health_score >= 75
                                    ? 'var(--color-sage)'
                                    : insp.health_score >= 50
                                    ? 'var(--color-mineral)'
                                    : '#ff8b80',
                              }}
                            >
                              {insp.health_score.toFixed(1)}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  )
}
