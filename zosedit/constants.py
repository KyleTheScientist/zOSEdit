from pathlib import Path
from tempfile import gettempdir
from textwrap import dedent
tempdir = Path(gettempdir()) / 'zosedit'
tempdir.mkdir(exist_ok=True)

jcl_path = Path(__file__).parent / 'jcl'
JCL = {
    'opercmd': (jcl_path / 'opercmd.jcl').read_text(),
}
