function RecommendationCard({ item }) {
  return (
    <article className="card recommendation-card">
      <div className="card-body">
        <div className="card-heading">
          <h3>{item.movie.title}</h3>
          <span>{item.movie.year}</span>
        </div>
        <p className="meta">
          {item.movie.genres.join(' • ')} | {item.method}
        </p>
        <p className="score-line">
          Score: {item.score} | Match: {item.matchPercentage}%
        </p>
        <p>{item.explanationSummary}</p>
        <ul className="signals-list">
          {item.explanationSignals.map((signal) => (
            <li key={`${item.movie.id}-${signal.label}`}>
              <strong>{signal.label}:</strong> {signal.value}
            </li>
          ))}
        </ul>
      </div>
    </article>
  )
}

export default RecommendationCard

