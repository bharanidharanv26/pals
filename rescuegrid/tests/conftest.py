"""Tests never share the demonstration user's persistent workspace database."""
import os
import tempfile
from pathlib import Path

runtime=Path(__file__).resolve().parents[1]/'runtime'
runtime.mkdir(exist_ok=True)
test_directory=tempfile.TemporaryDirectory(prefix='engine-tests-',dir=runtime)
os.environ['DATABASE_URL']=f"sqlite:///{(Path(test_directory.name)/'test.db').as_posix()}"

def pytest_sessionfinish(session,exitstatus):
    from backend import store
    store.db.dispose()
    test_directory.cleanup()
