export const SECTION_TOP_THRESHOLD = 360

export function getScrollBehavior() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ? 'auto'
    : 'smooth'
}

export function scrollToApplicationTop(container, behavior = getScrollBehavior()) {
  if (!container) return
  container.scrollTo({
    top: 0,
    behavior,
  })
}

export function isPastSectionTopThreshold(container) {
  if (!container) return false
  return container.scrollTop > SECTION_TOP_THRESHOLD
}
