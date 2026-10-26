import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import EvidenceUploader from '../EvidenceUploader'
import type { SelectedMediaFile } from '../EvidenceUploader'

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

// Mock useAssetEvidence hook to return empty archive by default
vi.mock('../../hooks/useAssetEvidence', () => ({
  useAssetEvidence: () => ({
    data: [],
    isLoading: false,
  }),
}))

describe('EvidenceUploader Component Interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('clicking quick observation tags toggles state and NEVER triggers file picker', () => {
    const handleToggleTag = vi.fn()
    const handleSelectMedia = vi.fn()
    const handleChangeSource = vi.fn()
    const handleChangeNotes = vi.fn()

    renderWithClient(
      <EvidenceUploader
        source="image"
        onChangeSource={handleChangeSource}
        notes=""
        onChangeNotes={handleChangeNotes}
        mediaFile={null}
        onSelectMediaFile={handleSelectMedia}
        selectedTags={['Hairline crack (<1mm)']}
        onToggleTag={handleToggleTag}
      />
    )

    const fileInput = screen.getByTestId('evidence-file-input') as HTMLInputElement
    const clickSpy = vi.spyOn(fileInput, 'click')

    // Find observation tags
    const hairlineBtn = screen.getByTestId('tag-hairline-crack---1mm-')
    const wideBtn = screen.getByTestId('tag-wide-crack---2mm-')
    const spallingBtn = screen.getByTestId('tag-surface-spalling')

    expect(hairlineBtn).toHaveAttribute('aria-pressed', 'true')
    expect(wideBtn).toHaveAttribute('aria-pressed', 'false')

    // Click an unselected tag
    fireEvent.click(wideBtn)
    expect(handleToggleTag).toHaveBeenCalledWith('Wide crack (>2mm)')
    expect(clickSpy).not.toHaveBeenCalled()

    // Click another tag
    fireEvent.click(spallingBtn)
    expect(handleToggleTag).toHaveBeenCalledWith('Surface spalling')
    expect(clickSpy).not.toHaveBeenCalled()

    // Click the already-selected tag to toggle off
    fireEvent.click(hairlineBtn)
    expect(handleToggleTag).toHaveBeenCalledWith('Hairline crack (<1mm)')
    expect(clickSpy).not.toHaveBeenCalled()
  })

  it('clicking Advanced Ingestion Parameters disclosure does NOT trigger file picker', () => {
    const handleToggleTag = vi.fn()
    const handleSelectMedia = vi.fn()
    const handleChangeSource = vi.fn()
    const handleChangeNotes = vi.fn()

    renderWithClient(
      <EvidenceUploader
        source="image"
        onChangeSource={handleChangeSource}
        notes=""
        onChangeNotes={handleChangeNotes}
        mediaFile={null}
        onSelectMediaFile={handleSelectMedia}
        selectedTags={[]}
        onToggleTag={handleToggleTag}
      />
    )

    const fileInput = screen.getByTestId('evidence-file-input') as HTMLInputElement
    const clickSpy = vi.spyOn(fileInput, 'click')

    const summary = screen.getByTestId('advanced-params-summary')
    fireEvent.click(summary)

    expect(clickSpy).not.toHaveBeenCalled()

    // Changing acquisition modality
    const select = screen.getByLabelText(/Capture Acquisition Modality/i)
    fireEvent.change(select, { target: { value: 'drone' } })
    expect(handleChangeSource).toHaveBeenCalledWith('drone')
    expect(clickSpy).not.toHaveBeenCalled()
  })

  it('clicking or editing Field Notes textarea does NOT trigger file picker', () => {
    const handleSelectMedia = vi.fn()
    const handleChangeSource = vi.fn()
    const handleChangeNotes = vi.fn()

    renderWithClient(
      <EvidenceUploader
        source="image"
        onChangeSource={handleChangeSource}
        notes=""
        onChangeNotes={handleChangeNotes}
        mediaFile={null}
        onSelectMediaFile={handleSelectMedia}
      />
    )

    const fileInput = screen.getByTestId('evidence-file-input') as HTMLInputElement
    const clickSpy = vi.spyOn(fileInput, 'click')

    const textarea = screen.getByLabelText(/Field Observations/i)
    fireEvent.click(textarea)
    fireEvent.change(textarea, { target: { value: 'Crack on north pier' } })

    expect(handleChangeNotes).toHaveBeenCalledWith('Crack on north pier')
    expect(clickSpy).not.toHaveBeenCalled()
  })

  it('clicking dropzone or Choose Image button triggers file picker', () => {
    const handleSelectMedia = vi.fn()
    const handleChangeSource = vi.fn()
    const handleChangeNotes = vi.fn()

    renderWithClient(
      <EvidenceUploader
        source="image"
        onChangeSource={handleChangeSource}
        notes=""
        onChangeNotes={handleChangeNotes}
        mediaFile={null}
        onSelectMediaFile={handleSelectMedia}
      />
    )

    const fileInput = screen.getByTestId('evidence-file-input') as HTMLInputElement
    const clickSpy = vi.spyOn(fileInput, 'click')

    // Click Choose Image button
    const chooseBtn = screen.getByTestId('choose-image-btn')
    fireEvent.click(chooseBtn)
    expect(clickSpy).toHaveBeenCalledTimes(1)

    // Click dropzone area
    const dropzone = screen.getByTestId('dropzone-area')
    fireEvent.click(dropzone)
    expect(clickSpy).toHaveBeenCalledTimes(2)

    // Keyboard trigger on dropzone (Enter)
    fireEvent.keyDown(dropzone, { key: 'Enter' })
    expect(clickSpy).toHaveBeenCalledTimes(3)
  })

  it('when mediaFile is staged, Replace triggers file picker and tags still do NOT trigger it', () => {
    const handleToggleTag = vi.fn()
    const handleSelectMedia = vi.fn()
    const handleChangeSource = vi.fn()
    const handleChangeNotes = vi.fn()

    const stagedMedia: SelectedMediaFile = {
      previewUrl: 'blob:http://localhost/test-uuid',
      caption: 'crack_sample_01.jpeg',
      formattedSize: '3.45 MB',
      width: 1920,
      height: 1080,
    }

    renderWithClient(
      <EvidenceUploader
        source="image"
        onChangeSource={handleChangeSource}
        notes=""
        onChangeNotes={handleChangeNotes}
        mediaFile={stagedMedia}
        onSelectMediaFile={handleSelectMedia}
        selectedTags={['Surface spalling']}
        onToggleTag={handleToggleTag}
      />
    )

    const fileInput = screen.getByTestId('evidence-file-input') as HTMLInputElement
    const clickSpy = vi.spyOn(fileInput, 'click')

    // Dropzone should not be shown when staged
    expect(screen.queryByTestId('dropzone-area')).toBeNull()

    // Preview card is rendered
    expect(screen.getByTestId('staged-preview-card')).toBeInTheDocument()
    expect(screen.getByText('crack_sample_01.jpeg')).toBeInTheDocument()
    expect(screen.getByText('3.45 MB')).toBeInTheDocument()
    expect(screen.getByText('1920 × 1080 px')).toBeInTheDocument()

    // Clicking observation tag in staged state must NOT trigger file input
    const tagBtn = screen.getByTestId('tag-rust-discoloration')
    fireEvent.click(tagBtn)
    expect(handleToggleTag).toHaveBeenCalledWith('Rust discoloration')
    expect(clickSpy).not.toHaveBeenCalled()

    // Clicking Advanced summary in staged state must NOT trigger file input
    const summary = screen.getByTestId('advanced-params-summary')
    fireEvent.click(summary)
    expect(clickSpy).not.toHaveBeenCalled()

    // Clicking Replace button MUST trigger file picker
    const replaceBtn = screen.getByTestId('replace-image-btn')
    fireEvent.click(replaceBtn)
    expect(clickSpy).toHaveBeenCalledTimes(1)

    // Clicking Remove button removes staged media
    const removeBtn = screen.getByTestId('remove-image-btn')
    fireEvent.click(removeBtn)
    expect(handleSelectMedia).toHaveBeenCalledWith(null)
  })

  it('verifies hidden file input has display: none and does not intercept clicks', () => {
    const handleSelectMedia = vi.fn()
    const handleChangeSource = vi.fn()
    const handleChangeNotes = vi.fn()

    renderWithClient(
      <EvidenceUploader
        source="image"
        onChangeSource={handleChangeSource}
        notes=""
        onChangeNotes={handleChangeNotes}
        mediaFile={null}
        onSelectMediaFile={handleSelectMedia}
        selectedTags={[]}
        onToggleTag={vi.fn()}
      />
    )

    const fileInput = screen.getByTestId('evidence-file-input') as HTMLInputElement
    expect(fileInput).toHaveStyle({ display: 'none' })
    expect(fileInput).toHaveAttribute('aria-hidden', 'true')
    expect(fileInput).toHaveAttribute('tabIndex', '-1')
  })

  it('all observation tags have explicit type="button"', () => {
    renderWithClient(
      <EvidenceUploader
        source="image"
        onChangeSource={vi.fn()}
        notes=""
        onChangeNotes={vi.fn()}
        mediaFile={null}
        onSelectMediaFile={vi.fn()}
        selectedTags={[]}
        onToggleTag={vi.fn()}
      />
    )

    const tagNames = [
      'tag-hairline-crack---1mm-',
      'tag-wide-crack---2mm-',
      'tag-surface-spalling',
      'tag-water-seepage---dampness',
      'tag-rust-discoloration',
      'tag-concrete-scaling',
    ]

    for (const testId of tagNames) {
      const btn = screen.getByTestId(testId)
      expect(btn).toHaveAttribute('type', 'button')
    }
  })

  it('pressing Space on dropzone triggers file picker', () => {
    renderWithClient(
      <EvidenceUploader
        source="image"
        onChangeSource={vi.fn()}
        notes=""
        onChangeNotes={vi.fn()}
        mediaFile={null}
        onSelectMediaFile={vi.fn()}
      />
    )

    const fileInput = screen.getByTestId('evidence-file-input') as HTMLInputElement
    const clickSpy = vi.spyOn(fileInput, 'click')

    const dropzone = screen.getByTestId('dropzone-area')
    fireEvent.keyDown(dropzone, { key: ' ' })
    expect(clickSpy).toHaveBeenCalledTimes(1)
  })
})
