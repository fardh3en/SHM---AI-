import { useState, useRef, useEffect } from 'react'
import {
  UploadCloud,
  Trash2,
  AlertCircle,
  Camera,
  Check,
} from 'lucide-react'
import type { InspectionSource } from '../../api/inspections'
import { useAssetEvidence } from '../../hooks/useAssetEvidence'
import type { AssetEvidence } from '../../api/evidence'
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
}

const SOURCES: { value: InspectionSource; label: string; desc: string }[] = [
  { value: 'image', label: 'Field Photography', desc: 'Direct high-resolution visual capture' },
  { value: 'drone', label: 'UAV / Drone Survey', desc: 'Aerial inspection and photogrammetry' },
  { value: 'manual', label: 'Manual Observation', desc: 'Human structural engineer on-site notes' },
  { value: 'camera_feed', label: 'Fixed Camera Feed', desc: 'Continuous stationary surveillance frame' },
  { value: 'video', label: 'Video Footage', desc: 'Motion recording or borescopic survey' },
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
}: EvidenceUploaderProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'archive' | 'upload'>('archive')
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Fetch asset archived visual evidence
  const { data: archivedEvidence, isLoading: isEvidenceLoading } = useAssetEvidence(assetId)

  // Revoke object URL on unmount if it was created locally from a File object
  useEffect(() => {
    return () => {
      if (mediaFile?.file && mediaFile.previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(mediaFile.previewUrl)
      }
    }
  }, [mediaFile])

  // If asset has no archived evidence, default tab to upload
  useEffect(() => {
    if (archivedEvidence && archivedEvidence.length === 0 && activeTab === 'archive') {
      setActiveTab('upload')
    }
  }, [archivedEvidence, activeTab])

  // Select an archived evidence image
  const handleSelectArchived = (ev: AssetEvidence) => {
    onSelectMediaFile({
      file: undefined,
      previewUrl: ev.file_path,
      formattedSize: 'Archived',
      isSampleEvidence: true,
      sampleEvidenceId: ev.id,
      caption: ev.caption,
      classification: ev.classification,
    })
    setValidationError(null)
  }

  // Handle local file validation & staging
  const handleFile = (file: File) => {
    setValidationError(null)

    if (!ACCEPTED_TYPES.includes(file.type)) {
      setValidationError(
        `Unsupported file type (${file.type || 'unknown'}). Supported: JPEG, PNG, WebP, TIFF.`
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

  const archiveCount = archivedEvidence?.length ?? 0

  return (
    <div className={styles.container}>
      {/* ── Mode Selection Tab Bar ── */}
      <div className={styles.tabBar}>
        <button
          type="button"
          className={`${styles.tabBtn} ${activeTab === 'archive' ? styles.tabBtnActive : ''}`}
          onClick={() => setActiveTab('archive')}
        >
          <Camera size={14} />
          <span>Asset Evidence Archive ({isEvidenceLoading ? '…' : archiveCount})</span>
        </button>

        <button
          type="button"
          className={`${styles.tabBtn} ${activeTab === 'upload' ? styles.tabBtnActive : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          <UploadCloud size={14} />
          <span>Upload Local File</span>
        </button>
      </div>

      {/* ── Tab 1: Archived Asset Evidence ── */}
      {activeTab === 'archive' && (
        <div>
          {isEvidenceLoading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', padding: '12px' }}>
              Loading archived structural evidence...
            </div>
          ) : archiveCount === 0 ? (
            <div
              style={{
                padding: '24px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: '0.875rem',
                border: '1px dashed var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
              }}
            >
              No archived evidence photographs available for this asset. Switch to "Upload Local File" to ingest a new image.
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
                    onClick={() => handleSelectArchived(ev)}
                    role="button"
                    tabIndex={0}
                  >
                    <div className={styles.archiveThumbWrap}>
                      <img
                        src={ev.file_path}
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

      {/* ── Tab 2: Upload New Local File ── */}
      {activeTab === 'upload' && !mediaFile && (
        <div
          className={`${styles.dropzone} ${isDragOver ? styles.dropzoneActive : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragOver(true)
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.webp,.tif,.tiff"
            className={styles.hiddenInput}
            onChange={handleInputChange}
          />
          <div className={styles.uploadIconWrap}>
            <UploadCloud size={24} />
          </div>
          <div className={styles.dropTitle}>Drag and drop structural photograph here</div>
          <div className={styles.dropSub}>or click to browse local files</div>
          <div className={styles.dropLimit}>
            Supported: JPEG, PNG, WebP, TIFF · Max single file: 25 MB
          </div>
        </div>
      )}

      {/* ── Active Staged Media Preview Card ── */}
      {mediaFile && (
        <div className={styles.previewCard}>
          <div className={styles.previewLeft}>
            <img
              src={mediaFile.previewUrl}
              alt={mediaFile.caption ?? 'Evidence preview'}
              className={styles.thumbImg}
            />
            <div className={styles.fileInfo}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className={styles.fileName}>
                  {mediaFile.caption ?? (mediaFile.file ? mediaFile.file.name : 'Staged Evidence')}
                </span>
                {mediaFile.isSampleEvidence ? (
                  <span className={styles.samplePill}>Archived Evidence</span>
                ) : (
                  <span className={styles.userUploadPill}>Local Upload</span>
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

          <button
            type="button"
            className={styles.removeBtn}
            onClick={handleRemove}
            title="Remove staged evidence"
          >
            <Trash2 size={13} />
            <span>Remove</span>
          </button>
        </div>
      )}

      {/* Validation Error Banner */}
      {validationError && (
        <div className={styles.errorBanner} role="alert">
          <AlertCircle size={15} style={{ flexShrink: 0 }} />
          <span>{validationError}</span>
        </div>
      )}

      {/* ── Capture Parameters & Field Notes Form ── */}
      <div className={styles.formGrid}>
        <div className={styles.field}>
          <label htmlFor="inspection-source-select" className={styles.label}>
            Data Acquisition Modality / Source
          </label>
          <select
            id="inspection-source-select"
            className={styles.select}
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

        <div className={`${styles.field} ${styles.fullWidth}`}>
          <label htmlFor="inspection-notes-input" className={styles.label}>
            Inspector / Field Observations &amp; Context Notes
          </label>
          <textarea
            id="inspection-notes-input"
            className={styles.textarea}
            placeholder="Record ambient weather, structural joint condition, crack morphology, or operational notes..."
            value={notes}
            onChange={(e) => onChangeNotes(e.target.value)}
          />
        </div>
      </div>
    </div>
  )
}
