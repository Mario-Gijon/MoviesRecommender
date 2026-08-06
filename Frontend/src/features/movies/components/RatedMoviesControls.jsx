function RatedMoviesControls({ ratedMoviesCount, onClearProfile, canClearProfile }) {
  const profileLabel = `${ratedMoviesCount} ${
    ratedMoviesCount === 1 ? 'película valorada' : 'películas valoradas'
  }`

  return (
    <div className="review-profile-toolbar">
      <div className="review-profile-summary">
        <span className="review-profile-summary-icon" aria-hidden="true">★</span>
        <strong>{profileLabel}</strong>
      </div>

      {canClearProfile ? (
        <button
          type="button"
          className="clear-profile-button"
          onClick={onClearProfile}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path
              d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <span>Reiniciar perfil</span>
        </button>
      ) : null}
    </div>
  )
}

export default RatedMoviesControls
