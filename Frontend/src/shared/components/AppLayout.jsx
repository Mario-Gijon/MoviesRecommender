import { useEffect, useRef } from 'react'

import ScrollToSectionTopButton from './ScrollToSectionTopButton'
import { AppScrollContext } from '../scroll/scrollContext'
import { scrollToApplicationTop } from '../scroll/scrollUtils'

function AppLayout({ activeStep, steps, onStepSelect, sectionControls, children }) {
  const scrollRef = useRef(null)
  const hasMountedRef = useRef(false)

  useEffect(() => {
    if (!hasMountedRef.current) {
      hasMountedRef.current = true
      return
    }

    const container = scrollRef.current
    scrollToApplicationTop(container, 'auto')
  }, [activeStep])

  return (
    <AppScrollContext.Provider value={scrollRef}>
      <div ref={scrollRef} className="game-shell">
        <div className="app-sticky-header">
          <header className="game-header">
            <div className="game-brand">
              <img className="game-brand-logo" src="/sinbad2-logo-white.png" alt="SINBAD2" />
            </div>

            <nav className="game-steps" aria-label="Demo steps">
              {steps.map((step) => (
                <button
                  key={step.id}
                  type="button"
                  className={step.id === activeStep ? 'game-step active' : 'game-step'}
                  onClick={() => onStepSelect(step.id)}
                  aria-current={step.id === activeStep ? 'step' : undefined}
                >
                  <span>{step.id}</span>
                  <div className="game-step-copy">
                    <strong>{step.title}</strong>
                    <small>{step.description}</small>
                  </div>
                </button>
              ))}
            </nav>
          </header>

          <div className="active-section-controls">{sectionControls}</div>
        </div>

        <main className="game-main">{children}</main>
        <ScrollToSectionTopButton
          activeStep={activeStep}
          scrollRef={scrollRef}
        />
      </div>
    </AppScrollContext.Provider>
  )
}

export default AppLayout
