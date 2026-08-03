"""Read-only configuration helpers for the interactive manager."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
EXAMPLE_ENV_FILE = ROOT / ".env.example"
DEFAULT_ITEM_KNN_VARIANT = "top_k_100_min_support_25"
DEFAULT_BIASED_VARIANT = "factors_128_epochs_100_lr_0_005_reg_0_02"


@dataclass(frozen=True)
class Configuration:
    root: Path
    source: Path
    values: dict[str, str]

    @property
    def data_dir(self) -> Path:
        configured = Path(self.values.get("DATA_DIR", "./data")).expanduser()
        return (configured if configured.is_absolute() else self.root / configured).resolve()

    @property
    def item_knn_variant(self) -> str:
        return self.values.get(
            "MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT",
            DEFAULT_ITEM_KNN_VARIANT,
        )

    @property
    def biased_variant(self) -> str:
        return self.values.get(
            "MOVIES_RECOMMENDER_BIASED_MATRIX_FACTORIZATION_MODEL_VARIANT",
            DEFAULT_BIASED_VARIANT,
        )

    def url(self, host_key: str, port_key: str, default_port: str) -> str:
        host = self.values.get(host_key, "127.0.0.1")
        port = self.values.get(port_key, default_port)
        shown_host = "127.0.0.1" if host == "0.0.0.0" else host
        return f"http://{shown_host}:{port}"


def load_configuration(root: Path = ROOT, *, require_env: bool = False) -> Configuration:
    env_file = root / ".env"
    example_file = root / ".env.example"
    source = env_file if env_file.is_file() else example_file
    if require_env and not env_file.is_file():
        raise FileNotFoundError(env_file)
    values: dict[str, str] = {}
    if source.is_file():
        for line in source.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            values[key] = value
    return Configuration(root=root, source=source, values=values)
