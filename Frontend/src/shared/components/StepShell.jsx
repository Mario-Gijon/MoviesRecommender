function StepShell({ errorMessage, children }) {
  return (
    <section className="game-step-shell">
      {errorMessage ? <p className="game-error">{errorMessage}</p> : null}
      {children}
    </section>
  )
}

export default StepShell