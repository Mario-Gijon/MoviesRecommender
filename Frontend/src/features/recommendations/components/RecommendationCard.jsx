import { getMovieDisplayTitle } from '../../movies/movieDisplay'

function RecommendationCard({ item, rank }) {
  const movieTitle = getMovieDisplayTitle(item.movie)
  const affinityLabel = `${item.matchPercentage.toFixed(1)}%`
  const scoreLabel = item.score.toFixed(3)
  const reasons = item.explanation.reasons.slice(0, 2)

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
            <span>Afinidad</span>
            <strong>{affinityLabel}</strong>
          </div>

          {item.explanation.summary ? (
            <p className="recommendation-headline">
              {item.explanation.summary}
            </p>
          ) : null}

          <span className="recommendation-raw-score">Puntuación: {scoreLabel}</span>

          {reasons.length ? (
            <div className="recommendation-hover-details">
              <ul>
                {reasons.map((reason) => (
                  <li key={`${item.movie.movieId || item.movie.id}-${reason}`}>{reason}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="recommendation-rank-badge">#{rank}</div>
      </div>
    </article>
  )
}

export default RecommendationCard
