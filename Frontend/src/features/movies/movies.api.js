import { apiRequest } from '../../api/client'

export function fetchFeaturedMovies() {
  return apiRequest('/movies/featured')
}

export function fetchPublicCatalogPage({ page, pageSize, search, genre }) {
  const params = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
  })

  if (search && search.trim()) {
    params.set('search', search.trim())
  }

  if (genre && genre.trim()) {
    params.set('genre', genre.trim())
  }

  return apiRequest(`/movies/public-catalog?${params.toString()}`)
}
