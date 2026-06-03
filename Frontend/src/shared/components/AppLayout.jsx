function AppLayout({ activeStep, steps, children }) {
  return (
    <div className="game-shell">
      <header className="game-header">
        <div className="game-brand">
          <span className="game-brand-mark">UJA</span>
          <span className="game-brand-title">Movie Recommender</span>
        </div>

        <nav className="game-steps" aria-label="Demo steps">
          {steps.map((step) => (
            <div
              key={step.id}
              className={step.id === activeStep ? 'game-step active' : 'game-step'}
            >
              <span>{step.id}</span>
              <strong>{step.title}</strong>
            </div>
          ))}
        </nav>
      </header>

      <main className="game-main">{children}</main>
    </div>
  )
}

export default AppLayout