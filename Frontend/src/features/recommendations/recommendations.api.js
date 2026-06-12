import { apiRequest } from '../../api/client'

export function requestRecommendations({ ratings }) {
  return apiRequest('/recommendations/content-based', {
    method: 'POST',
    body: JSON.stringify({
      ratings,
      limit: 10,
      templateSessionId: 'stand-demo',
    }),
  })
}