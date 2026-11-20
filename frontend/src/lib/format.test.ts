import { describe, expect, it } from 'vitest'

import { formatDate } from './format'

describe('formatDate', () => {
  it('formats an ISO timestamp in UTC', () => {
    expect(formatDate('2026-11-18T10:05:00Z')).toBe('18 Nov 2026, 10:05')
  })

  it('returns the input when it is not a date', () => {
    expect(formatDate('not a date')).toBe('not a date')
  })
})
