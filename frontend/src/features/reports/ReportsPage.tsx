import { useState, useMemo, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAssets } from '../../hooks/useAssets'
import { useAssetInspections } from '../../hooks/useAssetInspections'
import { useReportsList, useGenerateReport } from '../../hooks/useReports'
import type { ReportGenerateResponse } from '../../api/reports'
import PageHeader from '../../components/layout/PageHeader'
import LoadingState from '../../components/ui/LoadingState'
import ErrorState from '../../components/ui/ErrorState'
import {
  FileText,
  Play,
  RotateCw,
  Download,
  ExternalLink,
  Printer,
  Archive,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react'
import styles from './ReportsPage.module.css'

export default function ReportsPage() {
  const [searchParams] = useSearchParams()
  const urlAssetId = searchParams.get('assetId')
  const urlInspId = searchParams.get('inspectionId')
  const urlReportFile = searchParams.get('reportFile')

  const { data: assetsData, isLoading: assetsLoading, isError: assetsError } = useAssets(1, 100)
  const assets = useMemo(() => assetsData?.items ?? [], [assetsData])

  // Asset selection
  const [selectedAssetId, setSelectedAssetId] = useState<string>('')

  useEffect(() => {
    if (urlAssetId && assets.some((a) => a.id === urlAssetId)) {
      setSelectedAssetId(urlAssetId)
    }
  }, [urlAssetId, assets])

  const effectiveAssetId = selectedAssetId || (urlAssetId && assets.some((a) => a.id === urlAssetId) ? urlAssetId : assets[0]?.id) || ''

  const selectedAsset = useMemo(
    () => assets.find((a) => a.id === effectiveAssetId) ?? assets[0] ?? null,
    [assets, effectiveAssetId]
  )

  // Inspections for selected asset
  const { data: inspections = [], isLoading: inspLoading } = useAssetInspections(selectedAsset?.id)
  const completedInspections = useMemo(
    () => inspections.filter((i) => i.status === 'completed'),
    [inspections]
  )

  // Selected completed inspection
  const [selectedInspId, setSelectedInspId] = useState<string>('')

  useEffect(() => {
    if (urlInspId && completedInspections.some((i) => i.id === urlInspId)) {
      setSelectedInspId(urlInspId)
    }
  }, [urlInspId, completedInspections])

  const effectiveInspId = selectedInspId || (urlInspId && completedInspections.some((i) => i.id === urlInspId) ? urlInspId : completedInspections[0]?.id) || ''

  const selectedInspection = useMemo(
    () => completedInspections.find((i) => i.id === effectiveInspId) ?? completedInspections[0] ?? null,
    [completedInspections, effectiveInspId]
  )

  // Persisted reports list
  const { data: archivedReports = [], isLoading: archiveLoading, refetch: refetchArchive } = useReportsList()

  // Generate mutation
  const generateMutation = useGenerateReport()
  const [activeReport, setActiveReport] = useState<ReportGenerateResponse | null>(null)
  const [selectedReportFile, setSelectedReportFile] = useState<string | null>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    if (urlReportFile) {
      setSelectedReportFile(urlReportFile)
    }
  }, [urlReportFile])

  const handleCompileReport = () => {
    if (!selectedAsset || !selectedInspection) return
    generateMutation.mutate(
      {
        asset_id: selectedAsset.id,
        inspection_id: selectedInspection.id,
        format: 'html',
      },
      {
        onSuccess: (data) => {
          setActiveReport(data)
          setSelectedReportFile(data.filename)
          void refetchArchive()
        },
      }
    )
  }

  const handlePrint = () => {
    if (iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.print()
    }
  }

  const currentPreviewFilename = activeReport?.filename || selectedReportFile

  if (assetsLoading) {
    return (
      <div className={styles.container}>
        <PageHeader
          title="Structural Engineering Reports"
          description="Formal structural health condition reports, defect inventories, and maintenance action decisions."
        />
        <div className={styles.content}>
          <LoadingState rows={4} columns={3} />
        </div>
      </div>
    )
  }

  if (assetsError) {
    return (
      <div className={styles.container}>
        <PageHeader
          title="Structural Engineering Reports"
          description="Formal structural health condition reports, defect inventories, and maintenance action decisions."
        />
        <div className={styles.content}>
          <ErrorState message="Could not retrieve asset registry for report compilation." />
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <PageHeader
        title="Structural Engineering Reports"
        description="Formal inspection dossiers, defect inventories, risk escalation, and maintenance action estimates."
        breadcrumb={[
          { label: 'Dashboard', to: '/dashboard' },
          { label: 'Engineering Reports' },
        ]}
      />

      <div className={styles.content}>
        {/* Report Compilation Form Panel */}
        <section className={styles.generatorPanel} aria-label="Compile Report">
          <h2 className={styles.panelHeading}>
            <FileText size={18} color="#353B32" />
            <span>Compile New Engineering Report</span>
          </h2>

          <div className={styles.formGrid}>
            <div className={styles.fieldGroup}>
              <label htmlFor="report-asset-select" className={styles.fieldLabel}>
                1. Monitored Civil Asset
              </label>
              <select
                id="report-asset-select"
                className={styles.selectInput}
                value={effectiveAssetId}
                onChange={(e) => {
                  setSelectedAssetId(e.target.value)
                  setSelectedInspId('')
                }}
              >
                {assets.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.asset_type.toUpperCase()})
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.fieldGroup}>
              <label htmlFor="report-inspection-select" className={styles.fieldLabel}>
                2. Associated Completed Inspection
              </label>
              {inspLoading ? (
                <div style={{ padding: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
                  Loading inspection history...
                </div>
              ) : completedInspections.length > 0 ? (
                <select
                  id="report-inspection-select"
                  className={styles.selectInput}
                  value={effectiveInspId}
                  onChange={(e) => setSelectedInspId(e.target.value)}
                >
                  {completedInspections.map((insp) => {
                    const dateStr = new Date(insp.created_at).toLocaleDateString('en-GB', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    })
                    return (
                      <option key={insp.id} value={insp.id}>
                        {dateStr} — {insp.defect_count} defect(s), score {insp.health_score ?? '—'}/100
                      </option>
                    )
                  })}
                </select>
              ) : (
                <div style={{ padding: '8px', fontSize: '12px', color: '#9D3E32', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <AlertCircle size={14} />
                  <span>No completed inspections found for this asset.</span>
                </div>
              )}
            </div>
          </div>

          <div className={styles.actionRow}>
            <div className={styles.capabilityNotice}>
              <strong>Export Format:</strong> Full HTML report generation active. Server-side PDF export requires optional GTK WeasyPrint runtime; browser-native Print-to-PDF is fully supported.
            </div>

            <button
              type="button"
              className={styles.compileBtn}
              disabled={!selectedInspection || generateMutation.isPending}
              onClick={handleCompileReport}
            >
              {generateMutation.isPending ? (
                <RotateCw className="spin" size={14} />
              ) : (
                <Play size={14} />
              )}
              <span>
                {generateMutation.isPending ? 'Assembling Report...' : 'Compile & Preview Report'}
              </span>
            </button>
          </div>

          {generateMutation.isError && (
            <div style={{ color: '#9D3E32', fontSize: '12px', marginTop: '8px' }}>
              Error: {generateMutation.error.message || 'Report assembly failed.'}
            </div>
          )}
        </section>

        {/* Live Report Preview Frame */}
        {currentPreviewFilename && (
          <section className={styles.previewSection} aria-label="Report Preview">
            <div className={styles.previewHeader}>
              <div className={styles.previewMeta}>
                <CheckCircle2 size={16} color="#66765A" />
                <span>
                  Report Dossier: <strong>{currentPreviewFilename}</strong>
                </span>
                {activeReport?.health_score !== undefined && (
                  <span>• Health: {activeReport.health_score ?? '—'}/100</span>
                )}
                {activeReport?.recommended_action && (
                  <span>• Action: {activeReport.recommended_action.toUpperCase()}</span>
                )}
              </div>

              <div className={styles.previewActions}>
                <a
                  href={`/api/v1/reports/${currentPreviewFilename}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.previewBtn}
                  title="Open report in separate browser tab"
                >
                  <ExternalLink size={13} />
                  <span>New Tab</span>
                </a>

                <button
                  type="button"
                  className={styles.previewBtn}
                  onClick={handlePrint}
                  title="Print or Save as PDF via browser print dialogue"
                >
                  <Printer size={13} />
                  <span>Print to PDF</span>
                </button>

                <a
                  href={`/api/v1/reports/${currentPreviewFilename}`}
                  download={currentPreviewFilename}
                  className={styles.previewBtn}
                  title="Download HTML report file"
                >
                  <Download size={13} />
                  <span>Download HTML</span>
                </a>
              </div>
            </div>

            <div className={styles.iframeWrapper}>
              <iframe
                ref={iframeRef}
                src={activeReport ? undefined : `/api/v1/reports/${currentPreviewFilename}`}
                srcDoc={activeReport ? activeReport.html_content : undefined}
                title="Compiled Engineering Report Preview"
                className={styles.reportIframe}
              />
            </div>
          </section>
        )}

        {/* Persisted Reports Archive */}
        <section className={styles.archiveSection} aria-label="Persisted Reports Archive">
          <h3 className={styles.panelHeading}>
            <Archive size={16} color="#77766D" />
            <span>Persisted Report Archive ({archivedReports.length})</span>
          </h3>

          {archiveLoading ? (
            <LoadingState rows={3} columns={4} />
          ) : archivedReports.length > 0 ? (
            <div className={styles.tableWrap}>
              <table className={styles.reportsTable}>
                <thead>
                  <tr>
                    <th>Report File</th>
                    <th>Asset UUID</th>
                    <th>Inspection UUID</th>
                    <th>Created (UTC)</th>
                    <th>File Size</th>
                    <th>Format</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {archivedReports.map((r) => {
                    const dateStr = new Date(r.created_at).toLocaleString('en-GB', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                    return (
                      <tr key={r.filename}>
                        <td>
                          <a
                            href={`/api/v1/reports/${r.filename}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={styles.reportLink}
                          >
                            <FileText size={13} />
                            <span>{r.filename}</span>
                          </a>
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{r.asset_id ?? '—'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{r.inspection_id ?? '—'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{dateStr}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>
                          {(r.size_bytes / 1024).toFixed(1)} KB
                        </td>
                        <td>
                          <span
                            style={{
                              fontFamily: 'var(--font-mono)',
                              textTransform: 'uppercase',
                              fontWeight: 600,
                              fontSize: '10px',
                              padding: '2px 6px',
                              borderRadius: '2px',
                              background: 'var(--bg-subtle)',
                              color: 'var(--text-primary)',
                            }}
                          >
                            {r.format}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedReportFile(r.filename)
                                setActiveReport(null)
                                window.scrollTo({ top: 380, behavior: 'smooth' })
                              }}
                              className={styles.reportLink}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                              title="Preview report in frame above"
                            >
                              <ExternalLink size={13} />
                              <span>Preview</span>
                            </button>
                            <a
                              href={`/api/v1/reports/${r.filename}`}
                              download={r.filename}
                              className={styles.reportLink}
                              title="Download file"
                            >
                              <Download size={13} />
                              <span>Download</span>
                            </a>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-muted)' }}>
              No persisted reports generated yet. Select an asset and completed inspection above to compile the first report.
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
