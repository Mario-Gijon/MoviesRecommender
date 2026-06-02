import MoviesGrid from './MoviesGrid'

function RatedMoviesStep({ ratedMovies, ratings, profileChips, onRate }) {
  return (
    <div className="step-panel two-column-step">
      <section className="info-panel">
        <h3>Detected profile</h3>
        <p className="section-copy">
          This is a placeholder white-box profile for the outreach demo. Real profile signals will
          be computed later.
        </p>
        <div className="chips-row">
          {profileChips.map((chip) => (
            <span key={chip} className="profile-chip">
              {chip}
            </span>
          ))}
        </div>
      </section>
      <section className="scroll-panel">
        {ratedMovies.length ? (
          <MoviesGrid movies={ratedMovies} ratings={ratings} onRate={onRate} />
        ) : (
          <div className="empty-state">
            <h3>No rated movies yet</h3>
            <p className="helper-text">Go back to step 1 and rate a few movies to populate this review step.</p>
          </div>
        )}
      </section>
    </div>
  )
}

export default RatedMoviesStep

