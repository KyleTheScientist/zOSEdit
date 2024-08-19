class Dataset:
    cols = 'volume', 'unit', 'date', 'ext', 'used', 'record_format', 'record_length', 'block_size', 'type', 'name'

    def __init__(self, line):
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

        self.line = line
        data = line.split()
        if len(data) != len(self.cols):
            self.name = data[-1].replace("'", "")
            return

        for col, value in zip(self.cols, data):
            setattr(self, col, value)

        self.name = self.name.replace("'", "")
        # self.used = int(self.used)
        # self.ext = int(self.ext)
        self.record_length = int(self.record_length)
        # self.block_size = int(self.block_size)

    def is_partitioned(self):
        return self.type == 'PO'

    def __repr__(self):
        attrs = ', '.join(f"{col}={getattr(self, col)}" for col in self.cols)
        return f"Dataset({attrs})"
