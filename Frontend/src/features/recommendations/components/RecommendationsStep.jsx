import { useRef } from 'react'

import useSmoothWheelScroll from '../../../shared/hooks/useSmoothWheelScroll'
import { isStrategyEnabled } from '../strategies'
import AlgorithmSelector from './AlgorithmSelector'
import RecommendationCard from './RecommendationCard'
import StrategySelector from './StrategySelector'

function RecommendationsStep({
  selectedStrategy,
  onSelectStrategy,
  selectedAlgorithm,
  onSelectAlgorithm,
  onGenerateRecommendations,
  recommendations,
  isLoadingRecommendations,
  ratedMoviesCount,
  ratings,
  onRate,
  isStale,
}) {
  const scrollPanelRef = useRef(null)
  const canGenerate =
    ratedMoviesCount > 0 &&
    isStrategyEnabled(selectedStrategy) &&
    !isLoadingRecommendations

  useSmoothWheelScroll(scrollPanelRef)

  return (
    <div className="recommend-game-step compact-recommend-step">
      <div className="recommend-toolbar compact-recommend-toolbar">
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

      {isStale ? (
        <p className="recommendation-stale-notice">Has cambiado tus valoraciones. Vuelve a recomendar para actualizar los resultados.</p>
      ) : null}

      <section ref={scrollPanelRef} className="game-catalog-panel recommendations-stage">
        {recommendations ? (
          <div className="recommendations-panel">
            {recommendations.recommendations.length ? (
              <div className="recommendation-grid">
                {recommendations.recommendations.map((item, index) => (
                  <RecommendationCard
                    key={item.movie.movieId || item.movie.id}
                    item={item}
                    rank={index + 1}
                    rating={ratings[item.movie.movieId || item.movie.id] || null}
                    onRate={onRate}
                  />
                ))}
              </div>
            ) : (
              <div className="game-state"><strong>Ya has valorado todas las películas de esta recomendación.</strong><span>Vuelve a recomendar para obtener nuevas opciones.</span></div>
            )}
          </div>
        ) : (
          <div className="game-state">
            <strong>
              {ratedMoviesCount ? 'Listo para recomendar' : 'Valora algunas películas primero'}
            </strong>
          </div>
        )}
      </section>
    </div>
  )
}

export default RecommendationsStep
