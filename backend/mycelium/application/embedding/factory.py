"""Factory for creating embedding generators based on configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from .registry import create_embedding_generator as _create_from_registry
from ...domain.repositories import EmbeddingGenerator

if TYPE_CHECKING:
    from ...client_config import MyceliumClientConfig
    from ...config import MyceliumConfig


def create_embedding_generator(
    config: Union["MyceliumConfig", "MyceliumClientConfig"],
) -> EmbeddingGenerator:
    """Create the appropriate embedding generator from a full config object."""
    return _create_from_registry(
        model_type=config.embedding.type,
        config_overrides=config.get_active_model_config(),
    )
