import { apiRequest } from '../../api/client'

export function fetchFeaturedMovies() {
  return apiRequest('/movies/featured')
}

