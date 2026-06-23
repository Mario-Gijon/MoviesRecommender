import { RECOMMENDATION_STRATEGIES } from '../strategies'

function StrategySelector({ value, onChange }) {
  return (
    <div className="game-strategy-tabs" aria-label="Recommendation strategy">
      {RECOMMENDATION_STRATEGIES.map((strategy) => (
        <button
          key={strategy.value}
          type="button"
          className={value === strategy.value ? 'game-strategy-button active' : 'game-strategy-button'}
          onClick={() => onChange(strategy.value)}
          disabled={strategy.disabled}
        >
          <span>{strategy.label}</span>
          <small>{strategy.status}</small>
        </button>
      ))}
    </div>
  )
}

export default StrategySelector
