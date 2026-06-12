import { getMovieDisplayTitle } from '../../movies/movieDisplay'

function RecommendationCard({ item, rank }) {
  const matchLabel = `${Math.round(item.scores.recommendationScore * 100)}%`
  const movieTitle = getMovieDisplayTitle(item.movie)
  const genresLabel = item.movie.displayGenres?.join(' · ') || item.movie.genres?.join(' · ')
  const reasons = item.explanation?.reasons || []
  const matchedSignals = item.explanation?.matchedSignals || []
  const similarRatedMovies = item.explanation?.similarRatedMovies || []

  return (
    <article className="recommendation-poster-card">
      <div className="recommendation-poster-frame">
        {item.movie.posterUrl ? (
          <img src={item.movie.posterUrl} alt={`${movieTitle} poster`} loading="lazy" />
        ) : (
          <span className="poster-fallback">{movieTitle.slice(0, 1)}</span>
        )}

        <div className="recommendation-shade" aria-hidden="true" />

        <div className="recommendation-rank">#{rank}</div>

        <div className="recommendation-content">
          <div>
            <h3>{movieTitle}</h3>
            {item.movie.year ? <span>{item.movie.year}</span> : null}
          </div>

          <div className="recommendation-score-row">
            <strong>{matchLabel}</strong>
            {genresLabel ? <span>{genresLabel}</span> : null}
          </div>

          {item.explanation?.headline ? (
            <p>{item.explanation.headline}</p>
          ) : null}

          {reasons.length ? (
            <ul className="signals-list recommendation-reasons-list">
              {reasons.slice(0, 3).map((reason) => (
                <li key={`${item.movie.movieId}-${reason}`}>{reason}</li>
              ))}
            </ul>
          ) : null}

          {matchedSignals.length ? (
            <div className="recommendation-signals">
              {matchedSignals.slice(0, 4).map((signal) => (
                <span key={`${item.movie.movieId}-${signal}`}>
                  {signal}
                </span>
              ))}
            </div>
          ) : null}

          {similarRatedMovies.length ? (
            <p className="recommendation-footnote">
              Similar to your picks: {similarRatedMovies.join(', ')}
            </p>
          ) : null}
        </div>
      </div>
    </article>
  )
}

export default RecommendationCard
