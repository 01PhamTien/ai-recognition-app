import { useEffect, useRef, useState } from 'react'
import { MAX_IMAGE_SIZE_MB, validateImage } from './imageValidation.js'
import { formatConfidence, requestRecognition } from './recognitionApi.js'

function ImageGlyph({ className = '' }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      viewBox="0 0 24 24"
    >
      <rect
        x="3.5"
        y="4.5"
        width="17"
        height="15"
        rx="2.5"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <circle cx="9" cy="10" r="1.5" fill="currentColor" />
      <path
        d="m5 17 4.2-4.1a1.2 1.2 0 0 1 1.7 0l1.5 1.4 2.2-2.2a1.2 1.2 0 0 1 1.7 0l3.2 3.2"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.7"
      />
    </svg>
  )
}

function UploadGlyph() {
  return (
    <svg aria-hidden="true" fill="none" viewBox="0 0 32 32">
      <path
        d="M16 21V7m0 0-5.5 5.5M16 7l5.5 5.5M7 20v5a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  )
}

function formatFileSize(size) {
  return size < 1024 * 1024
    ? `${Math.max(1, Math.round(size / 1024))} KB`
    : `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export default function App() {
  const inputRef = useRef(null)
  const [selectedImage, setSelectedImage] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [error, setError] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isTakingLong, setIsTakingLong] = useState(false)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!selectedImage) {
      setPreviewUrl('')
      return undefined
    }

    const objectUrl = URL.createObjectURL(selectedImage)
    setPreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [selectedImage])

  function chooseImage(file) {
    const validationError = validateImage(file)
    if (validationError) {
      setError(validationError)
      return
    }

    setSelectedImage(file)
    setError('')
    setResult(null)
  }

  function handleInputChange(event) {
    const [file] = event.target.files ?? []
    if (file) chooseImage(file)
    event.target.value = ''
  }

  function removeImage() {
    if (isSubmitting) return
    setSelectedImage(null)
    setError('')
    setResult(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  async function submitImage() {
    if (!selectedImage || isSubmitting) return

    setIsSubmitting(true)
    setIsTakingLong(false)
    setError('')
    setResult(null)

    try {
      const recognitionResult = await requestRecognition(selectedImage, {
        onLongRunning: () => setIsTakingLong(true),
      })
      setResult(recognitionResult)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Đã xảy ra lỗi không xác định khi gửi ảnh.',
      )
    } finally {
      setIsSubmitting(false)
      setIsTakingLong(false)
    }
  }

  function handleDrop(event) {
    event.preventDefault()
    setIsDragging(false)
    const [file] = event.dataTransfer.files
    if (file) chooseImage(file)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a aria-label="AI Vision — Trang chủ" className="brand" href="/">
          <span className="brand-mark">
            <ImageGlyph />
          </span>
          <span>AI Vision</span>
        </a>
        <span className="topbar-label">NHẬN DIỆN HÌNH ẢNH</span>
      </header>

      <main className="main-content">
        <section aria-labelledby="page-title" className="upload-section">
          <div className="eyebrow">
            <span className="eyebrow-dot" />
            AI IMAGE RECOGNITION
          </div>
          <h1 id="page-title">Khám phá hình ảnh của bạn</h1>
          <p className="intro">
            Tải lên một hình ảnh và để AI giúp bạn tìm hiểu những gì có trong đó.
          </p>

          <div className="upload-card">
            <div className="card-heading">
              <div>
                <h2>Tải ảnh lên</h2>
                <p>Chọn một ảnh để bắt đầu quá trình nhận diện.</p>
              </div>
              <span className="step-badge">BƯỚC 01</span>
            </div>

            {selectedImage ? (
              <div className="preview-card">
                <img
                  alt={`Xem trước ${selectedImage.name}`}
                  className="image-preview"
                  src={previewUrl || undefined}
                />
                <div className="file-details">
                  <div className="file-icon">
                    <ImageGlyph />
                  </div>
                  <div className="file-copy">
                    <p className="file-name">{selectedImage.name}</p>
                    <p className="file-size">
                      {formatFileSize(selectedImage.size)} · Đã sẵn sàng
                    </p>
                  </div>
                  <button
                    aria-label="Xóa ảnh đã chọn"
                    className="icon-button"
                    disabled={isSubmitting}
                    onClick={removeImage}
                    type="button"
                  >
                    <svg aria-hidden="true" fill="none" viewBox="0 0 20 20">
                      <path
                        d="m5 5 10 10M15 5 5 15"
                        stroke="currentColor"
                        strokeLinecap="round"
                        strokeWidth="1.7"
                      />
                    </svg>
                  </button>
                </div>
                <button
                  className="change-image"
                  disabled={isSubmitting}
                  onClick={() => inputRef.current?.click()}
                  type="button"
                >
                  Chọn ảnh khác
                </button>
              </div>
            ) : (
              <div
                className={`drop-zone${isDragging ? ' is-dragging' : ''}`}
                onDragEnter={(event) => {
                  event.preventDefault()
                  setIsDragging(true)
                }}
                onDragLeave={(event) => {
                  event.preventDefault()
                  setIsDragging(false)
                }}
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
              >
                <div className="upload-icon">
                  <UploadGlyph />
                </div>
                <p className="drop-title">Kéo thả ảnh vào đây</p>
                <p className="drop-subtitle">hoặc chọn ảnh từ thiết bị</p>
                <button
                  className="browse-button"
                  onClick={() => inputRef.current?.click()}
                  type="button"
                >
                  Chọn ảnh
                </button>
                <p className="file-hint">
                  Hỗ trợ JPG, PNG <span>·</span> Tối đa {MAX_IMAGE_SIZE_MB} MB
                </p>
              </div>
            )}

            <input
              ref={inputRef}
              accept="image/jpeg,image/png,.jpg,.jpeg,.png"
              aria-label="Chọn tệp ảnh"
              className="visually-hidden"
              onChange={handleInputChange}
              type="file"
            />

            {error && (
              <p className="error-message" role="alert">
                <span aria-hidden="true">!</span>
                {error}
              </p>
            )}

            <button
              className="submit-button"
              disabled={!selectedImage || isSubmitting}
              onClick={submitImage}
              type="button"
            >
              {isSubmitting ? (
                <>
                  <span aria-hidden="true" className="loading-spinner" />
                  <span>Đang nhận diện ảnh...</span>
                </>
              ) : (
                <>
                  <span>Gửi yêu cầu nhận diện</span>
                  <svg aria-hidden="true" fill="none" viewBox="0 0 20 20">
                    <path
                      d="M4 10h12m-5-5 5 5-5 5"
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="1.7"
                    />
                  </svg>
                </>
              )}
            </button>
            {isSubmitting && (
              <p className="api-notice" role="status">
                {isTakingLong
                  ? 'Tác vụ vẫn đang được xử lý. Vui lòng tiếp tục chờ kết quả.'
                  : 'Ảnh đang được gửi tới backend để xử lý.'}
              </p>
            )}

            {result !== null && (
              <section
                aria-labelledby="result-title"
                aria-live="polite"
                className="result-panel"
              >
                <h3 id="result-title">Kết quả nhận diện</h3>
                {Array.isArray(result.predictions) && result.predictions.length > 0 ? (
                  <ol className="prediction-list">
                    {result.predictions.map((prediction, index) => (
                      <li key={`${prediction.class_id ?? 'label'}-${prediction.label ?? index}`}>
                        <span className="prediction-label">
                          {prediction.label || 'Không rõ nhãn'}
                        </span>
                        <span className="prediction-confidence">
                          {formatConfidence(prediction.confidence)}
                        </span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="empty-predictions">Không tìm thấy nhãn phù hợp trong ảnh.</p>
                )}
                {result.model_version ? (
                  <p className="model-version">Mô hình: {result.model_version}</p>
                ) : null}
              </section>
            )}
          </div>

          <div className="privacy-note">
            <svg aria-hidden="true" fill="none" viewBox="0 0 20 20">
              <path
                d="M10 2.5 3.5 5v4.4c0 3.8 2.7 6.7 6.5 8.1 3.8-1.4 6.5-4.3 6.5-8.1V5L10 2.5Z"
                stroke="currentColor"
                strokeLinejoin="round"
                strokeWidth="1.4"
              />
              <path
                d="m7.5 9.8 1.7 1.7 3.5-3.6"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.4"
              />
            </svg>
            <span>Ảnh của bạn chỉ được xử lý khi gửi yêu cầu nhận diện.</span>
          </div>
        </section>
      </main>

      <footer className="footer">
        <span>AI Vision</span>
        <span>Nhận diện hình ảnh bằng trí tuệ nhân tạo</span>
      </footer>
    </div>
  )
}
