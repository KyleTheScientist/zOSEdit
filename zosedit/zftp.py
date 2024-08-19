from ftplib import FTP
from .dataset import Dataset
from pathlib import Path
from tempfile import NamedTemporaryFile
from dearpygui import dearpygui as dpg
from zosedit.constants import tempdir

class zFTP:

    def __init__(self, host, user, password):
        self.ftp = FTP(host)
        print('Attempting to connect to', host)
        self.ftp.login(user=user, passwd=password)

    def quit(self):
        self.ftp.quit()

    def list_datasets(self, search_string: str):
        files = []
        try:
            self.ftp.dir(search_string, files.append)
        except Exception as e:
            if '550' in str(e):
                return []
            print('Error listing datasets', type(e), e)
            self.error(f'Error listing datasets:\n{e}')
            return []
        datasets = [Dataset(file_) for file_ in files[1:]]
        datasets = sorted(datasets, key=lambda x: x.is_partitioned())
        return datasets

    def get_members(self, dataset: Dataset):
        members = []
        def append(line):
            members.append(line.split()[0])
        try:
            self.ftp.dir(f"'{dataset.name}(*)'", append)
        except Exception as e:
            print('Error getting members for', dataset.name)
            print(e)
        dataset._populated = True
        return members[1:] if members else []

    def download_file(self, dataset: Dataset, member:str =None):
        name = f"{dataset.name}({member})" if member else dataset.name

        raw_data = []
        # Download file
        def write(data):
            raw_data.append(data.decode('cp500'))

        try:
            self.ftp.retrbinary(f"RETR '{name}'", write)
            raw_data = ''.join(raw_data)
        except Exception as e:
            print('Error downloading', dataset)
            self.error(f'Error downloading dataset:\n{e}')
            return

        # Group data into record_length chunks
        lines = [raw_data[i:i+dataset.record_length] for i in range(0, len(raw_data), dataset.record_length)]
        path = tempdir / name
        path.write_text('\n'.join(lines))
        return path

    def mkdir(self, dataset: Dataset):
        try:
            self.ftp.mkd(f"'{dataset.name}'")
        except Exception as e:
            print('Error creating PDS', dataset)
            print(e)
            return

    def upload(self, local_path: Path, dataset: Dataset):
        data = self.read(local_path, dataset)
        try:
            with NamedTemporaryFile() as tmp:
                tmp.write(data.encode('cp500'))
                tmp.seek(0)
                self.ftp.storbinary(f"STOR '{local_path.name}'", tmp)
        except Exception as e:
            print('Error uploading', dataset)
            self.error(f'Error uploading dataset:\n{e}')
            return False
        return True

    def read(self, local_path: Path, dataset: Dataset):
        data = local_path.read_text()
        # Pad data to record_length
        lines = [line.ljust(dataset.record_length) for line in data.split('\n')]
        return ''.join(lines)

    def error(self, message):
        if dpg.does_item_exist('error'):
            dpg.delete_item('error')
        with dpg.window(label='FTP Error', tag='error'):
            dpg.add_text(message, color=(255, 0, 0))
