from pathlib import Path
from tempfile import gettempdir

tempdir = Path(gettempdir()) / 'zosedit'
tempdir.mkdir(exist_ok=True)
