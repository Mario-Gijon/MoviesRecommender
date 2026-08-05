import { useEffect, useRef, useState } from 'react'

import { getMovieDisplayTitle } from '../movieDisplay'
import MovieRatingControl from './MovieRatingControl'

function MovieCard({
  movie,
  rating,
  onRate,
  index = 0,
  isTouchOpen = false,
  onToggleTouch,
}) {
  const cardRef = useRef(null)
  const [isVisible, setIsVisible] = useState(false)
  const isRated = Boolean(rating)
  const movieTitle = getMovieDisplayTitle(movie)

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
    if (!cardRef.current) {
      return undefined
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
        }
      },
      {
        threshold: 0.2,
        rootMargin: '70px 0px',
      },
    )

    observer.observe(cardRef.current)

    return () => observer.disconnect()
  }, [])

  return (
    <article
      ref={cardRef}
      className={[
        'poster-card',
        isRated ? 'rated' : '',
        isVisible ? 'visible' : '',
        isTouchOpen ? 'touch-open' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={{ '--card-order': index % 16 }}
      tabIndex={0}
      aria-expanded={isTouchOpen}
      onClick={handleCardClick}
      onKeyDown={handleCardKeyDown}
    >
      <div className="poster-frame">
        {movie.posterUrl ? (
          <img src={movie.posterUrl} alt={`${movieTitle} póster`} loading="lazy" />
        ) : (
          <span className="poster-fallback">{movieTitle.slice(0, 1)}</span>
        )}

        <div className="poster-shade" aria-hidden="true" />
        <div className="poster-light" aria-hidden="true" />

        <div className="poster-overlay">
          <div className="poster-title-block">
            <h3>{movieTitle}</h3>
            {movie.year ? <span>{movie.year}</span> : null}
          </div>

          <div className="poster-actions">
            <MovieRatingControl movie={movie} rating={rating} onRate={onRate} />

            {isRated ? (
              <button type="button" className="poster-clear" onClick={() => onRate(movie, null)}>
                Quitar valoración
              </button>
            ) : null}
          </div>
        </div>

        {isRated ? (
          <div className="poster-rating-badge" aria-label={`${rating} estrellas`}>
            {rating}★
          </div>
        ) : null}
      </div>
    </article>
  )
}

export default MovieCard
