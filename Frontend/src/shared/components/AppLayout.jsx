import { useEffect, useRef, useState } from 'react'

import ScrollToSectionTopButton from './ScrollToSectionTopButton'
import { AppScrollContext } from '../scroll/scrollContext'
import { scrollToApplicationTop } from '../scroll/scrollUtils'

const HEADER_HIDE_START = 120
const HEADER_SCROLL_THRESHOLD = 8
const HEADER_TOP_ZONE = 24

function AppLayout({
  activeStep,
  steps,
  onStepSelect,
  sectionControls,
  children,
}) {
  const scrollRef = useRef(null)
  const headerRef = useRef(null)
  const hasMountedRef = useRef(false)
  const lastRelevantScrollTopRef = useRef(0)
  const animationFrameRef = useRef(null)
  const keyboardNavigationRef = useRef(false)

  const [isHeaderHidden, setIsHeaderHidden] = useState(false)

  function showHeader() {
    setIsHeaderHidden(false)
  }

  /*
   * Diferenciamos foco de teclado y foco provocado por ratón.
   * Un clic deja el botón enfocado, pero no debe impedir que
   * el header vuelva a ocultarse al hacer scroll.
   */
  useEffect(() => {
    function handleKeyboardInput(event) {
      if (event.key === 'Tab') {
        keyboardNavigationRef.current = true
      }
    }

    function handlePointerInput() {
      keyboardNavigationRef.current = false
    }

    window.addEventListener('keydown', handleKeyboardInput, true)
    window.addEventListener('pointerdown', handlePointerInput, true)

    return () => {
      window.removeEventListener(
        'keydown',
        handleKeyboardInput,
        true,
      )

      window.removeEventListener(
        'pointerdown',
        handlePointerInput,
        true,
      )
    }
  }, [])

  useEffect(() => {
    const container = scrollRef.current

    if (!container) {
      return undefined
    }

    lastRelevantScrollTopRef.current = container.scrollTop

    function updateHeaderVisibility() {
      animationFrameRef.current = null

      const scrollTop = Math.max(0, container.scrollTop)
      const previousScrollTop =
        lastRelevantScrollTopRef.current

      const scrollDifference =
        scrollTop - previousScrollTop

      const headerHasKeyboardFocus =
        keyboardNavigationRef.current &&
        headerRef.current?.contains(document.activeElement)

      /*
       * Si hay un dropdown abierto, no ocultamos el header.
       * Esto cubre el selector de algoritmos.
       */
      const headerHasExpandedControl = Boolean(
        headerRef.current?.querySelector(
          '[aria-expanded="true"]',
        ),
      )

      if (
        scrollTop <= HEADER_TOP_ZONE ||
        headerHasKeyboardFocus ||
        headerHasExpandedControl
      ) {
        setIsHeaderHidden(false)
        lastRelevantScrollTopRef.current = scrollTop
        return
      }

      /*
       * Ignora pequeños movimientos de trackpad o táctiles.
       * No actualizamos la referencia para que esos pequeños
       * movimientos se acumulen hasta formar una dirección clara.
       */
      if (
        Math.abs(scrollDifference) <
        HEADER_SCROLL_THRESHOLD
      ) {
        return
      }

      if (
        scrollDifference > 0 &&
        scrollTop > HEADER_HIDE_START
      ) {
        setIsHeaderHidden(true)
      } else if (scrollDifference < 0) {
        setIsHeaderHidden(false)
      }

      lastRelevantScrollTopRef.current = scrollTop
    }

    function handleScroll() {
      if (animationFrameRef.current !== null) {
        return
      }

      animationFrameRef.current =
        window.requestAnimationFrame(
          updateHeaderVisibility,
        )
    }

    container.addEventListener('scroll', handleScroll, {
      passive: true,
    })

    return () => {
      container.removeEventListener(
        'scroll',
        handleScroll,
      )

      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(
          animationFrameRef.current,
        )
      }
    }
  }, [])

  useEffect(() => {
    if (!hasMountedRef.current) {
      hasMountedRef.current = true
      return
    }

    showHeader()
    lastRelevantScrollTopRef.current = 0
    scrollToApplicationTop(scrollRef.current, 'auto')
  }, [activeStep])

  function handleStepClick(stepId) {
    showHeader()

    /*
     * Pulsar la sección ya seleccionada también vuelve arriba.
     * Como activeStep no cambia, el useEffect no se ejecutaría.
     */
    if (stepId === activeStep) {
      lastRelevantScrollTopRef.current = 0
      scrollToApplicationTop(scrollRef.current, 'auto')
      return
    }

    onStepSelect(stepId)
  }

  const stickyHeaderClassName = [
    'app-sticky-header',
    isHeaderHidden ? 'is-hidden' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <AppScrollContext.Provider value={scrollRef}>
      <div ref={scrollRef} className="game-shell">
        <div
          ref={headerRef}
          className={stickyHeaderClassName}
          onFocusCapture={() => {
            if (keyboardNavigationRef.current) {
              showHeader()
            }
          }}
        >
          <header className="game-header">
            <div className="game-brand">
              <img
                className="game-brand-logo"
                src="/sinbad2-logo-white.png"
                alt="SINBAD2"
              />
            </div>

            <nav
              className="game-steps"
              aria-label="Pasos de la aplicación"
            >
              {steps.map((step) => (
                <button
                  key={step.id}
                  type="button"
                  className={
                    step.id === activeStep
                      ? 'game-step active'
                      : 'game-step'
                  }
                  onClick={() => handleStepClick(step.id)}
                  aria-label={`${step.title}: ${step.description}`}
                  aria-current={
                    step.id === activeStep
                      ? 'step'
                      : undefined
                  }
                >
                  <span className="game-step-number">{step.id}</span>

                  <div className="game-step-copy">
                    <strong>
                      <span className="game-step-title-full">{step.title}</span>
                      <span className="game-step-title-short">{step.shortTitle}</span>
                      <span className="game-step-title-narrow">{step.narrowTitle}</span>
                    </strong>
                    <small>{step.description}</small>
                  </div>
                </button>
              ))}
            </nav>
          </header>

          <div className="active-section-controls">
            {sectionControls}
          </div>
        </div>

        <main className="game-main">
          {children}
        </main>

        <ScrollToSectionTopButton
          activeStep={activeStep}
          scrollRef={scrollRef}
          onBeforeScroll={showHeader}
        />
      </div>
    </AppScrollContext.Provider>
  )
}

export default AppLayout
