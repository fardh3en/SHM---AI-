import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { UploadCloud, Layers, ScanLine, ArrowRight } from 'lucide-react'
import Button from '../../components/ui/Button'
import styles from './HeroInspectionAction.module.css'

interface HeroInspectionActionProps {
  onOpenAssetModal: () => void
}

export default function HeroInspectionAction({ onOpenAssetModal }: HeroInspectionActionProps) {
  const navigate = useNavigate()
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const handleFile = (file: File) => {
    // Navigate straight to inspections with the preloaded file in router state
    navigate('/inspections', { state: { preloadedFile: file } })
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

  return (
    <div className={styles.heroCard}>
      <div className={styles.topRow}>
        <div className={styles.titleArea}>
          <div className={styles.badgeRow}>
            <span className={styles.mainBadge}>
              <span className={styles.activeIndicator} />
              Primary AI Diagnostic Flow
            </span>
          </div>
          <h2 className={styles.heading}>
            Upload Crack Image &amp; Run AI Inspection
          </h2>
          <p className={styles.description}>
            Instant structural defect diagnosis. Drop a crack photograph or drone image to execute
            automated computer vision segmentation, bounding-box localization, and health scoring
            without lengthy setup.
          </p>
        </div>

        <div className={styles.actionsGroup}>
          <Button
            variant="primary"
            onClick={() => navigate('/inspections')}
          >
            <ScanLine size={16} /> Start Image Inspection <ArrowRight size={14} />
          </Button>

          <Button
            variant="secondary"
            onClick={onOpenAssetModal}
          >
            <Layers size={16} /> Register Asset (Secondary)
          </Button>
        </div>
      </div>

      {/* ── Direct Dropzone on Dashboard ── */}
      <div
        className={`${styles.dropzoneArea} ${isDragOver ? styles.dropzoneActive : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragOver(true)
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Upload crack image directly from dashboard"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp,.tif,.tiff"
          className={styles.hiddenInput}
          onChange={handleInputChange}
        />
        <div className={styles.dropzoneIconWrap}>
          <UploadCloud size={20} />
        </div>
        <div className={styles.dropzoneText}>
          <span className={styles.dropzoneTitle}>
            Drag &amp; drop a crack photograph right here to analyze immediately
          </span>
          <span className={styles.dropzoneSub}>
            or click to browse local files (JPG, PNG, WebP · up to 25 MB)
          </span>
        </div>
      </div>
    </div>
  )
}
