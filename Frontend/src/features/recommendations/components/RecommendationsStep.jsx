import { useState } from 'react'

import { isStrategyEnabled } from '../strategies'
import RecommendationCard from './RecommendationCard'

function RecommendationsStep({
  selectedStrategy,
  onGenerateRecommendations,
  recommendations,
  isLoadingRecommendations,
  ratedMoviesCount,
  ratings,
  onRate,
  isStale,
}) {
  const [openRecommendationId, setOpenRecommendationId] = useState(null)

  const canGenerate =
    ratedMoviesCount > 0 &&
    isStrategyEnabled(selectedStrategy) &&
    !isLoadingRecommendations

  return (
    <div className="recommend-game-step compact-recommend-step">
      {isStale ? (
        <div className="recommendation-top-area">
          <div
            className="recommendation-refresh-banner"
            role="status"
            aria-live="polite"
          >
            <span
              className="recommendation-refresh-icon"
              aria-hidden="true"
            >
              ✦
            </span>

            <div className="recommendation-refresh-copy">
              <strong>
                Puedo mejorar la recomendación
              </strong>

              <span>
                Tendré en cuenta tus nuevas valoraciones.
              </span>
            </div>

            <button
              type="button"
              className="recommendation-refresh-button"
              onClick={onGenerateRecommendations}
              disabled={!canGenerate}
            >
              {isLoadingRecommendations
                ? 'Mejorando...'
                : 'Mejorar'}
            </button>
          </div>
        </div>
      ) : null}

      <section className="game-catalog-panel recommendations-stage">
        {recommendations ? (
          <div className="recommendations-panel">
            {recommendations.recommendations.length ? (
              <div className="recommendation-grid">
                {recommendations.recommendations.map((item, index) => {
                  const movieId =
                    item.movie.movieId || item.movie.id

                  return (
                    <RecommendationCard
                      key={movieId}
                      item={item}
                      rank={index + 1}
                      rating={ratings[movieId] || null}
                      onRate={onRate}
                      isTouchOpen={openRecommendationId === movieId}
                      onToggleTouch={() => {
                        setOpenRecommendationId((currentMovieId) =>
                          currentMovieId === movieId ? null : movieId,
                        )
                      }}
                    />
                  )
                })}
              </div>
            ) : (
              <div className="game-state">
                <strong>
                  Ya has valorado todas estas películas
                </strong>

                <span>
                  Vuelve a recomendar para descubrir otras.
                </span>
              </div>
            )}
          </div>
        ) : (
          <div className="game-state">
            <strong>
              {ratedMoviesCount
                ? 'Listo para recomendar'
                : 'Valora algunas películas primero'}
            </strong>
          </div>
        )}
      </section>
    </div>
  )
}

export default RecommendationsStep
