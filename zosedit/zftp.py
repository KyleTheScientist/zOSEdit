from ftplib import FTP
from .dataset import Dataset
from pathlib import Path
from tempfile import NamedTemporaryFile
from dearpygui import dearpygui as dpg
from zosedit.constants import tempdir

class zFTP:

    def __init__(self, host, user, password):
        self.host = host
        self.user = user
        self.password = password
        self.reconnect()

    def reconnect(self):
        print('Attempting to connect to', self.host)
        self.ftp = FTP(self.host)
        self.ftp.login(user=self.user, passwd=self.password)

    def quit(self):
        try:
            self.ftp.quit()
        except Exception as e:
            print('Error quitting', type(e), e)

    def check_alive(self):
        try:
            self.ftp.voidcmd('NOOP')
        except Exception as e:
            self.reconnect()

    def list_datasets(self, search_string: str):
        files = []
        try:
            self.check_alive()
            self.ftp.dir(search_string, files.append)
        except Exception as e:
            if '550' in str(e):
                return []
            print('Error listing datasets', type(e), e)
            self.show_error(f'Error listing datasets:\n{e}')
            return []
        datasets = [Dataset(file_) for file_ in files[1:]]
        datasets = sorted(datasets, key=lambda x: x.is_partitioned())
        return datasets

    def get_members(self, dataset: Dataset):
        members = []
        def append(line):
            members.append(line.split()[0])
        try:
            self.check_alive()
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
            raw_data.append(data)

        try:
            self.check_alive()
            self.ftp.retrlines(f"RETR '{name}'", write)
            raw_data = '\n'.join(raw_data)
        except Exception as e:
            print('Error downloading', dataset)
            print(e)
            self.show_error(f'Error downloading dataset:\n{e}')
            return

        # Group data into record_length chunks
        lines = [raw_data[i:i+dataset.record_length] for i in range(0, len(raw_data), dataset.record_length)]
        path = tempdir / name
        path.write_text('\n'.join(lines))
        return path

    def mkdir(self, dataset: Dataset):
        try:
            self.check_alive()
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
                self.check_alive()
                self.ftp.storbinary(f"STOR '{local_path.name}'", tmp)
        except Exception as e:
            print('Error uploading', dataset)
            self.show_error(f'Error uploading dataset:\n{e}')
            return False
        return True

    def delete(self, dataset: Dataset, member: str = None):
        name = f"{dataset.name}({member})" if member else dataset.name
        try:
            self.check_alive()
            self.ftp.delete(f"'{name}'")
            print('Deleted', name)
        except Exception as e:
            print('Error deleting', dataset)
            self.show_error(f'Error deleting dataset:\n{e}')
            return False
        return True

    def read(self, local_path: Path, dataset: Dataset):
        data = local_path.read_text()
        # Pad data to record_length
        lines = [line.ljust(dataset.record_length) for line in data.split('\n')]
        return ''.join(lines)

    def show_error(self, message):
        if dpg.does_item_exist('error'):
            dpg.delete_item('error')
        with dpg.window(label='FTP Error', tag='error', popup=True, autosize=True):
            dpg.add_text(message, color=(255, 0, 0))

        # center the error window
        w, h = dpg.get_item_rect_size('error')
        vw, vh = dpg.get_viewport_size()
        dpg.set_item_pos('error', (vw/2 - w/2, vh/2 - h/2))
