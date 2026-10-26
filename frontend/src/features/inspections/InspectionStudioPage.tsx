import { useState, useEffect } from 'react'
import { useSearchParams, useLocation } from 'react-router-dom'
import {
  Layers,
  UploadCloud,
  ChevronRight,
  ArrowLeft,
  History,
  AlertCircle,
  Loader2,
  ScanLine,
  PlusCircle,
} from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import Button from '../../components/ui/Button'
import StatusChip from '../../components/ui/StatusChip'
import EmptyState from '../../components/ui/EmptyState'
import AssetSelector from './AssetSelector'
import EvidenceUploader, { type SelectedMediaFile } from './EvidenceUploader'
import InspectionFindingsCard from './InspectionFindingsCard'
import { useAsset, useAssets, useCreateAsset } from '../../hooks/useAssets'
import { useAssetInspections } from '../../hooks/useAssetInspections'
import {
  useCreateInspection,
  useUpdateInspection,
  useRunInspection,
} from '../../hooks/useInspections'
import type { Asset, AssetType } from '../../api/assets'
import type { Inspection, InspectionSource } from '../../api/inspections'
import { evidenceApi } from '../../api/evidence'
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
  const location = useLocation()
  const initialAssetId = searchParams.get('asset_id')
  const initialEvidencePath = searchParams.get('evidence_path')

  // Step state — defaults to Step 1: Upload Crack Photograph (Photo-First)
  const [step, setStep] = useState<Step>(1)
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null)
  const [structureMode, setStructureMode] = useState<'existing' | 'quick'>('quick')
  const [quickName, setQuickName] = useState<string>('')
  const [quickCategory, setQuickCategory] = useState<AssetType>('building')

  const [source, setSource] = useState<InspectionSource>('image')
  const [notes, setNotes] = useState<string>('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [mediaFile, setMediaFile] = useState<SelectedMediaFile | null>(null)
  const [triggerVisionPipeline, setTriggerVisionPipeline] = useState<boolean>(true)
  const [retryInspectionId, setRetryInspectionId] = useState<string | null>(null)

  // Result state
  const [completedInspection, setCompletedInspection] = useState<Inspection | null>(null)
  const [submissionError, setSubmissionError] = useState<string | null>(null)

  // Mutations
  const createAssetMutation = useCreateAsset()
  const createMutation = useCreateInspection()
  const updateMutation = useUpdateInspection()
  const runMutation = useRunInspection()

  // Queries
  const { data: preloadedAsset } = useAsset(initialAssetId ?? undefined)
  const { data: allAssetsData } = useAssets(1, 100)
  const assetsList = allAssetsData?.items ?? []

  const { data: assetInspections, isLoading: inspectionsLoading } = useAssetInspections(
    selectedAsset?.id
  )

  // Check for preloaded file passed via router location state (e.g. from Dashboard drop)
  useEffect(() => {
    const locState = location.state as { preloadedFile?: File } | null
    if (locState?.preloadedFile && !mediaFile) {
      const file = locState.preloadedFile
      const objectUrl = URL.createObjectURL(file)
      const img = new Image()
      img.onload = () => {
        setMediaFile({
          file,
          previewUrl: objectUrl,
          width: img.naturalWidth,
          height: img.naturalHeight,
          formattedSize: `${(file.size / (1024 * 1024)).toFixed(2)} MB`,
          isSampleEvidence: false,
          caption: file.name,
        })
      }
      img.onerror = () => {
        setMediaFile({
          file,
          previewUrl: objectUrl,
          formattedSize: `${(file.size / (1024 * 1024)).toFixed(2)} MB`,
          isSampleEvidence: false,
          caption: file.name,
        })
      }
      img.src = objectUrl
    }
  }, [location.state, mediaFile])

  // Pre-populate asset or archived evidence if query params provided
  useEffect(() => {
    if (preloadedAsset && !selectedAsset) {
      setSelectedAsset(preloadedAsset)
      setStructureMode('existing')
      if (initialEvidencePath) {
        setMediaFile({
          previewUrl: initialEvidencePath,
          formattedSize: 'Archived',
          isSampleEvidence: true,
          caption: initialEvidencePath.split('/').pop(),
        })
        setStep(3)
      }
    }
  }, [preloadedAsset, selectedAsset, initialEvidencePath])

  // When mediaFile is selected, default a quick name if empty
  useEffect(() => {
    if (mediaFile && !quickName && !selectedAsset) {
      const baseStem = mediaFile.caption
        ? mediaFile.caption.replace(/\.[^/.]+$/, '').replace(/[^a-zA-Z0-9_\-\s]/g, ' ')
        : 'Inspected Structure'
      setQuickName(baseStem.trim() || 'Monitored Structure')
    }
  }, [mediaFile, quickName, selectedAsset])

  const [isUploading, setIsUploading] = useState(false)
  const isSubmitting =
    isUploading ||
    createAssetMutation.isPending ||
    createMutation.isPending ||
    updateMutation.isPending ||
    runMutation.isPending

  const handleToggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    )
  }

  // Handle Form Submission
  const handleSubmitInspection = async () => {
    setSubmissionError(null)

    if (!mediaFile) {
      setSubmissionError('Please select or upload a crack photograph before running analysis.')
      return
    }

    try {
      let activeAsset = selectedAsset

      // If user opted for Quick Structure Entry and no asset is chosen, register it
      if (!activeAsset) {
        const structureName = quickName.trim() || 'Monitored Structure'
        const tagNotes = selectedTags.length > 0 ? `Field tags: ${selectedTags.join(', ')}` : undefined
        const createdAsset = await createAssetMutation.mutateAsync({
          name: structureName,
          asset_type: quickCategory,
          description: tagNotes,
        })
        activeAsset = createdAsset
        setSelectedAsset(createdAsset)
      }

      let currentInspection: Inspection
      let inputPath: string | undefined = undefined

      if (mediaFile) {
        if (mediaFile.isSampleEvidence) {
          inputPath = mediaFile.previewUrl
        } else if (mediaFile.file) {
          setIsUploading(true)
          try {
            const uploadRes = await evidenceApi.upload(
              mediaFile.file,
              activeAsset.id,
              notes.trim() || mediaFile.caption || mediaFile.file.name
            )
            inputPath = uploadRes.file_path
          } catch (uploadErr: unknown) {
            const msg = uploadErr instanceof Error ? uploadErr.message : 'Upload failed'
            throw new Error(`Evidence image upload failed: ${msg}`)
          } finally {
            setIsUploading(false)
          }
        }
      }

      // Synthesize notes with tags
      const noteParts: string[] = []
      if (selectedTags.length > 0) noteParts.push(`Observations: ${selectedTags.join(', ')}`)
      if (notes.trim()) noteParts.push(notes.trim())
      const combinedNotes = noteParts.length > 0 ? noteParts.join(' | ') : undefined

      if (retryInspectionId) {
        // Updating existing inspection with newly attached evidence
        currentInspection = await updateMutation.mutateAsync({
          id: retryInspectionId,
          data: {
            input_path: inputPath,
            status: 'pending',
            error_message: null,
            notes: combinedNotes,
          },
        })
      } else {
        // 1. Create base inspection record
        currentInspection = await createMutation.mutateAsync({
          asset_id: activeAsset.id,
          source,
          input_path: inputPath,
          notes: combinedNotes,
        })
      }

      // 2. Trigger vision pipeline if selected
      if (triggerVisionPipeline) {
        try {
          const runResult = await runMutation.mutateAsync(currentInspection.id)
          currentInspection = runResult
        } catch (err: unknown) {
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
    if (!completedInspection) return
    setRetryInspectionId(completedInspection.id)
    setSubmissionError(null)
    setStep(1)
  }

  // Handle Reassign / Associate with another Asset
  const handleReassignAsset = async (targetAssetId: string) => {
    if (!completedInspection) return
    const updated = await updateMutation.mutateAsync({
      id: completedInspection.id,
      data: { asset_id: targetAssetId },
    })
    setCompletedInspection(updated)
    const newAssignedAsset = assetsList.find((a) => a.id === targetAssetId)
    if (newAssignedAsset) {
      setSelectedAsset(newAssignedAsset)
    }
  }

  // Reset entire studio workflow
  const handleResetWorkflow = () => {
    setStep(1)
    setNotes('')
    setSelectedTags([])
    setMediaFile(null)
    setCompletedInspection(null)
    setSubmissionError(null)
    setRetryInspectionId(null)
  }

  return (
    <div className={styles.container}>
      <PageHeader
        title="Inspection Studio"
        description="Photo-first structural diagnostic pipeline: upload crack imagery, assign structure context, and execute vision AI."
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
            onClick={() => setStep(1)}
            disabled={step === 4 || isSubmitting}
          >
            <span className={styles.stepNumber}>{step > 1 ? '✓' : '1'}</span>
            <span>Upload Crack Photo</span>
          </button>

          <div className={styles.stepDivider} aria-hidden="true" />

          <button
            type="button"
            className={`${styles.stepItem} ${step === 2 ? styles.stepActive : ''} ${
              step > 2 ? styles.stepCompleted : ''
            }`}
            onClick={() => step > 2 && setStep(2)}
            disabled={step === 4 || !mediaFile || isSubmitting}
          >
            <span className={styles.stepNumber}>{step > 2 ? '✓' : '2'}</span>
            <span>Structure &amp; Context</span>
          </button>

          <div className={styles.stepDivider} aria-hidden="true" />

          <button
            type="button"
            className={`${styles.stepItem} ${step === 3 ? styles.stepActive : ''} ${
              step > 3 ? styles.stepCompleted : ''
            }`}
            onClick={() => step > 3 && setStep(3)}
            disabled={step === 4 || !mediaFile || isSubmitting}
          >
            <span className={styles.stepNumber}>{step > 3 ? '✓' : '3'}</span>
            <span>Review &amp; Run</span>
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

        {/* ── Step 1: Upload Crack Photograph (Photo-First) ── */}
        {step === 1 && (
          <div className={styles.workspace}>
            <div className={styles.stepCard}>
              <div className={styles.stepHeader}>
                <h2 className={styles.stepTitle}>Step 1: Upload Crack Photograph</h2>
                <p className={styles.stepSubtitle}>
                  Start by uploading or dropping a high-resolution photograph of the structural crack
                  or defect.
                </p>
              </div>

              <EvidenceUploader
                assetId={selectedAsset?.id}
                source={source}
                onChangeSource={setSource}
                notes={notes}
                onChangeNotes={setNotes}
                mediaFile={mediaFile}
                onSelectMediaFile={setMediaFile}
                selectedTags={selectedTags}
                onToggleTag={handleToggleTag}
              />

              <div className={styles.stepFooter}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  {mediaFile
                    ? `Staged: ${mediaFile.caption ?? 'Crack photo'} (${mediaFile.formattedSize})`
                    : 'Select or drop an image above to continue.'}
                </span>

                <Button
                  variant="primary"
                  disabled={!mediaFile}
                  onClick={() => setStep(2)}
                >
                  Configure Structure &amp; Context <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ── Step 2: Structure & Context (Optional / Flexible) ── */}
        {step === 2 && (
          <div className={styles.workspace}>
            <div className={styles.stepCard}>
              <div className={styles.stepHeader}>
                <h2 className={styles.stepTitle}>Step 2: Structural Asset Association</h2>
                <p className={styles.stepSubtitle}>
                  Optionally link this inspection to an existing registered civil structure, or provide a quick structure name.
                </p>
              </div>

              {/* Mode Switcher */}
              <div className={styles.modeTabs}>
                <button
                  type="button"
                  className={`${styles.modeTab} ${structureMode === 'quick' ? styles.modeTabActive : ''}`}
                  onClick={() => setStructureMode('quick')}
                >
                  <PlusCircle size={15} />
                  <span>Quick Structure Entry (Recommended)</span>
                </button>
                <button
                  type="button"
                  className={`${styles.modeTab} ${structureMode === 'existing' ? styles.modeTabActive : ''}`}
                  onClick={() => setStructureMode('existing')}
                >
                  <Layers size={15} />
                  <span>Select from Registered Assets ({assetsList.length})</span>
                </button>
              </div>

              {structureMode === 'quick' ? (
                <div className={styles.quickAssetCard}>
                  <div className={styles.quickAssetRow}>
                    <div>
                      <label className={styles.label} htmlFor="quick-struct-name">
                        Structure Name
                      </label>
                      <input
                        id="quick-struct-name"
                        type="text"
                        className={styles.input}
                        placeholder="e.g. College Block A or Highway Overpass"
                        value={quickName}
                        onChange={(e) => setQuickName(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className={styles.label} htmlFor="quick-struct-category">
                        Category
                      </label>
                      <select
                        id="quick-struct-category"
                        className={styles.select}
                        value={quickCategory}
                        onChange={(e) => setQuickCategory(e.target.value as AssetType)}
                      >
                        <option value="building">Building</option>
                        <option value="bridge">Bridge</option>
                        <option value="road">Road / Flyover</option>
                        <option value="tunnel">Tunnel</option>
                        <option value="dam">Dam</option>
                        <option value="other">Other Structure</option>
                      </select>
                    </div>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    An asset record will be automatically created with this name upon running the analysis. You can enrich engineering drawings or materials anytime later.
                  </span>
                </div>
              ) : (
                <AssetSelector
                  selectedAsset={selectedAsset}
                  onSelectAsset={(asset) => setSelectedAsset(asset)}
                />
              )}

              <div className={styles.stepFooter}>
                <Button variant="ghost" onClick={() => setStep(1)}>
                  <ArrowLeft size={16} /> Back to Photo
                </Button>

                <Button
                  variant="primary"
                  onClick={() => setStep(3)}
                >
                  Review &amp; Run Analysis <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ── Step 3: Review Before Submit ── */}
        {step === 3 && mediaFile && (
          <div className={styles.workspace}>
            <div className={styles.stepCard}>
              <div className={styles.stepHeader}>
                <h2 className={styles.stepTitle}>Step 3: Verification &amp; Pipeline Dispatch</h2>
                <p className={styles.stepSubtitle}>
                  Review the inspection parameters before sending the photographic bytes to Render
                  for automated computer vision defect segmentation.
                </p>
              </div>

              {submissionError && (
                <div
                  style={{
                    background: 'rgba(224, 86, 74, 0.1)',
                    border: '1px solid rgba(224, 86, 74, 0.4)',
                    color: '#ff8b80',
                    padding: '12px 16px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.875rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                  role="alert"
                >
                  <AlertCircle size={16} />
                  <span>{submissionError}</span>
                </div>
              )}

              <div className={styles.reviewGrid}>
                {/* Left: Media Information */}
                <div className={styles.reviewSection}>
                  <div className={styles.reviewSectionTitle}>
                    <UploadCloud size={14} /> Photographic Evidence
                  </div>
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                    <img
                      src={mediaFile.previewUrl}
                      alt="Staged evidence preview"
                      style={{
                        width: '96px',
                        height: '72px',
                        objectFit: 'cover',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-medium)',
                        background: '#000',
                      }}
                    />
                    <div className={styles.reviewFieldList}>
                      <div className={styles.reviewRow}>
                        <span className={styles.reviewLabel}>File Name</span>
                        <span className={styles.reviewValue}>
                          {mediaFile.caption ?? mediaFile.file?.name ?? 'Staged file'}
                        </span>
                      </div>
                      <div className={styles.reviewRow}>
                        <span className={styles.reviewLabel}>Resolution &amp; Size</span>
                        <span className={styles.reviewValue}>
                          {mediaFile.width && mediaFile.height
                            ? `${mediaFile.width} × ${mediaFile.height} px · ${mediaFile.formattedSize}`
                            : mediaFile.formattedSize}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right: Target Structure */}
                <div className={styles.reviewSection}>
                  <div className={styles.reviewSectionTitle}>
                    <Layers size={14} /> Target Structure &amp; Context
                  </div>
                  <div className={styles.reviewFieldList}>
                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Structure Name</span>
                      <span className={styles.reviewValue} style={{ fontWeight: 600 }}>
                        {selectedAsset
                          ? selectedAsset.name
                          : quickName.trim() || 'Monitored Structure'}
                      </span>
                    </div>
                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Category</span>
                      <span className={styles.reviewValue} style={{ textTransform: 'capitalize' }}>
                        {selectedAsset ? selectedAsset.asset_type : quickCategory}
                      </span>
                    </div>
                    <div className={styles.reviewRow}>
                      <span className={styles.reviewLabel}>Acquisition Modality</span>
                      <span className={styles.reviewValue} style={{ textTransform: 'capitalize' }}>
                        {source.replace('_', ' ')}
                      </span>
                    </div>
                    {selectedTags.length > 0 && (
                      <div className={styles.reviewRow}>
                        <span className={styles.reviewLabel}>Observed Tags</span>
                        <span className={styles.reviewValue}>{selectedTags.join(', ')}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Automated Execution Toggle */}
              <label className={styles.executionOption}>
                <input
                  type="checkbox"
                  checked={triggerVisionPipeline}
                  onChange={(e) => setTriggerVisionPipeline(e.target.checked)}
                />
                <div className={styles.executionText}>
                  <span className={styles.executionTitle}>
                    Execute Computer Vision Pipeline Immediately
                  </span>
                  <span className={styles.executionDesc}>
                    When enabled, the backend will immediately run defect segmentation and
                    structural health scoring against the uploaded photograph.
                  </span>
                </div>
              </label>

              <div className={styles.stepFooter}>
                <Button variant="ghost" onClick={() => setStep(2)} disabled={isSubmitting}>
                  <ArrowLeft size={16} /> Back to Structure Context
                </Button>

                <Button
                  variant="primary"
                  onClick={handleSubmitInspection}
                  disabled={isSubmitting}
                >
                  {isUploading ? (
                    <>
                      <Loader2 size={16} className="spin" /> Uploading Evidence Image…
                    </>
                  ) : runMutation.isPending ? (
                    <>
                      <Loader2 size={16} className="spin" /> Running Vision AI Pipeline…
                    </>
                  ) : isSubmitting ? (
                    <>
                      <Loader2 size={16} className="spin" /> Processing…
                    </>
                  ) : (
                    <>
                      <ScanLine size={16} /> Run Crack Analysis
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* ── Step 4: Diagnostic Findings & Actions ── */}
        {step === 4 && completedInspection && (
          <div className={styles.workspace}>
            <InspectionFindingsCard
              inspection={completedInspection}
              asset={
                selectedAsset ?? {
                  id: completedInspection.asset_id,
                  name: quickName.trim() || 'Monitored Structure',
                  asset_type: quickCategory,
                  status: 'active' as const,
                  location: null,
                  description: null,
                  construction_year: null,
                  material: null,
                  design_life_years: null,
                  latest_health_score: completedInspection.health_score,
                  created_at: completedInspection.created_at,
                  updated_at: completedInspection.updated_at,
                }
              }
              onReset={handleResetWorkflow}
              onRunVision={handleRunVisionPipelineOnCompleted}
              isRunningVision={runMutation.isPending}
              onRetryWithEvidence={handleRetryWithEvidence}
              onReassignAsset={handleReassignAsset}
              availableAssets={assetsList}
            />
          </div>
        )}

        {/* ── Asset Historical Inspection Ledger (Shown if existing asset selected) ── */}
        {selectedAsset && step < 4 && (
          <section className={styles.historySection} aria-label="Asset Historical Inspections">
            <div className={styles.historyHeader}>
              <div className={styles.historyTitle}>
                <History size={16} />
                <span>Historical Inspection Ledger ({selectedAsset.name})</span>
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {assetInspections?.length ?? 0} records
              </span>
            </div>

            {inspectionsLoading ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                Loading asset inspection ledger…
              </div>
            ) : !assetInspections || assetInspections.length === 0 ? (
              <EmptyState
                title="No prior inspections"
                description={`No inspection records have been registered for ${selectedAsset.name} yet.`}
              />
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className={styles.historyTable}>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Inspection ID</th>
                      <th>Modality</th>
                      <th>Defects</th>
                      <th>Health Score</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assetInspections.map((insp) => (
                      <tr key={insp.id}>
                        <td>{formatDate(insp.created_at)}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                          #{insp.id.slice(0, 8)}
                        </td>
                        <td style={{ textTransform: 'capitalize' }}>
                          {insp.source.replace('_', ' ')}
                        </td>
                        <td>{insp.defect_count}</td>
                        <td>
                          {insp.health_score !== null ? `${insp.health_score.toFixed(1)}/100` : '—'}
                        </td>
                        <td>
                          <StatusChip status={insp.status} size="sm" />
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
