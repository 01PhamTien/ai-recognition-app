import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'

function stubObjectUrls(previewUrl) {
  const NativeURL = URL
  class MockURL extends NativeURL {}
  MockURL.createObjectURL = vi.fn(() => previewUrl)
  MockURL.revokeObjectURL = vi.fn()
  vi.stubGlobal('URL', MockURL)
}

describe('image upload interface', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('previews a valid image and allows it to be removed', async () => {
    stubObjectUrls('blob:preview')
    const user = userEvent.setup()
    render(<App />)

    const image = new File(['image-data'], 'cat.png', { type: 'image/png' })
    await user.upload(screen.getByLabelText('Chọn tệp ảnh'), image)

    expect(await screen.findByRole('img', { name: 'Xem trước cat.png' })).toHaveAttribute(
      'src',
      'blob:preview',
    )
    expect(screen.getByText('cat.png')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Xóa ảnh đã chọn' }))
    expect(screen.queryByRole('img', { name: 'Xem trước cat.png' })).not.toBeInTheDocument()
    expect(screen.getByText('Kéo thả ảnh vào đây')).toBeInTheDocument()
  })

  it('shows an accessible error for an unsupported image', async () => {
    const user = userEvent.setup({ applyAccept: false })
    render(<App />)
    const file = new File(['text'], 'notes.txt', { type: 'text/plain' })

    await user.upload(screen.getByLabelText('Chọn tệp ảnh'), file)

    expect(await screen.findByRole('alert')).toHaveTextContent(/JPG hoặc PNG/)
    expect(screen.queryByRole('img', { name: 'Xem trước notes.txt' })).not.toBeInTheDocument()
  })

  it('accepts an image dropped into the upload area', async () => {
    stubObjectUrls('blob:dropped')
    render(<App />)
    const file = new File(['image-data'], 'dropped.jpg', { type: 'image/jpeg' })
    const dropZone = screen.getByText('Kéo thả ảnh vào đây').closest('.drop-zone')

    fireEvent.drop(dropZone, { dataTransfer: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByRole('img', { name: 'Xem trước dropped.jpg' })).toHaveAttribute(
        'src',
        'blob:dropped',
      )
    })
  })

  it('disables submission until an image has been selected', async () => {
    stubObjectUrls('blob:preview')
    const user = userEvent.setup()
    render(<App />)

    const submitButton = screen.getByRole('button', { name: /Gửi yêu cầu nhận diện/ })
    expect(submitButton).toBeDisabled()

    await user.upload(
      screen.getByLabelText('Chọn tệp ảnh'),
      new File(['image-data'], 'cat.png', { type: 'image/png' }),
    )

    expect(submitButton).toBeEnabled()
  })

  it('sends the selected image and displays the backend result', async () => {
    stubObjectUrls('blob:preview')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            job_id: 'job-123',
            status: 'queued',
            status_url: '/jobs/job-123',
          }),
          { status: 202, headers: { 'content-type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            job_id: 'job-123',
            status: 'completed',
            predictions: [{ label: 'cat', confidence: 0.98 }],
          }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        ),
      )
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)

    await user.upload(
      screen.getByLabelText('Chọn tệp ảnh'),
      new File(['image-data'], 'cat.png', { type: 'image/png' }),
    )
    await user.click(screen.getByRole('button', { name: /Gửi yêu cầu nhận diện/ }))

    expect(await screen.findByRole('heading', { name: 'Kết quả nhận diện' })).toBeInTheDocument()
    expect(screen.getByText(/"label": "cat"/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/jobs',
      expect.objectContaining({ method: 'POST' }),
    )
    const [, options] = fetchMock.mock.calls[0]
    expect(options.body.get('file')).toMatchObject({ name: 'cat.png', type: 'image/png' })
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/jobs/job-123',
      { method: 'GET' },
    )
  })

  it('shows backend errors instead of hiding a failed request', async () => {
    stubObjectUrls('blob:preview')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: { code: 'internal_error', message: 'Model chưa sẵn sàng.' },
          }),
          {
            status: 503,
            headers: { 'content-type': 'application/json' },
          },
        ),
      ),
    )
    const user = userEvent.setup()
    render(<App />)

    await user.upload(
      screen.getByLabelText('Chọn tệp ảnh'),
      new File(['image-data'], 'cat.png', { type: 'image/png' }),
    )
    await user.click(screen.getByRole('button', { name: /Gửi yêu cầu nhận diện/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Model chưa sẵn sàng.')
    expect(screen.queryByRole('heading', { name: 'Kết quả nhận diện' })).not.toBeInTheDocument()
  })

  it('shows a clear message when the backend cannot be reached', async () => {
    stubObjectUrls('blob:preview')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const user = userEvent.setup()
    render(<App />)

    await user.upload(
      screen.getByLabelText('Chọn tệp ảnh'),
      new File(['image-data'], 'cat.png', { type: 'image/png' }),
    )
    await user.click(screen.getByRole('button', { name: /Gửi yêu cầu nhận diện/ }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Không kết nối được backend/)
  })
})
