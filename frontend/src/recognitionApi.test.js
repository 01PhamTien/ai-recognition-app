import { describe, expect, it, vi } from 'vitest'
import { requestRecognition } from './recognitionApi.js'

describe('requestRecognition', () => {
  it('extracts nested backend error messages from JSON responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: { message: 'Model chưa sẵn sàng.' } }), {
          status: 503,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    )

    await expect(
      requestRecognition(new File(['image'], 'cat.png', { type: 'image/png' })),
    ).rejects.toThrow('Model chưa sẵn sàng.')

    vi.unstubAllGlobals()
  })
})
