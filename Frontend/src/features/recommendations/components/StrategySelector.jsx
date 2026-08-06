import { RECOMMENDATION_STRATEGIES } from '../strategies'

function StrategySelector({ value, onChange }) {
  return (
    <div
      className="game-strategy-tabs"
      aria-label="Estrategia de recomendación"
      data-strategy={value}
    >
      {RECOMMENDATION_STRATEGIES.map((strategy) => (
        <button
          key={strategy.value}
          type="button"
          aria-label={strategy.label}
          className={value === strategy.value ? 'game-strategy-button active' : 'game-strategy-button'}
          onClick={() => onChange(strategy.value)}
        >
          <span className="game-strategy-label-full">{strategy.label}</span>
          <span className="game-strategy-label-short" aria-hidden="true">
            {strategy.value === 'content' ? 'Contenido' : 'Colaborativo'}
          </span>
        </button>
      ))}
    </div>
  )
}

export default StrategySelector
