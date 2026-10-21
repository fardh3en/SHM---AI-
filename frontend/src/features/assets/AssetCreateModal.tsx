import { useState, useEffect } from 'react'
import { X, AlertCircle } from 'lucide-react'
import Button from '../../components/ui/Button'
import { useCreateAsset } from '../../hooks/useAssets'
import type { AssetType, AssetCreate } from '../../api/assets'
import styles from './AssetCreateModal.module.css'

interface AssetCreateModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: (createdId: string) => void
}

const ASSET_TYPES: { value: AssetType; label: string }[] = [
  { value: 'bridge', label: 'Bridge' },
  { value: 'building', label: 'Building' },
  { value: 'tunnel', label: 'Tunnel' },
  { value: 'road', label: 'Road / Flyover' },
  { value: 'dam', label: 'Dam / Reservoir' },
  { value: 'pipeline', label: 'Pipeline' },
  { value: 'other', label: 'Other Structure' },
]

export default function AssetCreateModal({ isOpen, onClose, onSuccess }: AssetCreateModalProps) {
  const createMutation = useCreateAsset()

  const [name, setName] = useState('')
  const [assetType, setAssetType] = useState<AssetType>('bridge')
  const [location, setLocation] = useState('')
  const [material, setMaterial] = useState('')
  const [constructionYear, setConstructionYear] = useState('')
  const [designLifeYears, setDesignLifeYears] = useState('')
  const [description, setDescription] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setName('')
      setAssetType('bridge')
      setLocation('')
      setMaterial('')
      setConstructionYear('')
      setDesignLifeYears('')
      setDescription('')
      setErrorMessage(null)
    }
  }, [isOpen])

  // Close on ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!name.trim()) {
      setErrorMessage('Asset name is required.')
      return
    }

    const payload: AssetCreate = {
      name: name.trim(),
      asset_type: assetType,
      location: location.trim() || undefined,
      material: material.trim() || undefined,
      description: description.trim() || undefined,
      construction_year: constructionYear ? parseInt(constructionYear, 10) : undefined,
      design_life_years: designLifeYears ? parseFloat(designLifeYears) : undefined,
    }

    try {
      const created = await createMutation.mutateAsync(payload)
      onSuccess?.(created.id)
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to register structural asset.'
      setErrorMessage(msg)
    }
  }

  return (
    <div className={styles.overlay} onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div>
            <h2 id="modal-title" className={styles.headerTitle}>Register Structural Asset</h2>
            <p className={styles.headerSub}>Add a new physical civil structure to the active monitoring registry.</p>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close dialog">
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit}>
          <div className={styles.body}>
            {errorMessage && (
              <div className={styles.errorBanner} role="alert">
                <AlertCircle size={16} />
                <span>{errorMessage}</span>
              </div>
            )}

            <div className={styles.formGrid}>
              <div className={[styles.field, styles.fullWidth].join(' ')}>
                <label className={styles.label} htmlFor="asset-name">
                  Structure Name<span className={styles.req}>*</span>
                </label>
                <input
                  id="asset-name"
                  type="text"
                  className={styles.input}
                  placeholder="e.g. Forth Road Bridge North Pier"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  autoFocus
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="asset-type">Asset Category</label>
                <select
                  id="asset-type"
                  className={styles.select}
                  value={assetType}
                  onChange={(e) => setAssetType(e.target.value as AssetType)}
                >
                  {ASSET_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="asset-material">Primary Material</label>
                <input
                  id="asset-material"
                  type="text"
                  className={styles.input}
                  placeholder="e.g. Reinforced Concrete"
                  value={material}
                  onChange={(e) => setMaterial(e.target.value)}
                />
              </div>

              <div className={[styles.field, styles.fullWidth].join(' ')}>
                <label className={styles.label} htmlFor="asset-location">Location / Coordinates</label>
                <input
                  id="asset-location"
                  type="text"
                  className={styles.input}
                  placeholder="e.g. 55.9984° N, 3.4056° W or Queensferry, Edinburgh"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="asset-year">Construction Year</label>
                <input
                  id="asset-year"
                  type="number"
                  min="1800"
                  max="2100"
                  className={styles.input}
                  placeholder="e.g. 1964"
                  value={constructionYear}
                  onChange={(e) => setConstructionYear(e.target.value)}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label} htmlFor="asset-life">Design Life (Years)</label>
                <input
                  id="asset-life"
                  type="number"
                  step="0.5"
                  min="1"
                  className={styles.input}
                  placeholder="e.g. 100"
                  value={designLifeYears}
                  onChange={(e) => setDesignLifeYears(e.target.value)}
                />
              </div>

              <div className={[styles.field, styles.fullWidth].join(' ')}>
                <label className={styles.label} htmlFor="asset-desc">Engineering Description</label>
                <textarea
                  id="asset-desc"
                  className={styles.textarea}
                  rows={3}
                  placeholder="Structural context, environmental exposure class, or special maintenance considerations..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Footer actions */}
          <div className={styles.footer}>
            <Button type="button" variant="ghost" size="sm" onClick={onClose} disabled={createMutation.isPending}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Registering…' : 'Register Asset'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
