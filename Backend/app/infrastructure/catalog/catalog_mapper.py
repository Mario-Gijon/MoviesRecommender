from app.infrastructure.catalog.catalog_models import MovieRecord


def movie_record_to_api_dict(record: MovieRecord) -> dict:
    return {
        "id": record.id,
        "tmdbId": record.tmdb_id,
        "movieLensId": record.movie_lens_id,
        "imdbId": record.imdb_id,
        "title": record.title,
        "originalTitle": record.original_title,
        "year": record.year,
        "overview": record.overview,
        "displayTitle": record.display_title or record.title,
        "displayOverview": record.display_overview or record.overview,
        "posterUrl": record.poster_url,
        "genres": [genre.name for genre in record.genres],
        "displayGenres": [genre.display_name or genre.name for genre in record.genres],
        "tags": [tag.name for tag in record.tags],
        "coverage": {
            "availableForContent": record.available_for_content,
            "availableForCollaborative": record.available_for_collaborative,
            "contentCoverage": record.content_coverage,
            "collaborativeCoverage": record.collaborative_coverage,
            "coverageNotes": [note.note for note in record.coverage_notes],
        },
    }
