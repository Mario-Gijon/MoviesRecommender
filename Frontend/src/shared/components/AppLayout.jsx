function AppLayout({ activeStep, steps, statusLabel, children }) {
  return (
    <div className="app-shell">
      <header className="wizard-header">
        <div className="hero-panel">
          <p className="eyebrow">Explainable Movies Recommender</p>
          <h1>Explore how recommendation strategies change what gets suggested.</h1>
          <p className="hero-copy">
            Rate a few placeholder movies, review the temporary profile, then generate
            deterministic recommendations with transparent explanations.
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
