import { isStrategyEnabled } from '../strategies'
import AlgorithmSelector from './AlgorithmSelector'
import StrategySelector from './StrategySelector'

function RecommendationControls({
  selectedStrategy,
  onSelectStrategy,
  selectedAlgorithm,
  onSelectAlgorithm,
  onGenerateRecommendations,
  isLoadingRecommendations,
  ratedMoviesCount,
}) {
  const canGenerate =
    ratedMoviesCount > 0 &&
    isStrategyEnabled(selectedStrategy) &&
    !isLoadingRecommendations

  return (
    <div
      className={`recommend-toolbar compact-recommend-toolbar ${
        selectedStrategy === 'collaborative' ? 'has-algorithm' : 'content-only'
      }`}
    >
      <StrategySelector value={selectedStrategy} onChange={onSelectStrategy} />

      {selectedStrategy === 'collaborative' ? (
        <AlgorithmSelector
          strategy={selectedStrategy}
          value={selectedAlgorithm}
          onChange={onSelectAlgorithm}
        />
      ) : null}

      <button
        type="button"
        className="game-nav-button primary generate-button"
        onClick={onGenerateRecommendations}
        disabled={!canGenerate}
      >
        {isLoadingRecommendations ? 'Generando...' : 'Recomendar'}
      </button>
    </div>
  )
}

export default RecommendationControls
