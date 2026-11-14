export const POLL_INTERVAL_MS = 1000
export const LONG_RUNNING_NOTICE_MS = 60 * 1000

function getApiBaseUrl() {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL
  if (typeof configuredBaseUrl === 'string') {
    return configuredBaseUrl.trim().replace(/\/+$/, '')
  }

  return 'http://localhost:8000'
}

function getJobsUrl(baseUrl) {
  return baseUrl ? `${baseUrl}/jobs` : '/jobs'
}

function getStatusUrl(statusUrl, baseUrl) {
  if (typeof statusUrl !== 'string' || !statusUrl.trim()) {
    throw new Error('Backend không trả về status_url hợp lệ cho tác vụ.')
  }

  const pageOrigin = typeof window === 'undefined' ? '' : window.location.origin
  const expectedOrigin = baseUrl ? new URL(baseUrl).origin : pageOrigin
  const resolvedUrl = new URL(statusUrl, baseUrl || pageOrigin)
  if (!expectedOrigin || resolvedUrl.origin !== expectedOrigin) {
    throw new Error('Backend trả về status_url không cùng địa chỉ API.')
  }

  return baseUrl ? resolvedUrl.toString() : `${resolvedUrl.pathname}${resolvedUrl.search}`
}

function extractErrorMessage(value) {
  if (typeof value === 'string') {
    const trimmedValue = value.trim()
    return trimmedValue || ''
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const itemMessage = extractErrorMessage(item)
      if (itemMessage) return itemMessage
    }
    return ''
  }

  if (value && typeof value === 'object') {
    const candidateKeys = ['detail', 'message', 'error', 'title']
    for (const key of candidateKeys) {
      const itemMessage = extractErrorMessage(value[key])
      if (itemMessage) return itemMessage
    }

    for (const nestedValue of Object.values(value)) {
      const nestedMessage = extractErrorMessage(nestedValue)
      if (nestedMessage) return nestedMessage
    }
  }

  return ''
}

function getErrorMessage(body, status) {
  const message = extractErrorMessage(body)
  if (message) return message

  return `Backend trả về lỗi HTTP ${status}.`
}

async function fetchResponse(fetchImpl, url, options) {
  try {
    return await fetchImpl(url, options)
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        'Không kết nối được backend. Hãy kiểm tra backend đang chạy, URL API và cấu hình CORS.',
        { cause: error },
      )
    }
    throw error
  }
}

async function readResponseBody(response) {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json') || contentType.includes('+json')) {
    try {
      return await response.json()
    } catch (error) {
      if (error instanceof SyntaxError) {
        throw new Error('Backend trả về JSON không hợp lệ.', { cause: error })
      }
      throw error
    }
  }

  return response.text()
}

function getJobFailureMessage(job) {
  const errorMessage = extractErrorMessage(job.error)
  if (errorMessage) return errorMessage

  const errorCode = job.error?.code
  return errorCode
    ? `Tác vụ nhận diện thất bại (${errorCode}).`
    : 'Tác vụ nhận diện thất bại.'
}

export async function requestRecognition(
  image,
  {
    fetchImpl = fetch,
    sleepImpl = (duration) => new Promise((resolve) => setTimeout(resolve, duration)),
    now = Date.now,
    pollIntervalMs = POLL_INTERVAL_MS,
    longRunningNoticeMs = LONG_RUNNING_NOTICE_MS,
    onLongRunning = () => {},
  } = {},
) {
  const baseUrl = getApiBaseUrl()
  const formData = new FormData()
  formData.append('file', image)

  const createResponse = await fetchResponse(fetchImpl, getJobsUrl(baseUrl), {
    method: 'POST',
    body: formData,
  })
  const createdJob = await readResponseBody(createResponse)

  if (!createResponse.ok) {
    throw new Error(getErrorMessage(createdJob, createResponse.status))
  }

  if (!createdJob || typeof createdJob !== 'object' || Array.isArray(createdJob)) {
    throw new Error('Backend trả về thông tin tác vụ không hợp lệ.')
  }
  if (typeof createdJob.job_id !== 'string' || !createdJob.job_id.trim()) {
    throw new Error('Backend không trả về job_id hợp lệ.')
  }

  const statusUrl = getStatusUrl(createdJob.status_url, baseUrl)
  const startedAt = now()
  let longRunningNotified = false

  while (true) {
    const statusResponse = await fetchResponse(fetchImpl, statusUrl, { method: 'GET' })
    const job = await readResponseBody(statusResponse)

    if (!statusResponse.ok) {
      throw new Error(getErrorMessage(job, statusResponse.status))
    }
    if (!job || typeof job !== 'object' || Array.isArray(job)) {
      throw new Error('Backend trả về trạng thái tác vụ không hợp lệ.')
    }

    if (job.status === 'completed') return job
    if (job.status === 'failed') throw new Error(getJobFailureMessage(job))
    if (job.status !== 'queued' && job.status !== 'processing') {
      throw new Error(`Backend trả về trạng thái tác vụ không được hỗ trợ: ${job.status ?? 'trống'}.`)
    }

    if (!longRunningNotified && now() - startedAt >= longRunningNoticeMs) {
      onLongRunning()
      longRunningNotified = true
    }

    await sleepImpl(pollIntervalMs)
  }
}

export function formatRecognitionResult(result) {
  if (typeof result === 'string') return result
  return JSON.stringify(result, null, 2)
}
