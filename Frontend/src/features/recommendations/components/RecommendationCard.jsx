import { getMovieDisplayTitle } from '../../movies/movieDisplay'
import MovieRatingControl from '../../movies/components/MovieRatingControl'

function RecommendationCard({ item, rank, rating, onRate }) {
  const movieTitle = getMovieDisplayTitle(item.movie)
  const scoreLabel = Number(item.score || 0).toFixed(3)
  const explanation = item.explanation || {}
  const summary = typeof explanation.summary === 'string' ? explanation.summary : ''
  const reasons = Array.isArray(explanation.reasons)
    ? explanation.reasons.filter((reason) => typeof reason === 'string').slice(0, 2)
    : []
  const ratingAction = (
    <div className="recommendation-rating-action">
      <span>¿Ya la has visto? Valórala</span>
      <MovieRatingControl
        movie={item.movie}
        rating={rating}
        onRate={onRate}
        className="recommendation-rating-control"
      />
    </div>
  )

  return (
    <article
      className="poster-card recommendation-card visible"
      style={{ '--card-order': rank % 16 }}
    >
      <div className="poster-frame recommendation-frame">
        {item.movie.posterUrl ? (
          <img src={item.movie.posterUrl} alt={`${movieTitle} poster`} loading="lazy" />
        ) : (
          <span className="poster-fallback">{movieTitle.slice(0, 1)}</span>
        )}

        <div className="poster-shade recommendation-poster-shade" aria-hidden="true" />
        <div className="poster-light" aria-hidden="true" />

        <div className="poster-overlay recommendation-overlay">
          <div className="poster-title-block">
            <h3>{movieTitle}</h3>
            {item.movie.year ? <span>{item.movie.year}</span> : null}
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

          {reasons.length ? (
            <div className="recommendation-hover-details">
              <ul>
                {reasons.map((reason) => (
                  <li key={`${item.movie.movieId || item.movie.id}-${reason}`}>{reason}</li>
                ))}
              </ul>
              {ratingAction}
            </div>
          ) : <div className="recommendation-rating-only">{ratingAction}</div>}
        </div>

        <div className="recommendation-rank-badge">#{rank}</div>
      </div>
    </article>
  )
}

export default RecommendationCard
