import { describe, it, expect } from 'vitest'
import { isLatestPreviewRequest } from './previewController'

describe('candidate preview race guard (B2)', () => {
  it('only the latest dispatched request may apply its result', () => {
    // req 1 dispatched, then req 2 dispatched (latest = 2): req 1's late result drops.
    expect(isLatestPreviewRequest(1, 2)).toBe(false)
    expect(isLatestPreviewRequest(2, 2)).toBe(true)
  })
})
