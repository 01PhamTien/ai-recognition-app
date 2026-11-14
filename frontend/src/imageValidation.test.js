import { describe, expect, it } from 'vitest'
import { MAX_IMAGE_SIZE_BYTES, validateImage } from './imageValidation.js'

describe('validateImage', () => {
  it('accepts JPG and PNG images', () => {
    expect(validateImage(new File(['image'], 'photo.jpg', { type: 'image/jpeg' }))).toBe('')
    expect(validateImage(new File(['image'], 'photo.png', { type: 'image/png' }))).toBe('')
    expect(validateImage(new File(['image'], 'photo.JPG', { type: 'image/jpeg' }))).toBe('')
  })

  it('rejects unsupported types and empty files', () => {
    expect(validateImage(new File(['text'], 'notes.txt', { type: 'text/plain' }))).toMatch(
      /JPG hoặc PNG/,
    )
    expect(validateImage(new File(['image'], 'photo.jpg', { type: 'image/jpg' }))).toMatch(
      /JPG hoặc PNG/,
    )
    expect(validateImage(new File(['image'], 'fake.jpg', { type: 'image/svg+xml' }))).toMatch(
      /JPG hoặc PNG/,
    )
    expect(validateImage(new File([], 'empty.png', { type: 'image/png' }))).toMatch(
      /trống/,
    )
  })

  it('rejects images larger than the configured maximum', () => {
    const oversizedImage = new File(
      [new Uint8Array(MAX_IMAGE_SIZE_BYTES + 1)],
      'large.png',
      { type: 'image/png' },
    )

    expect(validateImage(oversizedImage)).toMatch(/5 MB/)
  })

  it('asks the user to select an image when no file is provided', () => {
    expect(validateImage(null)).toMatch(/chọn một ảnh/)
  })
})
