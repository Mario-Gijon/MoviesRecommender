const STRATEGIES = [
  { value: 'content', label: 'Content' },
  { value: 'collaborative', label: 'Collaborative' },
  { value: 'hybrid', label: 'Hybrid' },
]

function StrategySelector({ value, onChange }) {
  return (
    <div className="game-strategy-tabs" aria-label="Recommendation strategy">
      {STRATEGIES.map((strategy) => (
        <button
          key={strategy.value}
          type="button"
          className={value === strategy.value ? 'game-strategy-button active' : 'game-strategy-button'}
          onClick={() => onChange(strategy.value)}
        >
          {strategy.label}
        </button>
      ))}
    </div>
  )
}

export default StrategySelector