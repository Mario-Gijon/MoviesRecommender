const STRATEGIES = [
  { value: 'content', label: 'Content' },
  { value: 'collaborative', label: 'Collaborative' },
  { value: 'hybrid', label: 'Hybrid' },
]

function StrategySelector({ value, onChange }) {
  return (
    <div className="strategy-row">
      {STRATEGIES.map((strategy) => (
        <button
          key={strategy.value}
          type="button"
          className={value === strategy.value ? 'strategy-button active' : 'strategy-button'}
          onClick={() => onChange(strategy.value)}
        >
          {strategy.label}
        </button>
      ))}
    </div>
  )
}

export default StrategySelector

