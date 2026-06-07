function AppLayout({ activeStep, steps, onStepSelect, children }) {
  return (
    <div className="game-shell">
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

      <main className="game-main">{children}</main>
    </div>
  )
}

export default AppLayout
