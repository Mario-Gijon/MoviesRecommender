import {
  hasMinimumRecommendationRatings,
  isStrategyEnabled,
} from '../strategies'
import StrategySelector from './StrategySelector'

function RecommendationControls({
  selectedStrategy,
  onSelectStrategy,
  onGenerateRecommendations,
  isLoadingRecommendations,
  ratedMoviesCount,
}) {
  const canGenerate =
    hasMinimumRecommendationRatings(ratedMoviesCount) &&
    isStrategyEnabled(selectedStrategy) &&
    !isLoadingRecommendations

  return (
    <div className="recommend-toolbar compact-recommend-toolbar">
      <StrategySelector value={selectedStrategy} onChange={onSelectStrategy} />

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
