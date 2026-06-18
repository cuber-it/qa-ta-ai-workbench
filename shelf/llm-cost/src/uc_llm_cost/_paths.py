"""Host-injectable base directory for this package's data and log files.

Default is the current working directory; the host app overrides it via
``uc_llm_cost.set_data_dir(path)`` so that data/ and logs/ land where the app
keeps them. Keeps the package free of any assumption about living inside a repo.
"""
from pathlib import Path

base_dir: Path = Path.cwd()


def data(*parts: str) -> Path:
    return base_dir.joinpath("data", *parts)


def logs(*parts: str) -> Path:
    return base_dir.joinpath("logs", *parts)
