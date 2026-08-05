import { useEffect, useRef, useState } from 'react'

import MovieRatingControl from '../../movies/components/MovieRatingControl'
import { getMovieDisplayTitle } from '../../movies/movieDisplay'

const EXIT_ANIMATION_MS = 520

function RecommendationCard({
  item,
  rank,
  rating,
  onRate,
  isTouchOpen = false,
  onToggleTouch,
}) {
  const [isLeaving, setIsLeaving] = useState(false)
  const [exitRating, setExitRating] = useState(null)
  const exitTimeoutRef = useRef(null)

  const movie = item.movie
  const movieTitle = getMovieDisplayTitle(movie)

  const numericScore = Number(item.score)
  const scoreLabel = Number.isFinite(numericScore)
    ? numericScore.toFixed(3)
    : '0.000'

  const explanation = item.explanation || {}

  const summary = typeof explanation.summary === 'string'
    ? explanation.summary.trim()
    : ''

  const reasons = Array.isArray(explanation.reasons)
    ? explanation.reasons
        .filter((reason) => typeof reason === 'string' && reason.trim())
        .slice(0, 2)
    : []

  const hasReasons = reasons.length > 0

  function handleCardClick(event) {
    if (event.target.closest('button')) return
    onToggleTouch?.()
  }

  function handleCardKeyDown(event) {
    if (event.target !== event.currentTarget) return
    if (event.key !== 'Enter' && event.key !== ' ') return

    event.preventDefault()
    onToggleTouch?.()
  }

  useEffect(() => {
    return () => {
      if (exitTimeoutRef.current !== null) {
        window.clearTimeout(exitTimeoutRef.current)
      }
    }
  }, [])

  function handleRateRecommendedMovie(ratedMovie, selectedRating) {
    if (isLeaving) return

    setExitRating(selectedRating)
    setIsLeaving(true)

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

    exitTimeoutRef.current = window.setTimeout(
      () => {
        onRate(ratedMovie, selectedRating)
      },
      prefersReducedMotion ? 30 : EXIT_ANIMATION_MS,
    )
  }

  const cardClassName = [
    'poster-card',
    'recommendation-card',
    'visible',
    isLeaving ? 'recommendation-card--leaving' : '',
    isTouchOpen ? 'touch-open' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <article
      className={cardClassName}
      style={{ '--card-order': rank % 16 }}
      tabIndex={0}
      aria-expanded={isTouchOpen}
      onClick={handleCardClick}
      onKeyDown={handleCardKeyDown}
    >
      <div className="poster-frame recommendation-frame">
        {movie.posterUrl ? (
          <img
            src={movie.posterUrl}
            alt={`${movieTitle} póster`}
            loading="lazy"
          />
        ) : (
          <span className="poster-fallback">
            {movieTitle.slice(0, 1)}
          </span>
        )}

        <div
          className="poster-shade recommendation-poster-shade"
          aria-hidden="true"
        />

        <div className="poster-light" aria-hidden="true" />

        <div className="poster-overlay recommendation-overlay">
          <div className="poster-title-block">
            <h3>{movieTitle}</h3>

            {movie.year ? (
              <span>{movie.year}</span>
            ) : null}
          </div>

          <div className="recommendation-score-line">
            <span>Puntuación</span>
            <strong>{scoreLabel}</strong>
          </div>

          {summary ? (
            <p className="recommendation-headline">
              {summary}
            </p>
          ) : null}

          <div
            className={[
              'recommendation-interaction-panel',
              hasReasons ? 'has-reasons' : 'rating-only',
            ].join(' ')}
          >
            {hasReasons ? (
              <ul className="recommendation-reasons">
                {reasons.map((reason) => (
                  <li
                    key={`${movie.movieId || movie.id}-${reason}`}
                  >
                    {reason}
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="recommendation-rating-action">
              <span>¿Ya la has visto? Valórala</span>

              <MovieRatingControl
                movie={movie}
                rating={rating}
                onRate={handleRateRecommendedMovie}
                className="recommendation-rating-control"
                disabled={isLeaving}
              />
            </div>
          </div>
        </div>

        <div className="recommendation-rank-badge">
          #{rank}
        </div>

        {isLeaving ? (
          <div
            className="recommendation-rating-confirmation"
            role="status"
            aria-live="polite"
          >
            <strong>{exitRating}★</strong>
            <span>¡Valorada!</span>
          </div>
        ) : null}
      </div>
    </article>
  )
}

export default RecommendationCard
