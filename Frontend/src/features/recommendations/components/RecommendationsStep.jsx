import { useState } from 'react'

import {
  getRecommendationRatingCta,
  hasMinimumRecommendationRatings,
  isStrategyEnabled,
} from '../strategies'
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
  guidanceMessage,
  onNavigateToRating,
}) {
  const [openRecommendationId, setOpenRecommendationId] = useState(null)
  const needsMoreRatings = !hasMinimumRecommendationRatings(ratedMoviesCount)
  const staleBannerNeedsRatings = isStale && needsMoreRatings
  const showStandaloneGuidance = Boolean(
    guidanceMessage && recommendations && !isStale,
  )

  const canGenerate =
    hasMinimumRecommendationRatings(ratedMoviesCount) &&
    isStrategyEnabled(selectedStrategy) &&
    !isLoadingRecommendations

  return (
    <div className="recommend-game-step compact-recommend-step">
      {isStale || showStandaloneGuidance ? (
        <div className="recommendation-top-area">
          {showStandaloneGuidance ? (
            <div className="recommendation-minimum-guidance" role="status" aria-live="polite">
              <span className="recommendation-minimum-guidance-icon" aria-hidden="true">
                ✦
              </span>

              <span>{guidanceMessage}</span>
            </div>
          ) : null}

          {isStale ? (
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
                  {staleBannerNeedsRatings
                    ? 'Necesito alguna valoración más'
                    : 'Puedo mejorar la recomendación'}
                </strong>

                <span>
                  {staleBannerNeedsRatings
                    ? getRecommendationRatingCta(ratedMoviesCount)
                    : 'Tendré en cuenta tus nuevas valoraciones.'}
                </span>
              </div>

              <button
                type="button"
                className="recommendation-refresh-button"
                onClick={staleBannerNeedsRatings
                  ? onNavigateToRating
                  : onGenerateRecommendations}
                disabled={staleBannerNeedsRatings ? false : !canGenerate}
              >
                {staleBannerNeedsRatings
                  ? 'Valorar películas'
                  : isLoadingRecommendations
                    ? 'Mejorando...'
                    : 'Mejorar'}
              </button>
            </div>
          ) : null}
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
              {guidanceMessage
                ? 'Completa tu perfil de gustos'
                : ratedMoviesCount
                  ? 'Listo para recomendar'
                  : 'Valora algunas películas primero'}
            </strong>

            {guidanceMessage ? <span>{guidanceMessage}</span> : null}
          </div>
        )}
      </section>
    </div>
  )
}

export default RecommendationsStep
