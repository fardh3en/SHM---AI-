import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Camera,
  CheckCircle2,
  Bookmark,
  ExternalLink,
  X,
  Play,
  Layers,
  Sparkles,
} from 'lucide-react'
import Button from '../../components/ui/Button'
import EmptyState from '../../components/ui/EmptyState'
import LoadingState from '../../components/ui/LoadingState'
import { useAssetEvidence } from '../../hooks/useAssetEvidence'
import type { AssetEvidence, EvidenceClassification } from '../../api/evidence'
import styles from './AssetEvidenceGallery.module.css'

interface AssetEvidenceGalleryProps {
  assetId: string
  assetName: string
}

function getBadge(classification: EvidenceClassification) {
  switch (classification) {
    case 'verified_structure':
      return {
        label: 'Verified Structure',
        className: styles.badgeVerified,
        icon: <CheckCircle2 size={12} />,
      }
    case 'comparable_reference':
      return {
        label: 'Comparable Reference',
        className: styles.badgeComparable,
        icon: <Bookmark size={12} />,
      }
    case 'synthetic_demo':
    default:
      return {
        label: 'Synthetic Demo',
        className: styles.badgeSynthetic,
        icon: <Sparkles size={12} />,
      }
  }
}

export default function AssetEvidenceGallery({ assetId, assetName }: AssetEvidenceGalleryProps) {
  const { data: evidenceList, isLoading, isError } = useAssetEvidence(assetId)
  const [activeModalEvidence, setActiveModalEvidence] = useState<AssetEvidence | null>(null)
  const [imageErrorMap, setImageErrorMap] = useState<Record<string, boolean>>({})

  const handleImageError = (id: string) => {
    setImageErrorMap((prev) => ({ ...prev, [id]: true }))
  }

  if (isLoading) {
    return (
      <section className={styles.section} aria-label="Visual Evidence Loading">
        <div className={styles.header}>
          <h2 className={styles.title}>
            <Camera size={18} /> Visual Evidence &amp; Photographic Archive
          </h2>
        </div>
        <LoadingState rows={3} columns={3} />
      </section>
    )
  }

  if (isError) {
    return (
      <section className={styles.section} aria-label="Visual Evidence Error">
        <div className={styles.header}>
          <h2 className={styles.title}>
            <Camera size={18} /> Visual Evidence &amp; Photographic Archive
          </h2>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
          Unable to load visual evidence records for this asset.
        </div>
      </section>
    )
  }

  const items = evidenceList ?? []

  return (
    <section className={styles.section} aria-label="Visual Evidence Gallery">
      <div className={styles.header}>
        <h2 className={styles.title}>
          <Camera size={18} /> Visual Evidence &amp; Photographic Archive
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className={styles.countPill}>
            {items.length} {items.length === 1 ? 'Photograph' : 'Photographs'} Available
          </span>
          <Link
            to={`/inspections?asset_id=${assetId}`}
            style={{ textDecoration: 'none' }}
          >
            <Button size="sm" variant="secondary">
              <Play size={13} /> Run Inspection Studio
            </Button>
          </Link>
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState
          title="No photographic evidence archived"
          description={`No verified field photographs or reference imagery have been linked to ${assetName} yet.`}
        />
      ) : (
        <div className={styles.grid}>
          {items.map((ev) => {
            const badge = getBadge(ev.classification)
            const hasError = imageErrorMap[ev.id]

            return (
              <article key={ev.id} className={styles.card}>
                <div
                  className={styles.imageWrap}
                  onClick={() => setActiveModalEvidence(ev)}
                  title="Click to expand high-resolution photograph"
                >
                  {hasError ? (
                    <div
                      style={{
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--text-muted)',
                        gap: '6px',
                        fontSize: '0.8125rem',
                      }}
                    >
                      <Camera size={28} />
                      <span>Image unavailable</span>
                    </div>
                  ) : (
                    <img
                      src={ev.file_path}
                      alt={ev.caption}
                      className={styles.image}
                      loading="lazy"
                      onError={() => handleImageError(ev.id)}
                    />
                  )}

                  <div className={`${styles.badge} ${badge.className}`}>
                    {badge.icon}
                    <span>{badge.label}</span>
                  </div>
                </div>

                <div className={styles.cardBody}>
                  <h3 className={styles.caption}>{ev.caption}</h3>

                  {ev.component_description && (
                    <p className={styles.description}>{ev.component_description}</p>
                  )}

                  <div className={styles.provenance}>
                    {ev.creator && (
                      <div className={styles.provenanceRow}>
                        <span>Creator / Source:</span>
                        <strong style={{ color: 'var(--text-primary)' }}>{ev.creator}</strong>
                      </div>
                    )}

                    {ev.license && (
                      <div className={styles.provenanceRow}>
                        <span>License:</span>
                        <code>{ev.license}</code>
                      </div>
                    )}

                    {ev.source_url && (
                      <div className={styles.provenanceRow}>
                        <span>Repository:</span>
                        <a
                          href={ev.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={styles.provenanceLink}
                        >
                          Source Record <ExternalLink size={10} />
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                <div className={styles.cardFooter}>
                  <Link
                    to={`/inspections?asset_id=${assetId}&evidence_path=${encodeURIComponent(
                      ev.file_path
                    )}`}
                    style={{ textDecoration: 'none' }}
                  >
                    <Button size="sm" variant="ghost">
                      <Layers size={13} /> Select for Inspection →
                    </Button>
                  </Link>
                </div>
              </article>
            )
          })}
        </div>
      )}

      {/* Modal Lightbox */}
      {activeModalEvidence && (
        <div
          className={styles.modalBackdrop}
          onClick={() => setActiveModalEvidence(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className={styles.modalContent}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.modalHeader}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  className={`${styles.badge} ${
                    getBadge(activeModalEvidence.classification).className
                  }`}
                  style={{ position: 'static' }}
                >
                  {getBadge(activeModalEvidence.classification).icon}
                  {getBadge(activeModalEvidence.classification).label}
                </span>
                <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>
                  {activeModalEvidence.caption}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setActiveModalEvidence(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '4px',
                }}
              >
                <X size={18} />
              </button>
            </div>

            <div className={styles.modalImageWrap}>
              <img
                src={activeModalEvidence.file_path}
                alt={activeModalEvidence.caption}
                className={styles.modalImage}
              />
            </div>

            <div className={styles.modalBody}>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {activeModalEvidence.component_description}
              </p>

              <div className={styles.provenance} style={{ fontSize: '0.75rem' }}>
                {activeModalEvidence.creator && (
                  <div className={styles.provenanceRow}>
                    <span>Photographer / Attribution:</span>
                    <strong>{activeModalEvidence.creator}</strong>
                  </div>
                )}
                {activeModalEvidence.license && (
                  <div className={styles.provenanceRow}>
                    <span>Reuse License:</span>
                    <code>{activeModalEvidence.license}</code>
                  </div>
                )}
                {activeModalEvidence.source_url && (
                  <div className={styles.provenanceRow}>
                    <span>Authoritative Repository Link:</span>
                    <a
                      href={activeModalEvidence.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.provenanceLink}
                    >
                      {activeModalEvidence.source_url} <ExternalLink size={12} />
                    </a>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <Button variant="ghost" onClick={() => setActiveModalEvidence(null)}>
                  Close Preview
                </Button>
                <Link
                  to={`/inspections?asset_id=${assetId}&evidence_path=${encodeURIComponent(
                    activeModalEvidence.file_path
                  )}`}
                  style={{ textDecoration: 'none' }}
                >
                  <Button variant="primary">
                    <Play size={14} /> Open in Inspection Studio
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
