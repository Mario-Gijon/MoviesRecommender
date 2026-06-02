class CatalogRepository:
    def __init__(self) -> None:
        self._featured_movies = [
            {
                "id": 101,
                "title": "Hidden Patterns",
                "year": 2019,
                "posterUrl": None,
                "genres": ["Drama", "Mystery"],
                "availableForContent": True,
                "availableForCollaborative": True,
            },
            {
                "id": 102,
                "title": "Orbit of Memory",
                "year": 2021,
                "posterUrl": None,
                "genres": ["Sci-Fi", "Drama"],
                "availableForContent": True,
                "availableForCollaborative": False,
            },
            {
                "id": 103,
                "title": "City of Small Clues",
                "year": 2018,
                "posterUrl": None,
                "genres": ["Crime", "Comedy"],
                "availableForContent": True,
                "availableForCollaborative": True,
            },
            {
                "id": 104,
                "title": "Summer on Titan Street",
                "year": 2020,
                "posterUrl": None,
                "genres": ["Comedy", "Romance"],
                "availableForContent": True,
                "availableForCollaborative": False,
            },
            {
                "id": 105,
                "title": "Echoes of the Deep Archive",
                "year": 2022,
                "posterUrl": None,
                "genres": ["Documentary", "History"],
                "availableForContent": False,
                "availableForCollaborative": True,
            },
        ]
        self._recommendation_candidates = [
            {
                "id": 201,
                "title": "Signal From Elsewhere",
                "year": 2017,
                "posterUrl": None,
                "genres": ["Sci-Fi", "Mystery"],
                "availableForContent": True,
                "availableForCollaborative": True,
            },
            {
                "id": 202,
                "title": "The Last Projectionist",
                "year": 2016,
                "posterUrl": None,
                "genres": ["Drama", "History"],
                "availableForContent": True,
                "availableForCollaborative": True,
            },
            {
                "id": 203,
                "title": "Paper Bridges",
                "year": 2023,
                "posterUrl": None,
                "genres": ["Romance", "Comedy"],
                "availableForContent": True,
                "availableForCollaborative": False,
            },
            {
                "id": 204,
                "title": "After the Static",
                "year": 2015,
                "posterUrl": None,
                "genres": ["Crime", "Thriller"],
                "availableForContent": False,
                "availableForCollaborative": True,
            },
        ]

    def get_status(self) -> dict:
        return {
            "catalogVersion": "placeholder-v1",
            "totalMovies": 2500,
            "visibleMovies": 1200,
            "contentCoverage": 0.82,
            "collaborativeCoverage": 0.64,
            "lastBuiltDate": None,
        }

    def get_featured_movies(self) -> list[dict]:
        return self._featured_movies

    def get_recommendation_candidates(self) -> list[dict]:
        return self._recommendation_candidates


catalog_repository = CatalogRepository()

