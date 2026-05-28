# Lazy imports to avoid circular import issues during test collection.
# Import directly from submodules when needed:
#   from app.services.backtest_service import BacktestService
#   from app.services.selection_service import SelectionService
#   from app.services.data_service import DataSyncService

__all__ = ["DataSyncService", "SelectionService", "BacktestService"]


def __getattr__(name: str):
    _lazy_imports = {
        "BacktestService": "app.services.backtest_service",
        "DataSyncService": "app.services.data_service",
        "SelectionService": "app.services.selection_service",
    }
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
