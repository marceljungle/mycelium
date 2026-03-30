"""Application package initialization.

Exports are lazy to avoid circular imports (config → registry → application → services → config).
"""

__all__ = [
    "MyceliumService",
    "MusicSearchUseCase",
]


def __getattr__(name: str):
    if name == "MyceliumService":
        from .services import MyceliumService
        return MyceliumService
    if name == "MusicSearchUseCase":
        from .search.use_cases import MusicSearchUseCase
        return MusicSearchUseCase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
