import { apiRequest } from '../../api/client'

export function requestRecommendations(payload) {
  return apiRequest('/recommendations', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

