import { useRef } from 'react'

import useSmoothWheelScroll from '../../../shared/hooks/useSmoothWheelScroll'
import RecommendationCard from './RecommendationCard'
import RecommendationProfileSummary from './RecommendationProfileSummary'

function RecommendationsStep({
  onGenerateRecommendations,
  recommendations,
  isLoadingRecommendations,
  ratedMoviesCount,
}) {
  const scrollPanelRef = useRef(null)
  const canGenerate = ratedMoviesCount > 0 && !isLoadingRecommendations

  useSmoothWheelScroll(scrollPanelRef)

  return (
    <div className="recommend-game-step compact-recommend-step">
      <div className="recommend-toolbar compact-recommend-toolbar">
        <button
          type="button"
          className="game-nav-button primary generate-button"
          onClick={onGenerateRecommendations}
          disabled={!canGenerate}
        >
          {isLoadingRecommendations ? 'Generando...' : 'Recomendar'}
        </button>
      </div>

      <section ref={scrollPanelRef} className="game-catalog-panel recommendations-stage">
        {recommendations ? (
          <div className="recommendations-panel">
            <RecommendationProfileSummary profile={recommendations.profile} />

            <div className="recommendation-grid">
              {recommendations.recommendations.map((item, index) => (
                <RecommendationCard key={item.movieId} item={item} rank={index + 1} />
              ))}
            </div>
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