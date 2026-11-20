"""My Project: A FastAPI API with a React visor."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("my-project")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0.0.0"
