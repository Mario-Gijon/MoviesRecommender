from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.common.models import CollaborativeUserRating


FAMILY_GENRES = {"Animation", "Family", "Fantasy", "Adventure", "Comedy"}
TEEN_GENRES = {"Action", "Science Fiction", "Thriller", "Mystery", "Adventure", "Fantasy"}


def infer_collaborative_profile_style(
    ratings: list[CollaborativeUserRating],
) -> str:
    positive_ratings = [rating for rating in ratings if rating.rating >= 4]

    if not positive_ratings:
        return "mixed"

    family_score = 0
    teen_score = 0

    for rating in positive_ratings:
        try:
            movie = catalog_repository.get_public_movie_by_id(rating.movie_id)
        except RuntimeError:
            continue

        suitability_category = str(movie.get("suitabilityCategory") or "")
        genres = set(movie.get("genres") or [])

        if suitability_category == "family_friendly":
            family_score += 2

        if suitability_category == "teen":
            teen_score += 2

        if genres & FAMILY_GENRES:
            family_score += 1

        if genres & TEEN_GENRES:
            teen_score += 1

    if family_score >= teen_score + 2:
        return "family"

    if teen_score >= family_score + 2:
        return "teen"

    return "mixed"