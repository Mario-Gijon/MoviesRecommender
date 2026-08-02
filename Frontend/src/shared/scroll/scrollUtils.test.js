import { expect, test } from 'bun:test'

import {
  SECTION_TOP_THRESHOLD,
  isPastSectionTopThreshold,
  scrollToApplicationTop,
} from './scrollUtils'

test('the return button remains hidden until the active section is meaningfully scrolled', () => {
  const container = { scrollTop: 459 }
  expect(isPastSectionTopThreshold(container)).toBe(true)

  container.scrollTop = 360
  expect(isPastSectionTopThreshold(container)).toBe(false)
  expect(SECTION_TOP_THRESHOLD).toBeGreaterThanOrEqual(300)
  expect(SECTION_TOP_THRESHOLD).toBeLessThanOrEqual(450)
})

test('returning to the application top uses native smooth scrolling', () => {
  const calls = []
  const container = { scrollTo: (options) => calls.push(options) }
  globalThis.window = {
    matchMedia: () => ({ matches: false }),
  }

  scrollToApplicationTop(container)

  expect(calls).toEqual([{ top: 0, behavior: 'smooth' }])
  delete globalThis.window
})

test('reduced-motion users return to the section without animation', () => {
  const calls = []
  const container = { scrollTo: (options) => calls.push(options) }
  globalThis.window = {
    matchMedia: () => ({ matches: true }),
  }

  scrollToApplicationTop(container)

  expect(calls).toEqual([{ top: 0, behavior: 'auto' }])
  delete globalThis.window
})
