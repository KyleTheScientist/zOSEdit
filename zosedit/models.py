import re
from pathlib import Path


class Dataset:
    cols = 'volume', 'unit', 'date', 'ext', 'used', 'recformat', 'reclength', 'block_size', 'type', 'name'

    def parse(string: str, member: str = None) -> 'Dataset':
        '''Parse an FTP list entry string into a Dataset object'''
        result = {}

        try:
            data = string.split()
            if len(data) != len(Dataset.cols):
                name = data[-1].replace("'", "")
                return Dataset(member=member, name=name)

            for col, value in zip(Dataset.cols, data):
                result[col] = value

            result['name'] = result['name'].replace("'", "")
            result['reclength'] = int(result['reclength'])
        except Exception as e:
            print('Error parsing dataset:', e)
            print(string)

        return Dataset(member=member, **result)

    def __init__(self,
                 name: str = None,
                 member: str = None,
                 block_size: str = 32720,
                 date: str = None,
                 ext: str = None,
                 recformat: str = 'FB',
                 reclength: str = 80,
                 type: str = 'PS',
                 unit: int = 3390,
                 used: str = None,
                 volume: str = None,
                 new: bool = False,
                 local_path: Path = None):

        self.name = f'{name}({member})' if member else name
        self.member = member
        self.block_size: int = block_size
        self.date: str = date
        self.ext: int = ext
        self.recformat: str = recformat
        self.reclength: int = reclength
        self.type: str = type
        self.unit: int = unit
        self.used: int = used
        self.volume: str = volume

        self.new = new
        self.parent: str = name
        self.local_path: Path = local_path
        self._populated = False

    def properties(self) -> dict:
        cols = sorted(self.cols)
        return {col: getattr(self, col) for col in cols}

    def is_partitioned(self):
        return self.type == 'PO'

    def __repr__(self):
        attrs = ', '.join(f"{key}={val}" for key, val in self.properties().items())
        return f"Dataset({attrs})"

    def __str__(self):
        return ', '.join(f"{key}={val}" for key, val in self.properties().items())

    def __call__(self, member: str) -> 'Dataset':
        if not member:
            return self
        dataset = Dataset(member=member, **self.properties())
        return dataset


class Job:
    cols = 'name', 'id', 'owner', 'status', 'class', 'rc', 'spool_count'

    def __init__(self, string):
        self.string = string

        self.name: str = None
        self.id: str = None
        self.owner: str = None
        self.status: str = None
        self.class_: str = None
        self.rc: int = None
        self.spool_count: int = None
        try:
            weirdness = re.search(r'\(([^)]*)\)', string)
            if weirdness:
                group = weirdness.group()
                string = string.replace(group, group.replace(' ', '_'))
            string = string.replace('RC unknown', '?')

            for col, value in zip(self.cols, string.split()):
                setattr(self, col, value)

            if self.rc:
                if '=' in self.rc:
                    self.rc = self.rc.split('=')[1]
                    if self.rc.isdecimal():
                        self.rc = int(self.rc)
                else:
                    self.rc = self.rc.replace('_', '').replace('(', '').replace(')', '')
            elif self.status == 'ACTIVE':
                self.rc = self.status.capitalize()
            if self.spool_count is not None:
                self.spool_count = int(self.spool_count.split()[0])
        except Exception as e:
            print('Error parsing job:', e)
            print(string)

    def theme(self):
        if self.status == 'ACTIVE':
            return 'active'
        rc = '?' if self.rc is None else self.rc
        if rc == 0:
            return 'success'
        return 'error'

    def read(self, *args, **kwargs):
        return None

    def __repr__(self):
        attrs = ', '.join(f"{col}={getattr(self, col)}" for col in self.cols)
        return f"Job({attrs})"

    def __str__(self):
        return ', '.join(f"{col}={getattr(self, col)}" for col in self.cols)


class Spool:

    cols = 'id', 'stepname', 'procstep', 'c', 'ddname', 'byte_count'

    def __init__(self, string: str, job: Job):
        self.string = string
        self.job = job

        self.id: str = None
        self.stepname: str = None
        self.procstep: str = None
        self.c: str = None
        self.ddname: str = None
        self.byte_count: int = None
        try:
            data = string.split()
            if len(data) == len(self.cols) - 1:
                data.insert(3, '')

            for col, value in zip(self.cols, data):
                setattr(self, col, value)

            if self.byte_count is not None:
                self.byte_count = float(self.byte_count)
        except Exception as e:
            print('Error parsing spool:', e)
            print(string)

    def __repr__(self):
        attrs = ', '.join(f"{col}={getattr(self, col)}" for col in self.cols)
        return f"Spool({self.job.id}, {attrs})"

    def __str__(self):
        return ', '.join(f"{col}={getattr(self, col)}" for col in self.cols)
