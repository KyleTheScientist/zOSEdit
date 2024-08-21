import re


class Dataset:
    cols = 'volume', 'unit', 'date', 'ext', 'used', 'record_format', 'record_length', 'block_size', 'type', 'name'

    def __init__(self, string, member: str = None):
        self.string = string
        self.member = member
        self.new = False

        self.volume: str = None
        self.unit: int = None
        self.date: str = None
        self.ext: int = None
        self.used: int = None
        self.record_format: str = None
        self.record_length: int = None
        self.block_size: int = None
        self.type: str = None
        self.name: str = None
        self._populated = False

        data = string.split()
        if len(data) != len(self.cols):
            self.name = data[-1].replace("'", "")
            return

        for col, value in zip(self.cols, data):
            setattr(self, col, value)

        self.name = self.name.replace("'", "")
        if self.member:
            self.name = f"{self.name}({self.member})"

        self.record_length = int(self.record_length)
        # self.used = int(self.used)
        # self.ext = int(self.ext)
        # self.block_size = int(self.block_size)

    def is_partitioned(self):
        return self.type == 'PO'

    def __repr__(self):
        attrs = ', '.join(f"{col}={getattr(self, col)}" for col in self.cols)
        return f"Dataset({attrs})"

    def __call__(self, member: str) -> 'Dataset':
        if not member:
            return self
        dataset = Dataset(self.string, member)
        return dataset


class Job:
    cols = 'name', 'id', 'owner', 'status', 'class', 'rc', 'spool_count'

    def __init__(self, string):
        self.name: str = None
        self.id: str = None
        self.owner: str = None
        self.status: str = None
        self.class_: str = None
        self.rc: int = None
        self.spool_count: int = None

        string = re.sub(r'\(([^\s]*?)\s([^\s].*?)\)', r'\1_\2', string)
        self.string = string
        data = string.split()
        for col, value in zip(self.cols, data):
            setattr(self, col, value)

        if self.rc is None:
            self.rc = '?'
        elif 'error' in self.rc:
            self.rc = 'JCLERR'
        else:
            self.rc = int(self.rc[3:])
        if self.spool_count is not None:
            self.spool_count = int(self.spool_count.split()[0])

    def __repr__(self):
        attrs = ', '.join(f"{col}={getattr(self, col)}" for col in self.cols)
        return f"Job({attrs})"


class Spool:

    cols = 'id', 'stepname', 'procstep', 'c', 'ddname', 'byte_count'

    def __init__(self, string):
        self.id: str = None
        self.stepname: str = None
        self.procstep: str = None
        self.c: str = None
        self.ddname: str = None
        self.byte_count: int = None

        self.string = string
        data = string.split()
        for col, value in zip(self.cols, data):
            setattr(self, col, value)

        if self.byte_count is not None:
            self.byte_count = int(self.byte_count)
