export const RECOMMENDER_OPTIONS = Object.freeze({
  content: Object.freeze([
    Object.freeze({ value: 'tfidf', label: 'TF-IDF' }),
  ]),
  collaborative: Object.freeze([
    Object.freeze({ value: 'item_knn', label: 'Item KNN' }),
    Object.freeze({ value: 'user_knn', label: 'User KNN' }),
    Object.freeze({ value: 'biased', label: 'Biased matrix factorization' }),
    Object.freeze({ value: 'popularity', label: 'Popularity' }),
  ]),
})

export const RECOMMENDATION_STRATEGIES = Object.freeze([
  Object.freeze({
    value: 'content',
    label: 'Basado en contenido',
    status: 'TF-IDF',
  }),
  Object.freeze({
    value: 'collaborative',
    label: 'Filtrado colaborativo',
    status: 'Cuatro algoritmos',
  }),
])

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
