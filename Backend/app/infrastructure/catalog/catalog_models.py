from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.session import Base


class MovieRecord(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    movie_lens_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imdb_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    original_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year: Mapped[int] = mapped_column(Integer)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    backdrop_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_recommendation_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_collaborative_core: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    available_for_content: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    available_for_collaborative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_coverage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    collaborative_coverage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    demo_suitability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rating_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmdb_popularity: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmdb_vote_average: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmdb_vote_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runtime: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_language: Mapped[str | None] = mapped_column(String(32), nullable=True)

    genres: Mapped[list["MovieGenreRecord"]] = relationship(
        back_populates="movie",
        cascade="all, delete-orphan",
    )
    tags: Mapped[list["MovieTagRecord"]] = relationship(
        back_populates="movie",
        cascade="all, delete-orphan",
    )
    coverage_notes: Mapped[list["MovieCoverageNoteRecord"]] = relationship(
        back_populates="movie",
        cascade="all, delete-orphan",
    )


class MovieGenreRecord(Base):
    __tablename__ = "movie_genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    movie: Mapped[MovieRecord] = relationship(back_populates="genres")


class MovieTagRecord(Base):
    __tablename__ = "movie_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    movie: Mapped[MovieRecord] = relationship(back_populates="tags")


class MovieCoverageNoteRecord(Base):
    __tablename__ = "movie_coverage_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    note: Mapped[str] = mapped_column(String(255), nullable=False)

    movie: Mapped[MovieRecord] = relationship(back_populates="coverage_notes")
