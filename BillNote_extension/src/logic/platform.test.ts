import { describe, expect, it } from 'vitest'
import { detectPlatform } from './platform'

describe('detectPlatform', () => {
  it.each([
    'https://www.bilibili.com/video/BV1hx4y147A8',
    'https://m.bilibili.com/video/av170001',
    'https://b23.tv/abc123',
    'https://www.b23.tv/abc123',
  ])('recognizes supported Bilibili URLs: %s', (url) => {
    expect(detectPlatform(url)).toBe('bilibili')
  })

  it('does not mark a non-video Bilibili page as a video', () => {
    expect(detectPlatform('https://www.bilibili.com/')).toBeNull()
  })
})
