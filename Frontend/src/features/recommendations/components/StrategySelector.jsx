import { RECOMMENDATION_STRATEGIES } from '../strategies'

function StrategySelector({ value, onChange }) {
  return (
    <div className="game-strategy-tabs" aria-label="Estrategia de recomendación">
      {RECOMMENDATION_STRATEGIES.map((strategy) => (
        <button
          key={strategy.value}
          type="button"
          className={value === strategy.value ? 'game-strategy-button active' : 'game-strategy-button'}
          onClick={() => onChange(strategy.value)}
        >
          <span>{strategy.label}</span>
        </button>
      ))}
    </div>
  )
}

export default StrategySelector
