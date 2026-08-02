import { useState } from 'react'

function MovieRatingControl({
  movie,
  rating,
  onRate,
  className = '',
  disabled = false,
}) {
  const [hoveredRating, setHoveredRating] = useState(null)
  const previewRating = hoveredRating || rating || 0
  const title = movie.displayTitle || movie.title || 'película'

  function handleRate(value) {
    if (disabled) return
    onRate(movie, value)
  }

  return (
    <div
      className={`poster-stars ${className}`.trim()}
      aria-label={`Valorar ${title}`}
      onMouseLeave={() => setHoveredRating(null)}
    >
      {[1, 2, 3, 4, 5].map((value) => (
        <button
          key={value}
          type="button"
          className={value <= previewRating ? 'poster-star active' : 'poster-star'}
          style={{ '--star-order': value }}
          aria-label={`${value} estrellas`}
          aria-pressed={rating === value}
          disabled={disabled}
          onMouseEnter={() => setHoveredRating(value)}
          onFocus={() => setHoveredRating(value)}
          onBlur={() => setHoveredRating(null)}
          onClick={() => handleRate(value)}
        >
          ★
        </button>
      ))}
    </div>
  )
}

export default MovieRatingControl