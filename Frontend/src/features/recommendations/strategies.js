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
    status: 'Próximamente',
    disabled: true,
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
  return RECOMMENDATION_STRATEGIES.find((item) => item.value === strategy)?.disabled === false
}
