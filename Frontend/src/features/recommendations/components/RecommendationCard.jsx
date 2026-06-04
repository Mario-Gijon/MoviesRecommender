import { getMovieDisplayTitle } from '../../movies/movieDisplay'

function RecommendationCard({ item, rank }) {
  const matchLabel = `${item.matchPercentage}%`
  const movieTitle = getMovieDisplayTitle(item.movie)

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
            <span>{item.method}</span>
          </div>

          {item.explanationSummary ? (
            <p>{item.explanationSummary}</p>
          ) : null}

          {item.explanationSignals?.length ? (
            <div className="recommendation-signals">
              {item.explanationSignals.slice(0, 3).map((signal) => (
                <span key={`${item.movie.id}-${signal.label}`}>
                  {signal.label}: {signal.value}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  )
}

export default RecommendationCard
