export const MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
export const MAX_IMAGE_SIZE_MB = MAX_IMAGE_SIZE_BYTES / (1024 * 1024)

const ALLOWED_IMAGE_TYPES = new Set(['image/jpeg', 'image/jpg', 'image/png'])
const ALLOWED_IMAGE_EXTENSION = /\.(jpe?g|png)$/i

export function validateImage(file) {
  if (!file) {
    return 'Vui lòng chọn một ảnh để tiếp tục.'
  }

  const mimeType = typeof file.type === 'string' ? file.type.toLowerCase().trim() : ''
  const hasSupportedMimeType = mimeType ? ALLOWED_IMAGE_TYPES.has(mimeType) : false
  const hasSupportedExtension = ALLOWED_IMAGE_EXTENSION.test(file.name ?? '')

  if (mimeType && !hasSupportedMimeType) {
    return 'Định dạng chưa được hỗ trợ. Vui lòng chọn ảnh JPG hoặc PNG.'
  }

  if (!mimeType && !hasSupportedExtension) {
    return 'Định dạng chưa được hỗ trợ. Vui lòng chọn ảnh JPG hoặc PNG.'
  }

  if (file.size > MAX_IMAGE_SIZE_BYTES) {
    return `Ảnh vượt quá ${MAX_IMAGE_SIZE_MB} MB. Vui lòng chọn ảnh nhỏ hơn.`
  }

  if (file.size === 0) {
    return 'Tệp ảnh đang trống. Vui lòng chọn một ảnh khác.'
  }

  return ''
}
