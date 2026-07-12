"""Migration sanity that runs without infrastructure: revision graph loads and the initial
revision is reversible by construction. The real-Postgres up/down run (skill oracle) is a
verification step: `make up` + `alembic upgrade head` + `alembic downgrade base`."""
from alembic.config import Config
from alembic.script import ScriptDirectory


def _script_dir() -> ScriptDirectory:
    cfg = Config("alembic.ini")
    return ScriptDirectory.from_config(cfg)


def test_single_head():
    heads = _script_dir().get_heads()
    assert heads == ["0001"]


def test_initial_revision_has_up_and_down():
    rev = _script_dir().get_revision("0001")
    module = rev.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
