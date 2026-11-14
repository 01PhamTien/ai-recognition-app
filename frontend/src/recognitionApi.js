function getApiUrl() {
  const endpoint = import.meta.env.VITE_RECOGNITION_ENDPOINT?.trim()
  if (endpoint) return endpoint

  const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')
    .trim()
    .replace(/\/+$/, '')
  return `${baseUrl}/api/recognize`
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

export async function requestRecognition(image, { fetchImpl = fetch } = {}) {
  const formData = new FormData()
  formData.append('file', image)

  let response
  try {
    response = await fetchImpl(getApiUrl(), {
      method: 'POST',
      body: formData,
    })
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        'Không kết nối được backend. Hãy kiểm tra backend đang chạy, URL API và cấu hình CORS.',
        { cause: error },
      )
    }
    throw error
  }

  const contentType = response.headers.get('content-type') || ''
  const body = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    throw new Error(getErrorMessage(body, response.status))
  }

  if (body === null || (typeof body === 'string' && !body.trim())) {
    throw new Error('Backend trả về phản hồi rỗng, không có kết quả nhận diện.')
  }

  return body
}

export function formatRecognitionResult(result) {
  if (typeof result === 'string') return result
  return JSON.stringify(result, null, 2)
}
