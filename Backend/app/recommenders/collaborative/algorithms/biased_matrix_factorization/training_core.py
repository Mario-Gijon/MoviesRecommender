import math

import numpy as np
from numba import njit


@njit(cache=True)
def train_epoch_sgd(
    *,
    user_indices: np.ndarray,
    movie_indices: np.ndarray,
    ratings: np.ndarray,
    order: np.ndarray,
    global_mean: float,
    user_biases: np.ndarray,
    movie_biases: np.ndarray,
    user_factors: np.ndarray,
    movie_factors: np.ndarray,
    learning_rate: float,
    regularization: float,
) -> None:
    factor_count = user_factors.shape[1]

    for order_position in range(order.shape[0]):
        rating_index = order[order_position]

        user_index = user_indices[rating_index]
        movie_index = movie_indices[rating_index]
        rating = ratings[rating_index]

        latent_score = 0.0
        for factor_index in range(factor_count):
            latent_score += (
                user_factors[user_index, factor_index]
                * movie_factors[movie_index, factor_index]
            )

        prediction = (
            global_mean
            + user_biases[user_index]
            + movie_biases[movie_index]
            + latent_score
        )
        error = rating - prediction

        old_user_bias = user_biases[user_index]
        old_movie_bias = movie_biases[movie_index]

        user_biases[user_index] = old_user_bias + learning_rate * (
            error - regularization * old_user_bias
        )
        movie_biases[movie_index] = old_movie_bias + learning_rate * (
            error - regularization * old_movie_bias
        )

        for factor_index in range(factor_count):
            old_user_factor = user_factors[user_index, factor_index]
            old_movie_factor = movie_factors[movie_index, factor_index]

            user_factors[user_index, factor_index] = old_user_factor + learning_rate * (
                error * old_movie_factor - regularization * old_user_factor
            )
            movie_factors[movie_index, factor_index] = old_movie_factor + learning_rate * (
                error * old_user_factor - regularization * old_movie_factor
            )


@njit(cache=True)
def compute_rmse_mae(
    *,
    user_indices: np.ndarray,
    movie_indices: np.ndarray,
    ratings: np.ndarray,
    global_mean: float,
    user_biases: np.ndarray,
    movie_biases: np.ndarray,
    user_factors: np.ndarray,
    movie_factors: np.ndarray,
    min_rating: float,
    max_rating: float,
) -> tuple[float, float]:
    if ratings.shape[0] == 0:
        return math.nan, math.nan

    factor_count = user_factors.shape[1]
    squared_error_sum = 0.0
    absolute_error_sum = 0.0

    for rating_index in range(ratings.shape[0]):
        user_index = user_indices[rating_index]
        movie_index = movie_indices[rating_index]
        rating = ratings[rating_index]

        latent_score = 0.0
        for factor_index in range(factor_count):
            latent_score += (
                user_factors[user_index, factor_index]
                * movie_factors[movie_index, factor_index]
            )

        prediction = (
            global_mean
            + user_biases[user_index]
            + movie_biases[movie_index]
            + latent_score
        )

        if prediction < min_rating:
            prediction = min_rating
        elif prediction > max_rating:
            prediction = max_rating

        error = rating - prediction
        squared_error_sum += error * error

        if error < 0:
            absolute_error_sum -= error
        else:
            absolute_error_sum += error

    rmse = math.sqrt(squared_error_sum / ratings.shape[0])
    mae = absolute_error_sum / ratings.shape[0]

    return rmse, mae


@njit(cache=True)
def predict_single_rating(
    *,
    user_index: int,
    movie_index: int,
    global_mean: float,
    user_biases: np.ndarray,
    movie_biases: np.ndarray,
    user_factors: np.ndarray,
    movie_factors: np.ndarray,
    min_rating: float,
    max_rating: float,
) -> float:
    latent_score = 0.0
    factor_count = user_factors.shape[1]

    for factor_index in range(factor_count):
        latent_score += (
            user_factors[user_index, factor_index]
            * movie_factors[movie_index, factor_index]
        )

    prediction = (
        global_mean
        + user_biases[user_index]
        + movie_biases[movie_index]
        + latent_score
    )

    if prediction < min_rating:
        return min_rating

    if prediction > max_rating:
        return max_rating

    return prediction