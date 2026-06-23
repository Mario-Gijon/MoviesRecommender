import { apiRequest } from '../../api/client'
import { isStrategyEnabled, STRATEGY_ENDPOINTS } from './strategies'

export function requestRecommendations({ strategy, ratings, limit, templateSessionId }) {
  if (!isStrategyEnabled(strategy)) {
    throw new Error('La estrategia seleccionada todavía no está disponible.')
  }

  const endpoint = STRATEGY_ENDPOINTS[strategy]

  if (!endpoint) {
    throw new Error('La estrategia seleccionada no existe.')
  }

  return apiRequest(endpoint, {
    method: 'POST',
    body: JSON.stringify({
      ratings,
      limit,
      templateSessionId,
    }),
  })
}