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
    "suitability": 0.22,
    "genreAppeal": 0.20,
    "recognition": 0.23,
    "recency": 0.16,
    "positiveTerms": 0.11,
    "dataReliability": 0.08,
}
STAND_SUITABILITY_WEIGHTS = {
    "family_friendly": 1.0,
    "teen": 0.80,
    "unknown": 0.0,
    "adult_or_sensitive": 0.0,
}
STAND_TEEN_WITH_FAMILY_CERT_SUITABILITY_WEIGHT = 0.86
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
STAND_FAMILY_CONTEXT_ANCHOR_GENRES = {
    "Family",
}
STAND_FAMILY_CONTEXT_SUPPORT_GENRES = {
    "Animation",
    "Comedy",
    "Adventure",
    "Fantasy",
}
STAND_FAMILY_CONTEXT_MIN_SUPPORT_MATCHES = 1
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
    "Horror": 0.082,
    "Thriller": 0.06,
    "War": 0.05,
    "Crime": 0.03,
}
STAND_MAX_SENSITIVE_GENRE_PENALTY = 0.10
STAND_FAMILY_CONTEXT_SENSITIVE_PENALTY_MULTIPLIER = 0.35
STAND_CATEGORY_PENALTIES = {
    "adult_or_sensitive": 0.25,
    "unknown": 0.15,
}
STAND_TMDB_POPULARITY_SATURATION = 110.0
PUBLIC_STAND_COMMON_ORIGINAL_LANGUAGES = {
    "en",
    "es",
}
PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_RATING_COUNT = 250
PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_TMDB_POPULARITY = 10.0
PUBLIC_STAND_LOW_ACCESSIBILITY_MAX_DISPLAY_SCORE = 0.55
PUBLIC_STAND_ACCESSIBILITY_PROTECTED_GENRES = {
    "Animation",
    "Family",
}
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
