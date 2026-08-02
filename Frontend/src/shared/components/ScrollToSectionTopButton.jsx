import { useEffect, useState } from 'react'

import {
  isPastSectionTopThreshold,
  scrollToApplicationTop,
} from '../scroll/scrollUtils'

function ScrollToSectionTopButton({
  activeStep,
  scrollRef,
  onBeforeScroll,
}) {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const container = scrollRef.current

    if (!container) {
      return undefined
    }

    function updateVisibility() {
      setIsVisible(
        isPastSectionTopThreshold(container),
      )
    }

    setIsVisible(false)
    updateVisibility()

    container.addEventListener(
      'scroll',
      updateVisibility,
      { passive: true },
    )

    return () => {
      container.removeEventListener(
        'scroll',
        updateVisibility,
      )
    }
  }, [activeStep, scrollRef])

  function handleScrollToSectionTop() {
    onBeforeScroll?.()
    scrollToApplicationTop(scrollRef.current)
  }

  return (
    <button
      type="button"
      className={
        `section-top-button${isVisible ? ' visible' : ''}`
      }
      aria-label="Volver al inicio de la sección"
      onClick={handleScrollToSectionTop}
    >
      ↑
    </button>
  )
}

export default ScrollToSectionTopButton