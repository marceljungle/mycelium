"""Centralized registry for embedding model adapters.

To add a new embedding model:
1. Create an adapter in ``infrastructure/model/<name>.py`` implementing ``EmbeddingGenerator``.
2. Add a ``ModelSpec`` entry to ``MODEL_REGISTRY`` below.
3. (Optional) add a default config section to ``config.example.yml``.

That's it — the factory, config validation, and CLI will pick it up automatically.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.repositories import EmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelSpec:
    """Metadata describing one embedding model adapter."""

    key: str
    """Short identifier used in config YAML (e.g. ``"clap"``)."""

    adapter_class_path: str
    """Fully-qualified class path, e.g. ``mycelium.infrastructure.model.clap.CLAPEmbeddingGenerator``."""

    display_name: str
    """Human-readable name shown in UI / logs."""

    supports_text_search: bool
    """Whether the model can produce text embeddings for text-based search."""

    default_config: Dict[str, Any] = field(default_factory=dict)
    """Default constructor kwargs when no user config is provided."""


# ---------------------------------------------------------------------------
# Central registry — add new models here
# ---------------------------------------------------------------------------
MODEL_REGISTRY: Dict[str, ModelSpec] = {
    "clap": ModelSpec(
        key="clap",
        adapter_class_path="mycelium.infrastructure.model.clap.CLAPEmbeddingGenerator",
        display_name="CLAP (Language-Audio Pretraining)",
        supports_text_search=True,
        default_config={
            "model_id": "laion/larger_clap_music_and_speech",
            "target_sr": 48000,
            "chunk_duration_s": 30,
            "micro_batch_size": 4,
        },
    ),
    "muq": ModelSpec(
        key="muq",
        adapter_class_path="mycelium.infrastructure.model.muq.MuQEmbeddingGenerator",
        display_name="MuQ (Music Understanding)",
        supports_text_search=False,
        default_config={
            "model_id": "OpenMuQ/MuQ-large-msd-iter",
            "target_sr": 24000,
            "chunk_duration_s": 30,
            "micro_batch_size": 4,
        },
    ),
}


def get_valid_model_types() -> List[str]:
    """Return sorted list of registered model type keys."""
    return sorted(MODEL_REGISTRY.keys())


def get_model_spec(model_type: str) -> ModelSpec:
    """Look up a model spec, raising ``ValueError`` for unknown types."""
    if model_type not in MODEL_REGISTRY:
        valid = ", ".join(get_valid_model_types())
        raise ValueError(
            f"Unknown embedding model type '{model_type}'. Valid types: {valid}"
        )
    return MODEL_REGISTRY[model_type]


def create_embedding_generator(
    model_type: str,
    config_overrides: Optional[Dict[str, Any]] = None,
) -> "EmbeddingGenerator":
    """Instantiate the embedding generator for *model_type*.

    Merges ``default_config`` from the registry with any user-supplied
    *config_overrides*.  Uses lazy imports so torch / transformers are only
    loaded when actually needed.
    """
    spec = get_model_spec(model_type)

    # Merge defaults with user overrides
    final_config = {**spec.default_config}
    if config_overrides:
        final_config.update(config_overrides)

    # Lazy import the adapter class
    module_path, class_name = spec.adapter_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    adapter_class: Type[EmbeddingGenerator] = getattr(module, class_name)

    # Only pass kwargs the constructor actually accepts — protects against
    # server/client version mismatches where one side knows a config key the
    # other doesn't.
    sig = inspect.signature(adapter_class.__init__)
    valid_params = set(sig.parameters.keys()) - {"self"}
    filtered_config = {k: v for k, v in final_config.items() if k in valid_params}
    dropped = set(final_config) - set(filtered_config)
    if dropped:
        logger.warning("Dropping unknown config keys for %s: %s", spec.key, dropped)

    logger.info(
        "Creating %s embedding generator (model_id=%s)",
        spec.display_name,
        filtered_config.get("model_id", "?"),
    )
    return adapter_class(**filtered_config)
