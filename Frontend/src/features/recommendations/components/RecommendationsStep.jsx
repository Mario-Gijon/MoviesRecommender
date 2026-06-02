import RecommendationCard from './RecommendationCard'
import StrategySelector from './StrategySelector'

function RecommendationsStep({
  selectedStrategy,
  onSelectStrategy,
  onGenerateRecommendations,
  recommendations,
  isLoadingRecommendations,
  ratedMoviesCount,
}) {
  const canGenerate = ratedMoviesCount > 0 && !isLoadingRecommendations

  return (
    <div className="step-panel two-column-step">
      <section className="info-panel">
        <h3>Recommendation strategy</h3>
        <p className="section-copy">
          Choose the placeholder strategy to explain how different recommender families behave.
        </p>
        <StrategySelector value={selectedStrategy} onChange={onSelectStrategy} />
        <button
          type="button"
          className="primary-button generate-button"
          onClick={onGenerateRecommendations}
          disabled={!canGenerate}
        >
          {isLoadingRecommendations ? 'Generating...' : 'Generate recommendations'}
        </button>
        {!ratedMoviesCount ? (
          <p className="helper-text">Add at least one rating before requesting recommendations.</p>
        ) : null}
      </section>
      <section className="scroll-panel recommendations-panel">
        {recommendations ? (
          <>
            <div className="card">
              <div className="card-body">
                <h3>Returned explanation</h3>
                <p className="meta">
                  Strategy: {recommendations.strategy} | Rated movies:{' '}
                  {recommendations.userProfile.ratedMoviesCount}
                </p>
                <p>{recommendations.explanation.summary}</p>
              </div>
            </div>
            <div className="recommendations-list">
              {recommendations.recommendations.map((item) => (
                <RecommendationCard key={item.movie.id} item={item} />
              ))}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <h3>No recommendations yet</h3>
            <p className="helper-text">Generate a result to inspect the placeholder explanation summaries.</p>
          </div>
        )}
      </section>
    </div>
  )
}

export default RecommendationsStep
