import { afterEach, describe, expect, it, vi } from 'vitest'
import { requestRecognition } from './recognitionApi.js'

const imageFile = () => new File(['image'], 'cat.png', { type: 'image/png' })
const jsonResponse = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })

describe('requestRecognition', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })

  it('submits a job and polls until the backend returns predictions', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            job_id: 'job-123',
            status: 'queued',
            status_url: '/jobs/job-123',
          },
          202,
        ),
      )
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-123', status: 'queued' }))
      .mockResolvedValueOnce(jsonResponse({ job_id: 'job-123', status: 'processing' }))
      .mockResolvedValueOnce(
        jsonResponse({
          job_id: 'job-123',
          status: 'completed',
          predictions: [{ label: 'cat', confidence: 0.98 }],
        }),
      )
    const sleepMock = vi.fn().mockResolvedValue()

    await expect(
      requestRecognition(imageFile(), {
        fetchImpl: fetchMock,
        sleepImpl: sleepMock,
      }),
    ).resolves.toMatchObject({
      status: 'completed',
      predictions: [{ label: 'cat', confidence: 0.98 }],
    })

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/jobs',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://localhost:8000/jobs/job-123', {
      method: 'GET',
      cache: 'no-store',
    })
    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(sleepMock).toHaveBeenCalledTimes(2)
    expect(sleepMock).toHaveBeenNthCalledWith(1, 1000)
    expect(sleepMock).toHaveBeenNthCalledWith(2, 1000)

    const [, options] = fetchMock.mock.calls[0]
    expect(options.body.get('file')).toMatchObject({ name: 'cat.png', type: 'image/png' })
  })

  it('reports the backend error when a job reaches failed', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          { job_id: 'job-123', status: 'queued', status_url: '/jobs/job-123' },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          job_id: 'job-123',
          status: 'failed',
          error: { code: 'inference_failed', message: 'Model chưa sẵn sàng.' },
        }),
      )

    await expect(
      requestRecognition(imageFile(), {
        fetchImpl: fetchMock,
        sleepImpl: vi.fn(),
      }),
    ).rejects.toThrow('Model chưa sẵn sàng.')
  })

  it('extracts nested backend errors from failed HTTP responses', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ error: { code: 'invalid_image', message: 'Ảnh bị hỏng.' } }, 422),
    )

    await expect(
      requestRecognition(imageFile(), { fetchImpl: fetchMock }),
    ).rejects.toThrow('Ảnh bị hỏng.')
  })

  it('shows a long-running notice but continues polling', async () => {
    let elapsed = 0
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          { job_id: 'job-123', status: 'queued', status_url: '/jobs/job-123' },
          202,
        ),
      )
      .mockResolvedValueOnce(jsonResponse({ status: 'queued' }))
      .mockResolvedValueOnce(jsonResponse({ status: 'processing' }))
      .mockResolvedValueOnce(jsonResponse({ status: 'completed', predictions: [] }))
    const onLongRunning = vi.fn()

    await requestRecognition(imageFile(), {
      fetchImpl: fetchMock,
      sleepImpl: async () => {
        elapsed += 1000
      },
      now: () => elapsed,
      longRunningNoticeMs: 500,
      onLongRunning,
    })

    expect(onLongRunning).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(4)
  })

  it('rejects a status URL that points to another origin', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          job_id: 'job-123',
          status: 'queued',
          status_url: 'https://other.example/jobs/job-123',
        },
        202,
      ),
    )

    await expect(
      requestRecognition(imageFile(), { fetchImpl: fetchMock }),
    ).rejects.toThrow('không cùng địa chỉ API')
  })

  it('uses the same-origin jobs proxy when the configured API base URL is empty', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          { job_id: 'job-123', status: 'queued', status_url: '/jobs/job-123' },
          202,
        ),
      )
      .mockResolvedValueOnce(jsonResponse({ status: 'completed', predictions: [] }))

    await requestRecognition(imageFile(), {
      fetchImpl: fetchMock,
      sleepImpl: vi.fn(),
    })

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/jobs',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/jobs/job-123', {
      method: 'GET',
      cache: 'no-store',
    })
  })
})
