"""Shared pytest fixtures.

Every test runs against a throwaway SQLite database so the suite works on a
fresh clone and never touches a developer's local data/symsafe.db.
"""

import sys

import pytest

import symsafe.config
import symsafe.feedback  # noqa: F401  (imported so its DB_PATH is patched)
import symsafe.main  # noqa: F401
import symsafe.store  # noqa: F401
import symsafe.web.app  # noqa: F401

try:
    import scripts.seed_demo_data  # noqa: F401
except ImportError:
    pass


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point every module's DB_PATH at a fresh temporary database."""
    db_path = tmp_path / "data" / "symsafe.db"
    for name, module in list(sys.modules.items()):
        if (name == "symsafe" or name.startswith("symsafe.") or name.startswith("scripts.")) \
                and module is not None and hasattr(module, "DB_PATH"):
            monkeypatch.setattr(module, "DB_PATH", db_path)
    symsafe.store.init_db(db_path)
    return db_path
