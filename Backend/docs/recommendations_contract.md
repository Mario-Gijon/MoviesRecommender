# Recommendation API contract

## Canonical route

```http
POST /recommendations
Content-Type: application/json
```

## Request

```json
{
  "requestId": "unity-request-42",
  "strategy": "collaborative",
  "algorithm": "item_knn",
  "ratings": [
    {
      "movieId": 1,
      "rating": 5
    },
    {
      "movieId": 260,
      "rating": 4
    },
    {
      "movieId": 296,
      "rating": 2
    }
  ],
  "limit": 10
}
```

`requestId` is optional. When omitted, the backend generates a non-persistent
identifier with a `rec-` prefix.

## Successful response

```json
{
  "requestId": "unity-request-42",
  "strategy": "collaborative",
  "algorithm": "item_knn",
  "recommendations": [
    {
      "rank": 1,
      "movie": {
        "movieId": 3114,
        "id": 3114,
        "tmdbId": 863,
        "movieLensId": 3114,
        "imdbId": "0120363",
        "title": "Toy Story 2",
        "cleanTitle": "Toy Story 2",
        "originalTitle": "Toy Story 2 (1999)",
        "year": 1999,
        "overview": "Woody is stolen by a toy collector.",
        "displayTitle": "Toy Story 2",
        "displayOverview": "Woody es secuestrado por un coleccionista.",
        "posterUrl": "/offline/posters/3114.jpg",
        "posterPath": null,
        "posterFile": "images/posters/3114.jpg",
        "runtime": 92,
        "originalLanguage": "en",
        "genres": [
          "Adventure",
          "Animation",
          "Comedy"
        ],
        "displayGenres": [
          "Aventura",
          "Animación",
          "Comedia"
        ],
        "keywords": [
          "toy",
          "friendship"
        ],
        "userTags": [
          "pixar"
        ],
        "topCast": [],
        "directors": [],
        "tags": [
          "toy",
          "friendship",
          "pixar"
        ],
        "ratingCount": 1000,
        "averageRating": 3.9,
        "filteredRatingCount": 1000,
        "filteredAverageRating": 3.9,
        "candidateScore": 0.8,
        "dataReliabilityScore": 0.9,
        "recencyScore": 0.5,
        "tmdbPopularity": 50.0,
        "tmdbVoteAverage": 7.6,
        "tmdbVoteCount": 12000,
        "suitabilityCategory": "family_friendly",
        "standDisplayScore": 0.8,
        "standDisplayReasons": [],
        "coverage": {
          "availableForContent": true,
          "availableForCollaborative": true,
          "contentCoverage": 1.0,
          "collaborativeCoverage": 1.0,
          "coverageNotes": [
            "Offline dataset"
          ]
        }
      },
      "score": 0.74,
      "matchPercentage": 68.5,
      "explanation": {
        "summary": "Users with similar preferences rated this movie positively.",
        "reasons": [
          "The movie has a strong score among similar users."
        ]
      }
    }
  ],
  "meta": {
    "limit": 10,
    "count": 1
  }
}
```

The `movie` object uses the existing `PublicMovieRecord` catalog schema.
Optional movie fields are consistently returned as a value or `null`.

## Error response

```json
{
  "requestId": "unity-request-42",
  "error": {
    "code": "insufficient_ratings",
    "message": "There are not enough ratings to run this recommender.",
    "details": {
      "minimumRequired": 3,
      "received": 2,
      "requirement": "nonNeutralRatings"
    }
  }
}
```

Recommendation request validation errors also use this shape with HTTP `422`.

## Registered combinations

| Strategy | Algorithm |
| --- | --- |
| `content` | `tfidf` |
| `collaborative` | `popularity` |
| `collaborative` | `item_knn` |
| `collaborative` | `user_knn` |
| `collaborative` | `biased` |

## Deprecated compatibility routes

- `POST /recommendations/content-based` selects `content + tfidf`.
- `POST /recommendations/collaborative` selects the configured collaborative
  algorithm.

Both deprecated routes accept their previous request payloads and return the
unified response contract.
