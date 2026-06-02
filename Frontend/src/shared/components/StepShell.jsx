function StepShell({ eyebrow, title, description, errorMessage, children }) {
  return (
    <section className="step-shell">
      <header className="step-header">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
        <p className="section-copy">{description}</p>
      </header>
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
      <div className="step-content">{children}</div>
    </section>
  )
}

export default StepShell

