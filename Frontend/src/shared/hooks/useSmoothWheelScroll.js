import { useEffect, useRef } from 'react'

const MIN_SMOOTH_DELTA = 18
const MAX_DELTA = 220
const WHEEL_MULTIPLIER = 0.85
const EASE = 0.18

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function normalizeWheelDelta(event) {
  let delta = event.deltaY

  if (event.deltaMode === WheelEvent.DOM_DELTA_LINE) {
    delta *= 16
  }

  if (event.deltaMode === WheelEvent.DOM_DELTA_PAGE) {
    delta *= window.innerHeight
  }

  return clamp(delta, -MAX_DELTA, MAX_DELTA) * WHEEL_MULTIPLIER
}

function useSmoothWheelScroll(scrollRef) {
  const targetScrollTopRef = useRef(0)
  const frameRef = useRef(null)
  const isDraggingScrollbarRef = useRef(false)

  useEffect(() => {
    const element = scrollRef.current

    if (!element) {
      return undefined
    }

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (prefersReducedMotion) {
      return undefined
    }

    targetScrollTopRef.current = element.scrollTop

    function cancelFrame() {
      if (frameRef.current) {
        window.cancelAnimationFrame(frameRef.current)
        frameRef.current = null
      }
    }

    function syncTargetWithCurrentScroll() {
      targetScrollTopRef.current = element.scrollTop
    }

    function animateScroll() {
      if (isDraggingScrollbarRef.current) {
        cancelFrame()
        syncTargetWithCurrentScroll()
        return
      }

      const distance = targetScrollTopRef.current - element.scrollTop

      if (Math.abs(distance) < 0.5) {
        element.scrollTop = targetScrollTopRef.current
        frameRef.current = null
        return
      }

      element.scrollTop += distance * EASE
      frameRef.current = window.requestAnimationFrame(animateScroll)
    }

    function handleWheel(event) {
      if (event.ctrlKey || event.shiftKey || isDraggingScrollbarRef.current) {
        return
      }

      const delta = normalizeWheelDelta(event)

      /*
       * Trackpads already send small continuous deltas.
       * We only smooth bigger mouse-wheel jumps.
       */
      if (Math.abs(delta) < MIN_SMOOTH_DELTA) {
        syncTargetWithCurrentScroll()
        return
      }

      const maxScrollTop = element.scrollHeight - element.clientHeight

      if (maxScrollTop <= 0) {
        return
      }

      const movingUp = delta < 0
      const movingDown = delta > 0
      const atTop = element.scrollTop <= 0 && targetScrollTopRef.current <= 0
      const atBottom =
        element.scrollTop >= maxScrollTop - 1 &&
        targetScrollTopRef.current >= maxScrollTop - 1

      if ((movingUp && atTop) || (movingDown && atBottom)) {
        syncTargetWithCurrentScroll()
        return
      }

      event.preventDefault()

      targetScrollTopRef.current = clamp(
        targetScrollTopRef.current + delta,
        0,
        maxScrollTop,
      )

      if (!frameRef.current) {
        frameRef.current = window.requestAnimationFrame(animateScroll)
      }
    }

    function handleManualScrollStart() {
      isDraggingScrollbarRef.current = true
      cancelFrame()
      syncTargetWithCurrentScroll()
    }

    function handleManualScrollEnd() {
      isDraggingScrollbarRef.current = false
      syncTargetWithCurrentScroll()
    }

    function handleNativeScroll() {
      if (!frameRef.current || isDraggingScrollbarRef.current) {
        syncTargetWithCurrentScroll()
      }
    }

    element.addEventListener('wheel', handleWheel, { passive: false })
    element.addEventListener('scroll', handleNativeScroll, { passive: true })

    /*
     * These events are important because dragging the scrollbar is native browser behavior.
     * We cancel the custom animation immediately so it cannot fight the scrollbar thumb.
     */
    element.addEventListener('pointerdown', handleManualScrollStart, { passive: true })
    element.addEventListener('mousedown', handleManualScrollStart, { passive: true })
    element.addEventListener('touchstart', handleManualScrollStart, { passive: true })
    element.addEventListener('keydown', handleManualScrollStart)

    window.addEventListener('pointerup', handleManualScrollEnd, { passive: true })
    window.addEventListener('mouseup', handleManualScrollEnd, { passive: true })
    window.addEventListener('touchend', handleManualScrollEnd, { passive: true })
    window.addEventListener('blur', handleManualScrollEnd)

    return () => {
      cancelFrame()

      element.removeEventListener('wheel', handleWheel)
      element.removeEventListener('scroll', handleNativeScroll)
      element.removeEventListener('pointerdown', handleManualScrollStart)
      element.removeEventListener('mousedown', handleManualScrollStart)
      element.removeEventListener('touchstart', handleManualScrollStart)
      element.removeEventListener('keydown', handleManualScrollStart)

      window.removeEventListener('pointerup', handleManualScrollEnd)
      window.removeEventListener('mouseup', handleManualScrollEnd)
      window.removeEventListener('touchend', handleManualScrollEnd)
      window.removeEventListener('blur', handleManualScrollEnd)
    }
  }, [scrollRef])
}

export default useSmoothWheelScroll