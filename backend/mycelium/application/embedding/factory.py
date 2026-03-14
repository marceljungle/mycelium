"""Factory for creating embedding generators based on configuration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Union

from ...domain.repositories import EmbeddingGenerator

if TYPE_CHECKING:
    from ...client_config import MyceliumClientConfig
    from ...config import MyceliumConfig

logger = logging.getLogger(__name__)


def create_embedding_generator(
    config: Union[MyceliumConfig, MyceliumClientConfig],
) -> EmbeddingGenerator:
    """Create the appropriate embedding generator based on configuration."""
    from ...config import EmbeddingModelType

    embedding_type = config.embedding.type

    if embedding_type == EmbeddingModelType.CLAP:
        from ...infrastructure.model.clap import CLAPEmbeddingGenerator

        clap_cfg = config.clap
        logger.info(f"Creating CLAP embedding generator with model: {clap_cfg.model_id}")
        return CLAPEmbeddingGenerator(
            model_id=clap_cfg.model_id,
            target_sr=clap_cfg.target_sr,
            chunk_duration_s=clap_cfg.chunk_duration_s,
        )

    if embedding_type == EmbeddingModelType.MUQ:
        from ...infrastructure.model.muq import MuQEmbeddingGenerator

        muq_cfg = config.muq
        logger.info(f"Creating MuQ embedding generator with model: {muq_cfg.model_id}")
        return MuQEmbeddingGenerator(
            model_id=muq_cfg.model_id,
            target_sr=muq_cfg.target_sr,
            chunk_duration_s=muq_cfg.chunk_duration_s,
        )

    raise ValueError(
        f"Unknown embedding model type: '{embedding_type}'. "
        f"Supported types: {EmbeddingModelType.CLAP}, {EmbeddingModelType.MUQ}"
    )
