import { apiRequest } from '../../api/client'

export function requestRecommendations(payload) {
  return apiRequest('/recommendations/content-based', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
