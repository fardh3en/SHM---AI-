import { useState, useEffect } from 'react'
import { X, AlertCircle, MapPin, Loader2 } from 'lucide-react'
import Button from '../../components/ui/Button'
import { useCreateAsset } from '../../hooks/useAssets'
import type { AssetType, AssetCreate } from '../../api/assets'
import styles from './AssetCreateModal.module.css'

interface AssetCreateModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: (createdId: string) => void
}

/**
 * Friendly structural categories mapped to backend AssetType enums.
 */
interface CategoryOption {
  id: string
  label: string
  backendType: AssetType
}

const CATEGORY_OPTIONS: CategoryOption[] = [
  { id: 'building', label: 'Building', backendType: 'building' },
  { id: 'bridge', label: 'Bridge', backendType: 'bridge' },
  { id: 'road', label: 'Road', backendType: 'road' },
  { id: 'tunnel', label: 'Tunnel', backendType: 'tunnel' },
  { id: 'dam', label: 'Dam', backendType: 'dam' },
  { id: 'retaining_wall', label: 'Retaining Wall', backendType: 'other' },
  { id: 'industrial', label: 'Industrial Structure', backendType: 'other' },
  { id: 'other', label: 'Other', backendType: 'other' },
]

/**
 * Standard civil engineering material options.
 */
const MATERIAL_OPTIONS = [
  'Reinforced Concrete',
  'Plain Concrete',
  'Steel',
  'Brick / Masonry',
  'Stone Masonry',
  'Prestressed Concrete',
  'Composite Steel–Concrete',
  'Timber / Wood',
  'Asphalt / Bituminous Material',
  'Earth / Soil',
  'Other',
  'Unknown / Not Sure',
]

/**
 * Quick observation tags for structural condition.
 */
const OBSERVATION_TAGS = [
  'Visible crack',
  'Surface damage / spalling',
  'Water leakage / dampness',
  'Rust staining',
  'Concrete deterioration',
  'Unknown condition',
]

export default function AssetCreateModal({ isOpen, onClose, onSuccess }: AssetCreateModalProps) {
  const createMutation = useCreateAsset()

  // Form states
  const [name, setName] = useState('')
  const [category, setCategory] = useState<string>('building')
  const [materialChoice, setMaterialChoice] = useState<string>('Reinforced Concrete')
  const [customMaterial, setCustomMaterial] = useState<string>('')
  const [location, setLocation] = useState<string>('')
  const [constructionYear, setConstructionYear] = useState<string>('')
  const [designLifeYears, setDesignLifeYears] = useState<string>('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [userNotes, setUserNotes] = useState<string>('')

  // Geolocation helper state
  const [isLocating, setIsLocating] = useState<boolean>(false)
  const [locationStatus, setLocationStatus] = useState<string | null>(null)

  // Validation & Error states
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [yearError, setYearError] = useState<string | null>(null)

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setName('')
      setCategory('building')
      setMaterialChoice('Reinforced Concrete')
      setCustomMaterial('')
      setLocation('')
      setConstructionYear('')
      setDesignLifeYears('')
      setSelectedTags([])
      setUserNotes('')
      setIsLocating(false)
      setLocationStatus(null)
      setErrorMessage(null)
      setYearError(null)
    }
  }, [isOpen])

  // Close on ESC key
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

  // Geolocation trigger
  const handleUseCurrentLocation = () => {
    if (!('geolocation' in navigator)) {
      setLocationStatus('Geolocation is not supported by your browser.')
      return
    }

    setIsLocating(true)
    setLocationStatus('Acquiring browser coordinates…')

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false)
        const lat = pos.coords.latitude.toFixed(5)
        const lon = pos.coords.longitude.toFixed(5)
        const locString = `${lat}° N, ${lon}° E (Browser Geolocation)`
        setLocation(locString)
        setLocationStatus('Coordinates acquired.')
      },
      (err) => {
        setIsLocating(false)
        if (err.code === err.PERMISSION_DENIED) {
          setLocationStatus('Location access permission was denied. You may enter a landmark manually.')
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setLocationStatus('Location information unavailable. You may enter a landmark manually.')
        } else {
          setLocationStatus('Could not determine location. Please enter address manually.')
        }
      },
      { timeout: 10000, enableHighAccuracy: true }
    )
  }

  // Toggle observation tags
  const handleToggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    )
  }

  const handleYearChange = (val: string) => {
    setConstructionYear(val)
    if (!val) {
      setYearError(null)
      return
    }
    const num = parseInt(val, 10)
    if (isNaN(num) || num < 1800 || num > 2100) {
      setYearError('Year must be between 1800 and 2100, or leave blank.')
    } else {
      setYearError(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!name.trim()) {
      setErrorMessage('Structure name is required.')
      return
    }

    if (yearError) {
      setErrorMessage('Please correct the construction year before submitting.')
      return
    }

    // Map category to backend AssetType
    const matchedCategory = CATEGORY_OPTIONS.find((c) => c.id === category)
    const backendAssetType = matchedCategory?.backendType ?? 'other'

    // Determine material string
    let resolvedMaterial: string | undefined = undefined
    if (materialChoice === 'Other') {
      resolvedMaterial = customMaterial.trim() || undefined
    } else if (materialChoice !== 'Unknown / Not Sure') {
      resolvedMaterial = materialChoice
    }

    // Synthesize engineering description from observation tags + notes
    const descParts: string[] = []
    if (category === 'retaining_wall') descParts.push('Structure category: Retaining Wall')
    if (category === 'industrial') descParts.push('Structure category: Industrial Structure')
    if (selectedTags.length > 0) {
      descParts.push(`Field observations: ${selectedTags.join(', ')}`)
    }
    if (userNotes.trim()) {
      descParts.push(`Inspector notes: ${userNotes.trim()}`)
    }
    const finalDescription = descParts.length > 0 ? descParts.join(' | ') : undefined

    const payload: AssetCreate = {
      name: name.trim(),
      asset_type: backendAssetType,
      location: location.trim() || undefined,
      material: resolvedMaterial,
      description: finalDescription,
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
    <div
      className={styles.overlay}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div>
            <h2 id="modal-title" className={styles.headerTitle}>
              Register Structural Asset
            </h2>
            <p className={styles.headerSub}>
              Add a monitored structure. Only the structure name is required to get started.
            </p>
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
              {/* Structure Name (Required) */}
              <div className={[styles.field, styles.fullWidth].join(' ')}>
                <label className={styles.label} htmlFor="asset-name">
                  Structure Name<span className={styles.req}>*</span>
                </label>
                <input
                  id="asset-name"
                  type="text"
                  className={styles.input}
                  placeholder="e.g. College Block A or Apartment Building"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  autoFocus
                />
                <span className={styles.fieldHint}>
                  Enter a familiar name for the building, bridge, or civil structure.
                </span>
              </div>

              {/* Asset Category */}
              <div className={styles.field}>
                <label className={styles.label} htmlFor="asset-category">
                  Asset Category
                </label>
                <select
                  id="asset-category"
                  className={styles.select}
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  {CATEGORY_OPTIONS.map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Primary Material */}
              <div className={styles.field}>
                <label className={styles.label} htmlFor="asset-material">
                  Primary Material
                </label>
                <select
                  id="asset-material"
                  className={styles.select}
                  value={materialChoice}
                  onChange={(e) => setMaterialChoice(e.target.value)}
                >
                  {MATERIAL_OPTIONS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                {materialChoice === 'Other' && (
                  <input
                    type="text"
                    className={styles.input}
                    style={{ marginTop: '6px' }}
                    placeholder="Specify material (e.g. Fiber-Reinforced Polymer)"
                    value={customMaterial}
                    onChange={(e) => setCustomMaterial(e.target.value)}
                  />
                )}
                <span className={styles.fieldHint}>
                  Select &apos;Unknown / Not Sure&apos; if structural drawings are unconfirmed.
                </span>
              </div>

              {/* Location & GPS Assistance */}
              <div className={[styles.field, styles.fullWidth].join(' ')}>
                <label className={styles.label} htmlFor="asset-location">
                  Location / Landmark <span className={styles.optionalBadge}>(Optional)</span>
                </label>
                <div className={styles.locationRow}>
                  <input
                    id="asset-location"
                    type="text"
                    className={styles.input}
                    placeholder="e.g. North Campus Quad, Sector 4 Ring Road, or Edinburgh"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                  />
                  <button
                    type="button"
                    className={styles.locBtn}
                    onClick={handleUseCurrentLocation}
                    disabled={isLocating}
                    title="Attempt browser geolocation to record coordinates"
                  >
                    {isLocating ? <Loader2 size={14} className="spin" /> : <MapPin size={14} />}
                    <span>Use My Location</span>
                  </button>
                </div>
                {locationStatus && (
                  <span
                    className={[
                      styles.locStatus,
                      locationStatus.toLowerCase().includes('denied') ||
                      locationStatus.toLowerCase().includes('unavailable')
                        ? styles.locStatusWarning
                        : '',
                    ].join(' ')}
                  >
                    {locationStatus}
                  </span>
                )}
                <span className={styles.fieldHint}>
                  Accepts a human-readable address, building name, or GPS coordinates.
                </span>
              </div>

              {/* Construction Year */}
              <div className={styles.field}>
                <label className={styles.label} htmlFor="asset-year">
                  Construction Year <span className={styles.optionalBadge}>(Optional)</span>
                </label>
                <input
                  id="asset-year"
                  type="number"
                  min="1800"
                  max="2100"
                  className={styles.input}
                  placeholder="e.g. 1998 (leave blank if unknown)"
                  value={constructionYear}
                  onChange={(e) => handleYearChange(e.target.value)}
                />
                {yearError ? (
                  <span className={[styles.fieldHint, styles.locStatusWarning].join(' ')}>
                    {yearError}
                  </span>
                ) : (
                  <span className={styles.fieldHint}>Leave blank if unknown.</span>
                )}
              </div>

              {/* Expected Service Life */}
              <div className={styles.field}>
                <label className={styles.label} htmlFor="asset-life">
                  Expected service life (years) <span className={styles.optionalBadge}>(Optional)</span>
                </label>
                <input
                  id="asset-life"
                  type="number"
                  step="1"
                  min="1"
                  className={styles.input}
                  placeholder="e.g. 50 (engineering estimate)"
                  value={designLifeYears}
                  onChange={(e) => setDesignLifeYears(e.target.value)}
                />
                <span className={styles.fieldHint}>
                  Engineering assumption or design estimate, not verified telemetry.
                </span>
              </div>

              {/* Field Observations / Condition Tags */}
              <div className={[styles.field, styles.fullWidth].join(' ')}>
                <label className={styles.label}>
                  Field Observations <span className={styles.optionalBadge}>(Optional tags)</span>
                </label>
                <div className={styles.tagList}>
                  {OBSERVATION_TAGS.map((tag) => {
                    const isSelected = selectedTags.includes(tag)
                    return (
                      <button
                        key={tag}
                        type="button"
                        className={`${styles.tagBtn} ${isSelected ? styles.tagBtnSelected : ''}`}
                        onClick={() => handleToggleTag(tag)}
                        aria-pressed={isSelected}
                      >
                        {isSelected ? `✓ ${tag}` : `+ ${tag}`}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Optional Notes */}
              <div className={[styles.field, styles.fullWidth].join(' ')}>
                <label className={styles.label} htmlFor="asset-notes">
                  Anything else you noticed? <span className={styles.optionalBadge}>(Optional notes)</span>
                </label>
                <textarea
                  id="asset-notes"
                  className={styles.textarea}
                  rows={2}
                  placeholder="e.g. Observed on second floor exterior beam after recent weather exposure..."
                  value={userNotes}
                  onChange={(e) => setUserNotes(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Footer Actions */}
          <div className={styles.footer}>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onClose}
              disabled={createMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={createMutation.isPending || !!yearError}
            >
              {createMutation.isPending ? 'Registering…' : 'Register Asset'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
