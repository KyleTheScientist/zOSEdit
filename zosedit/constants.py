from pathlib import Path
from tempfile import gettempdir
from textwrap import dedent
tempdir = Path(gettempdir()) / 'zosedit'
tempdir.mkdir(exist_ok=True)

OPERCMD_JCL = '''
//{name} JOB {params}
//CMD       EXEC PGM=SDSF
//CMDOUT DD SYSOUT=*
//ISFOUT DD DUMMY
//ISFIN  DD *
  SET CONSOLE BATCH
  SET DELAY 600
  {command}
  PRINT FILE CMDOUT
  ULOG
  PRINT
  PRINT CLOSE
/*
//
'''.strip()
