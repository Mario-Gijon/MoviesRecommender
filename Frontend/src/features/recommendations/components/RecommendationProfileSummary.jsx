function RecommendationProfileSummary({ profile }) {
  if (!profile) {
    return null
  }

  return (
    <section className="card recommendation-profile-summary">
      <div className="card-body">
        <div className="card-heading">
          <div>
            <span className="game-section-kicker">Profile</span>
            <h3>{profile.headline}</h3>
          </div>
        </div>

        <div className="chips-row">
          <span className="stats-chip">Style: {profile.style}</span>
          <span className="stats-chip">Confidence: {profile.confidence}</span>
          <span className="stats-chip">Rated: {profile.ratedMovieCount}</span>
          <span className="stats-chip">Positive: {profile.positiveRatingCount}</span>
          <span className="stats-chip">Negative: {profile.negativeRatingCount}</span>
        </div>

        {profile.positiveSignals?.length ? (
          <div className="recommendation-profile-block">
            <strong>What seems to click</strong>
            <div className="chips-row">
              {profile.positiveSignals.map((signal) => (
                <span key={`positive-${signal}`} className="profile-chip">
                  {signal}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {profile.negativeSignals?.length ? (
          <div className="recommendation-profile-block">
            <strong>Less your thing</strong>
            <div className="chips-row">
              {profile.negativeSignals.map((signal) => (
                <span key={`negative-${signal}`} className="profile-chip">
                  {signal}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  )
}

export default RecommendationProfileSummary
