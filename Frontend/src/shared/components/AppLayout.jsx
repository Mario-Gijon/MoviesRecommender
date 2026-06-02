function AppLayout({ activeStep, steps, statusLabel, children }) {
  return (
    <div className="app-shell">
      <header className="wizard-header">
        <div className="hero-panel">
          <p className="eyebrow">Explainable Movie Recommender</p>
          <h1>Rate. Choose a method. Understand the recommendation.</h1>
          <p className="hero-copy">
            A short interactive demo about content-based, collaborative and hybrid
            recommendation strategies.
          </p>
        </div>
        <div className="progress-panel">
          <div className="status-row">
            <strong>Backend:</strong>
            <span>{statusLabel}</span>
          </div>
          <div className="step-dots" aria-label="Wizard progress">
            {steps.map((step) => (
              <div
                key={step.id}
                className={step.id === activeStep ? 'step-dot active' : 'step-dot'}
              >
                <span className="step-dot-index">{step.id}</span>
                <span className="step-dot-label">{step.title}</span>
              </div>
            ))}
          </div>
        </div>
      </header>
      <main className="wizard-main">{children}</main>
    </div>
  )
}

export default AppLayout
