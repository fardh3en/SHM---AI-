import { useState, useRef } from 'react'
import {
  UploadCloud,
  Trash2,
  AlertCircle,
  Camera,
  Check,
  RefreshCw,
  Info,
  CheckCircle2,
  FolderOpen,
} from 'lucide-react'
import type { InspectionSource } from '../../api/inspections'
import { useAssetEvidence } from '../../hooks/useAssetEvidence'
import type { AssetEvidence } from '../../api/evidence'
import { resolveMediaUrl } from '../../api/client'
import styles from './EvidenceUploader.module.css'

export interface SelectedMediaFile {
  file?: File
  previewUrl: string
  width?: number
  height?: number
  formattedSize: string
  isSampleEvidence?: boolean
  sampleEvidenceId?: string
  caption?: string
  classification?: string
}

interface EvidenceUploaderProps {
  assetId?: string
  source: InspectionSource
  onChangeSource: (source: InspectionSource) => void
  notes: string
  onChangeNotes: (notes: string) => void
  mediaFile: SelectedMediaFile | null
  onSelectMediaFile: (media: SelectedMediaFile | null) => void
  selectedTags?: string[]
  onToggleTag?: (tag: string) => void
}

const SOURCES: { value: InspectionSource; label: string; desc: string }[] = [
  { value: 'image', label: 'Field Photography', desc: 'Standard direct high-resolution visual capture' },
  { value: 'drone', label: 'UAV / Drone Survey', desc: 'Aerial photogrammetry' },
  { value: 'manual', label: 'Manual Observation', desc: 'On-site visual engineering observation' },
  { value: 'camera_feed', label: 'Fixed Camera Feed', desc: 'Stationary monitoring feed' },
  { value: 'video', label: 'Video Footage', desc: 'Motion recording or borescope' },
]

const QUICK_OBSERVATION_TAGS = [
  'Hairline crack (<1mm)',
  'Wide crack (>2mm)',
  'Surface spalling',
  'Water seepage / dampness',
  'Rust discoloration',
  'Concrete scaling',
]

const MAX_BYTES = 25 * 1024 * 1024 // 25 MB
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/tiff']

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export default function EvidenceUploader({
  assetId,
  source,
  onChangeSource,
  notes,
  onChangeNotes,
  mediaFile,
  onSelectMediaFile,
  selectedTags = [],
  onToggleTag,
}: EvidenceUploaderProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [showArchive, setShowArchive] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Fetch asset archived visual evidence if assetId is set
  const { data: archivedEvidence, isLoading: isEvidenceLoading } = useAssetEvidence(assetId)

  // Select an archived evidence image
  const handleSelectArchived = (ev: AssetEvidence) => {
    onSelectMediaFile({
      file: undefined,
      previewUrl: ev.file_path,
      formattedSize: 'Archived File',
      isSampleEvidence: true,
      sampleEvidenceId: ev.id,
      caption: ev.caption,
      classification: ev.classification,
    })
    setValidationError(null)
    setShowArchive(false)
  }

  // Handle local file validation & staging
  const handleFile = (file: File) => {
    setValidationError(null)

    if (mediaFile?.file && mediaFile.previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(mediaFile.previewUrl)
    }

    if (!ACCEPTED_TYPES.includes(file.type)) {
      setValidationError(
        `Unsupported file format (${file.type || 'unknown'}). Supported formats: JPG, PNG, WebP, TIFF.`
      )
      return
    }

    if (file.size > MAX_BYTES) {
      setValidationError(
        `File exceeds maximum limit of 25 MB. Selected file size: ${formatBytes(file.size)}.`
      )
      return
    }

    const objectUrl = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      onSelectMediaFile({
        file,
        previewUrl: objectUrl,
        width: img.naturalWidth,
        height: img.naturalHeight,
        formattedSize: formatBytes(file.size),
        isSampleEvidence: false,
        caption: file.name,
      })
    }
    img.onerror = () => {
      onSelectMediaFile({
        file,
        previewUrl: objectUrl,
        formattedSize: formatBytes(file.size),
        isSampleEvidence: false,
        caption: file.name,
      })
    }
    img.src = objectUrl
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  const handleRemove = () => {
    if (mediaFile?.file && mediaFile.previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(mediaFile.previewUrl)
    }
    onSelectMediaFile(null)
    setValidationError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleReplace = () => {
    fileInputRef.current?.click()
  }

  const archiveCount = archivedEvidence?.length ?? 0

  return (
    <div className={styles.container}>
      {/* ── Single Hidden File Input (controlled via ref by dropzone, chooseBtn, and replaceBtn) ── */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.tif,.tiff"
        className={styles.hiddenInput}
        style={{ display: 'none' }}
        onChange={handleInputChange}
        tabIndex={-1}
        aria-hidden="true"
        data-testid="evidence-file-input"
      />

      {/* ── Guidance Tip ── */}
      <div className={styles.tipBox} role="note">
        <Info size={16} style={{ flexShrink: 0, color: 'var(--color-mineral)' }} />
        <span>
          <strong>Tip for best AI accuracy:</strong> A clear, focused, and well-lit photograph perpendicular to the crack works best for automated segmentation.
        </span>
      </div>

      {/* ── Prominent Drag & Drop Zone (Shown when no media staged) ── */}
      {!mediaFile && (
        <div
          className={`${styles.dropzone} ${isDragOver ? styles.dropzoneActive : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragOver(true)
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              fileInputRef.current?.click()
            }
          }}
          role="button"
          tabIndex={0}
          aria-label="Upload structural crack image"
          data-testid="dropzone-area"
        >
          <div className={styles.uploadIconWrap}>
            <UploadCloud size={24} />
          </div>
          <div className={styles.dropTitle}>Drag &amp; drop crack photograph here</div>
          <div className={styles.dropSub}>or click to browse from your device</div>
          <button
            type="button"
            className={styles.chooseBtn}
            onClick={(e) => {
              e.stopPropagation()
              fileInputRef.current?.click()
            }}
            data-testid="choose-image-btn"
          >
            <FolderOpen size={15} />
            <span>Choose Image</span>
          </button>
          <div className={styles.dropLimit}>
            Supported: JPEG, PNG, WebP, TIFF · Maximum file size: 25 MB
          </div>
        </div>
      )}

      {/* ── Active Staged Media Preview Card ── */}
      {mediaFile && (
        <div className={styles.previewCard} data-testid="staged-preview-card">
          <div className={styles.previewLeft}>
            <img
              src={mediaFile.previewUrl}
              alt={mediaFile.caption ?? 'Evidence preview'}
              className={styles.thumbImg}
            />
            <div className={styles.fileInfo}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span className={styles.fileName}>
                  {mediaFile.caption ?? (mediaFile.file ? mediaFile.file.name : 'Staged Evidence')}
                </span>
                <span className={styles.validationBadge}>
                  <CheckCircle2 size={12} /> Format &amp; Size Validated
                </span>
                {mediaFile.isSampleEvidence && (
                  <span className={styles.samplePill}>Archived Evidence</span>
                )}
              </div>
              <div className={styles.fileMeta}>
                <span>{mediaFile.formattedSize}</span>
                {mediaFile.width && mediaFile.height && (
                  <>
                    <span className={styles.metaSep}>·</span>
                    <span>{mediaFile.width} × {mediaFile.height} px</span>
                  </>
                )}
                {mediaFile.classification && (
                  <>
                    <span className={styles.metaSep}>·</span>
                    <span style={{ textTransform: 'capitalize' }}>
                      {mediaFile.classification.replace('_', ' ')}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className={styles.previewActions}>
            <button
              type="button"
              className={styles.replaceBtn}
              onClick={(e) => {
                e.stopPropagation()
                handleReplace()
              }}
              title="Replace current image with another file"
              data-testid="replace-image-btn"
            >
              <RefreshCw size={13} />
              <span>Replace</span>
            </button>
            <button
              type="button"
              className={styles.removeBtn}
              onClick={(e) => {
                e.stopPropagation()
                handleRemove()
              }}
              title="Remove staged evidence"
              data-testid="remove-image-btn"
            >
              <Trash2 size={13} />
              <span>Remove</span>
            </button>
          </div>
        </div>
      )}

      {/* Validation Error Banner */}
      {validationError && (
        <div className={styles.errorBanner} role="alert">
          <AlertCircle size={15} style={{ flexShrink: 0 }} />
          <span>{validationError}</span>
        </div>
      )}

      {/* ── Optional Archive Gallery Drawer (if asset has archived images) ── */}
      {assetId && archiveCount > 0 && (
        <div style={{ marginTop: '2px' }} onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            className={styles.replaceBtn}
            onClick={(e) => {
              e.stopPropagation()
              setShowArchive((prev) => !prev)
            }}
            style={{ fontSize: '0.75rem', padding: '4px 10px' }}
          >
            <Camera size={13} />
            <span>
              {showArchive
                ? 'Hide Archived Evidence Photos'
                : `Or select from asset evidence archive (${archiveCount} photos)`}
            </span>
          </button>

          {showArchive && (
            <div style={{ marginTop: '8px' }}>
              {isEvidenceLoading ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                  Loading archived structural photos...
                </div>
              ) : (
                <div className={styles.archiveGrid}>
                  {archivedEvidence?.map((ev) => {
                    const isSelected =
                      mediaFile?.previewUrl === ev.file_path ||
                      mediaFile?.sampleEvidenceId === ev.id

                    return (
                      <div
                        key={ev.id}
                        className={`${styles.archiveCard} ${
                          isSelected ? styles.archiveCardSelected : ''
                        }`}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleSelectArchived(ev)
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            e.stopPropagation()
                            handleSelectArchived(ev)
                          }
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <div className={styles.archiveThumbWrap}>
                          <img
                            src={resolveMediaUrl(ev.file_path)}
                            alt={ev.caption}
                            className={styles.archiveThumb}
                            loading="lazy"
                          />
                          {isSelected && (
                            <div className={styles.archiveCheck}>
                              <Check size={12} />
                            </div>
                          )}
                        </div>
                        <div className={styles.archiveBody}>
                          <span className={styles.archiveCaption} title={ev.caption}>
                            {ev.caption}
                          </span>
                          <span className={styles.archiveMeta}>
                            {ev.classification.replace('_', ' ').toUpperCase()}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Quick-Select Observation Tags ── */}
      {onToggleTag && (
        <div className={styles.field} style={{ marginTop: '4px' }}>
          <span className={styles.label} id="observation-tags-heading">
            Quick Field Observation Tags (Optional)
          </span>
          <div
            className={styles.tagList}
            role="group"
            aria-labelledby="observation-tags-heading"
          >
            {QUICK_OBSERVATION_TAGS.map((tag) => {
              const isSelected = selectedTags.includes(tag)
              return (
                <button
                  key={tag}
                  type="button"
                  className={`${styles.tagBtn} ${isSelected ? styles.tagBtnSelected : ''}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleTag(tag)
                  }}
                  aria-pressed={isSelected}
                  data-testid={`tag-${tag.replace(/[^a-zA-Z0-9]/g, '-').toLowerCase()}`}
                >
                  {isSelected ? `✓ ${tag}` : `+ ${tag}`}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Field Notes ── */}
      <div className={styles.field} onClick={(e) => e.stopPropagation()}>
        <label htmlFor="inspection-notes-input" className={styles.label}>
          Field Observations / Context Notes (Optional)
        </label>
        <textarea
          id="inspection-notes-input"
          className={styles.textarea}
          placeholder="e.g. South abutment wall, 2 meters above ground level, damp surface condition..."
          rows={2}
          value={notes}
          onChange={(e) => onChangeNotes(e.target.value)}
          onClick={(e) => e.stopPropagation()}
        />
      </div>

      {/* ── Collapsible Advanced Options ── */}
      <details className={styles.advancedDetails}>
        <summary
          className={styles.advancedSummary}
          onClick={(e) => e.stopPropagation()}
          data-testid="advanced-params-summary"
        >
          Advanced Ingestion Parameters (Acquisition Modality)
        </summary>
        <div style={{ marginTop: '12px' }} onClick={(e) => e.stopPropagation()}>
          <label htmlFor="inspection-source-select" className={styles.label}>
            Capture Acquisition Modality
          </label>
          <select
            id="inspection-source-select"
            className={styles.select}
            style={{ marginTop: '4px' }}
            value={source}
            onChange={(e) => onChangeSource(e.target.value as InspectionSource)}
          >
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label} ({s.desc})
              </option>
            ))}
          </select>
        </div>
      </details>
    </div>
  )
}
