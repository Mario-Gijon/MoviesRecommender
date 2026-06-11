FAMILY_US = {"G", "PG"}
FAMILY_ES = {"A", "Ai", "APTA", "7", "TP"}
TEEN_US = {"PG-13"}
TEEN_ES = {"12"}
ADULT_US = {"R", "NC-17"}
ADULT_ES = {"16", "18"}
SENSITIVE_GENRES = {"Horror", "Crime", "War", "Thriller"}
BOOST_SIGNAL_GENRES = {
    "Animation",
    "Family",
    "Adventure",
    "Fantasy",
    "Comedy",
}
FAMILY_POSITIVE_TERMS = {
    "pixar",
    "disney",
    "magic",
    "friendship",
    "superhero",
    "superheroes",
    "school",
    "robot",
    "dinosaur",
    "time travel",
    "alien",
    "wizard",
    "family",
    "fantasy world",
}
STAND_DISPLAY_WEIGHTS = {
    "suitability": 0.24,
    "genreAppeal": 0.23,
    "recognition": 0.20,
    "recency": 0.14,
    "positiveTerms": 0.11,
    "dataReliability": 0.08,
}
STAND_SUITABILITY_WEIGHTS = {
    "family_friendly": 1.0,
    "teen": 0.72,
    "unknown": 0.0,
    "adult_or_sensitive": 0.0,
}
STAND_GENRE_APPEAL_WEIGHTS = {
    "Animation": 1.00,
    "Family": 1.00,
    "Adventure": 0.75,
    "Fantasy": 0.70,
    "Comedy": 0.60,
    "Science Fiction": 0.35,
    "Action": 0.30,
}
STAND_GENRE_APPEAL_SATURATION = 3.0
STAND_POSITIVE_TERM_WEIGHTS = {
    "pixar": 1.00,
    "disney": 1.00,
    "friendship": 0.85,
    "magic": 0.80,
    "family": 0.80,
    "fantasy world": 0.75,
    "school": 0.65,
    "robot": 0.60,
    "dinosaur": 0.60,
    "wizard": 0.60,
    "superhero": 0.45,
    "superheroes": 0.45,
    "time travel": 0.35,
    "alien": 0.30,
}
STAND_POSITIVE_TERM_SATURATION = 2.5
STAND_SENSITIVE_GENRE_PENALTIES = {
    "Horror": 0.07,
    "Thriller": 0.05,
    "War": 0.05,
    "Crime": 0.03,
}
STAND_MAX_SENSITIVE_GENRE_PENALTY = 0.10
STAND_CATEGORY_PENALTIES = {
    "adult_or_sensitive": 0.25,
    "unknown": 0.15,
}
STAND_TMDB_POPULARITY_SATURATION = 100.0
PUBLIC_BLOCKED_TERMS = {
    "drug",
    "gore",
    "hitler",
    "adolf hitler",
    "holocaust",
    "murder",
    "nazi",
    "nazism",
    "neo-nazi",
    "prison",
    "psychopath",
    "rape",
    "serial killer",
    "slavery",
    "torture",
    "third reich",
    "genocide",
    "fascism",
    "dictator",
    "terrorism",
    "suicide",
    "self harm",
}
