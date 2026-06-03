import { useEffect, useRef, useState } from 'react'

function MovieCard({ movie, rating, onRate, index = 0 }) {
  const cardRef = useRef(null)
  const [isVisible, setIsVisible] = useState(false)
  const [hoveredRating, setHoveredRating] = useState(null)
  const isRated = Boolean(rating)
  const previewRating = hoveredRating || rating || 0

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
      ]
        .filter(Boolean)
        .join(' ')}
      style={{ '--card-order': index % 16 }}
    >
      <div className="poster-frame">
        {movie.posterUrl ? (
          <img src={movie.posterUrl} alt={`${movie.title} poster`} loading="lazy" />
        ) : (
          <span className="poster-fallback">{movie.title.slice(0, 1)}</span>
        )}

        <div className="poster-shade" aria-hidden="true" />
        <div className="poster-light" aria-hidden="true" />

        <div className="poster-overlay">
          <div className="poster-title-block">
            <h3>{movie.title}</h3>
            {movie.year ? <span>{movie.year}</span> : null}
          </div>

          <div className="poster-actions">
            <div
              className="poster-stars"
              aria-label={`Rate ${movie.title}`}
              onMouseLeave={() => setHoveredRating(null)}
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  className={value <= previewRating ? 'poster-star active' : 'poster-star'}
                  style={{ '--star-order': value }}
                  aria-label={`${value} stars`}
                  aria-pressed={rating === value}
                  onMouseEnter={() => setHoveredRating(value)}
                  onFocus={() => setHoveredRating(value)}
                  onBlur={() => setHoveredRating(null)}
                  onClick={() => onRate(movie.id, value)}
                >
                  ★
                </button>
              ))}
            </div>

            {isRated ? (
              <button type="button" className="poster-clear" onClick={() => onRate(movie.id, null)}>
                Clear
              </button>
            ) : null}
          </div>
        </div>

        {isRated ? (
          <div className="poster-rating-badge" aria-label={`${rating} stars`}>
            {rating}★
          </div>
        ) : null}
      </div>
    </article>
  )
}

export default MovieCard