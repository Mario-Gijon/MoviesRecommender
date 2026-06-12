function RecommendationProfileSummary({ profile }) {
  if (!profile) {
    return null
  }

  return (
    <section className="card recommendation-profile-summary">
      <div className="card-body recommendation-profile-body">
        <span className="game-section-kicker">Tu perfil</span>
        <h3>{profile.headline}</h3>
      </div>
    </section>
  )
}

export default RecommendationProfileSummary