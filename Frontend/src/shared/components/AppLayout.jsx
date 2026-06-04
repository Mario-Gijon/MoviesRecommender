function AppLayout({ activeStep, steps, onStepSelect, children }) {
  return (
    <div className="game-shell">
      <header className="game-header">
        <div className="game-brand">
          <span className="game-brand-mark">UJA</span>
          <span className="game-brand-title">Movie Recommender</span>
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
              <strong>{step.title}</strong>
            </button>
          ))}
        </nav>
      </header>

      <main className="game-main">{children}</main>
    </div>
  )
}

export default AppLayout