function StepNavigation({
  activeStep,
  totalSteps,
  canGoBack,
  canGoNext,
  nextButtonLabel,
  onBack,
  onNext,
  hint,
}) {
  return (
    <footer className="wizard-footer">
      <div className="wizard-footer-copy">
        <p className="footer-step-label">
          Step {activeStep} of {totalSteps}
        </p>
        {hint ? <p className="helper-text">{hint}</p> : null}
      </div>
      <div className="footer-actions">
        <button type="button" className="secondary-button" onClick={onBack} disabled={!canGoBack}>
          Back
        </button>
        <button type="button" className="primary-button" onClick={onNext} disabled={!canGoNext}>
          {nextButtonLabel}
        </button>
      </div>
    </footer>
  )
}

export default StepNavigation

