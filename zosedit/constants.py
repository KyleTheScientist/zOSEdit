from pathlib import Path
from tempfile import gettempdir


tempdir = Path(gettempdir()) / 'zosedit'
tempdir.mkdir(exist_ok=True)

OPERCMD_JCL = '''
//{name} JOB {params}
//CMD       EXEC PGM=IKJEFT01
//  COMMAND  '{command}'
'''.strip()
