function StepNavigation({
  canGoBack,
  canGoNext,
  nextButtonLabel,
  onBack,
  onNext,
}) {
  return (
    <footer className="game-navigation">
      {canGoBack ? (
        <button type="button" className="game-nav-button secondary" onClick={onBack}>
          Back
        </button>
      ) : (
        <span />
      )}

      {canGoNext ? (
        <button type="button" className="game-nav-button primary" onClick={onNext}>
          {nextButtonLabel}
        </button>
      ) : null}
    </footer>
  )
}

export default StepNavigation