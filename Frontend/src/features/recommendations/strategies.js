export const RECOMMENDER_OPTIONS = Object.freeze({
  content: Object.freeze([
    Object.freeze({ value: 'tfidf', label: 'TF-IDF' }),
  ]),
  collaborative: Object.freeze([
    Object.freeze({ value: 'item_knn', label: 'Item KNN' }),
  ]),
})

export const RECOMMENDATION_STRATEGIES = Object.freeze([
  Object.freeze({
    value: 'content',
    label: 'Basado en contenido',
  }),
  Object.freeze({
    value: 'collaborative',
    label: 'Filtrado colaborativo',
  }),
])

export const MIN_RECOMMENDATION_RATINGS = 4

export function getRemainingRecommendationRatings(ratedMoviesCount) {
  const normalizedCount = Number.isFinite(Number(ratedMoviesCount))
    ? Math.max(0, Math.trunc(Number(ratedMoviesCount)))
    : 0

  return Math.max(MIN_RECOMMENDATION_RATINGS - normalizedCount, 0)
}

export function hasMinimumRecommendationRatings(ratedMoviesCount) {
  return getRemainingRecommendationRatings(ratedMoviesCount) === 0
}

export function getRecommendationRatingGuidance(ratedMoviesCount) {
  const remainingRatings = getRemainingRecommendationRatings(ratedMoviesCount)
  const introduction = `Para darte una buena recomendación, necesito que valores al menos ${MIN_RECOMMENDATION_RATINGS} películas.`

  if (remainingRatings === 0) return introduction

  if (remainingRatings === 1) {
    return `${introduction} Te queda solo 1 película más 😊`
  }

  const remainingMessage = remainingRatings === MIN_RECOMMENDATION_RATINGS
    ? `Te quedan ${remainingRatings} películas por valorar 😊`
    : `Te quedan ${remainingRatings} películas más 😊`

  return `${introduction} ${remainingMessage}`
}

export function getRecommendationRatingCta(ratedMoviesCount) {
  const remainingRatings = getRemainingRecommendationRatings(ratedMoviesCount)
  const movieLabel = remainingRatings === 1 ? 'película' : 'películas'

  return `Para darte una buena recomendación, valora ${remainingRatings} ${movieLabel} más 😊`
}

export function isStrategyEnabled(strategy) {
  const strategyConfig = RECOMMENDATION_STRATEGIES.find((item) => item.value === strategy)

  if (!strategyConfig) {
    return false
  }

  return Boolean(strategyConfig)
}

export function getAlgorithmsForStrategy(strategy) {
  return RECOMMENDER_OPTIONS[strategy] || []
}

export function getDefaultAlgorithm(strategy) {
  return getAlgorithmsForStrategy(strategy)[0]?.value || null
}

export function isAlgorithmValidForStrategy(strategy, algorithm) {
  return getAlgorithmsForStrategy(strategy).some((item) => item.value === algorithm)
}

export function resolveAlgorithmForStrategy(strategy, algorithm) {
  return isAlgorithmValidForStrategy(strategy, algorithm)
    ? algorithm
    : getDefaultAlgorithm(strategy)
}
