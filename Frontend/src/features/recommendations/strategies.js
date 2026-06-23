export const RECOMMENDATION_STRATEGIES = [
  {
    value: 'content_based',
    label: 'Basado en contenido',
    status: 'Disponible',
    disabled: false,
  },
  {
    value: 'collaborative',
    label: 'Filtrado colaborativo',
    status: 'Baseline disponible',
    disabled: false,
  },
  {
    value: 'hybrid',
    label: 'Híbrido',
    status: 'Próximamente',
    disabled: true,
  },
]

export const STRATEGY_ENDPOINTS = {
  content_based: '/recommendations/content-based',
  collaborative: '/recommendations/collaborative',
  hybrid: '/recommendations/hybrid',
}

export function isStrategyEnabled(strategy) {
  const strategyConfig = RECOMMENDATION_STRATEGIES.find((item) => item.value === strategy)

  if (!strategyConfig) {
    return false
  }

  return strategyConfig.disabled === false
}