import { apiRequest } from '../../api/client'
import { STRATEGY_ENDPOINTS } from './strategies'

export function requestRecommendations({ strategy, ratings, limit, templateSessionId }) {
  if (strategy !== 'content_based') {
    throw new Error('La estrategia seleccionada todavía no está disponible.')
  }

  return apiRequest(STRATEGY_ENDPOINTS[strategy], {
    method: 'POST',
    body: JSON.stringify({
      ratings,
      limit,
      templateSessionId,
    }),
  })
}
