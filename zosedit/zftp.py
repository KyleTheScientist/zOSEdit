from typing import Literal
from ftplib import FTP
from .models import Dataset, Job, Spool
from pathlib import Path
from tempfile import NamedTemporaryFile
from dearpygui import dearpygui as dpg
from zosedit.constants import tempdir
from traceback import format_exc
from textwrap import indent

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
            print('Error quitting')
            print(indent(format_exc(), '    '))

    def check_alive(self):
        try:
            self.ftp.voidcmd('NOOP')
        except Exception as e:
            self.reconnect()

    def list_datasets(self, search_string: str):
        files = []
        try:
            self.check_alive()
            self.set_ftp_vars('SEQ')
            self.ftp.dir(search_string, files.append)
        except Exception as e:
            if '550' in str(e):
                return []
            print('Error listing datasets')
            print(indent(format_exc(), '    '))
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
            self.set_ftp_vars('SEQ')
            self.ftp.dir(f"'{dataset.name}(*)'", append)
        except Exception as e:
            print('Error getting members for', dataset.name)
            print(indent(format_exc(), '    '))
            print(e)
        dataset._populated = True
        return members[1:] if members else []

    def download_file(self, name):
        raw_data = []
        # Download file
        def write(data):
            raw_data.append(data)

        try:
            self.check_alive()
            self.set_ftp_vars('SEQ')
            self.ftp.retrlines(f"RETR '{name}'", write)
            content = '\n'.join(raw_data)
        except Exception as e:
            print('Error downloading', name)
            print(indent(format_exc(), '    '))
            print(e)
            self.show_error(f'Error downloading dataset:\n{e}')
            return

        path = tempdir / name
        path.write_text(content)
        return path

    def mkdir(self, dataset: Dataset):
        try:
            self.check_alive()
            self.set_ftp_vars('SEQ')
            self.ftp.mkd(f"'{dataset.name}'")
        except Exception as e:
            print('Error creating PDS', dataset)
            print(indent(format_exc(), '    '))
            print(e)
            return

    def upload(self, local_path: Path):
        data = local_path.read_text()
        try:
            with NamedTemporaryFile() as tmp:
                tmp.write(data.encode('cp500'))
                tmp.seek(0)
                self.check_alive()
                self.set_ftp_vars('SEQ')
                self.ftp.storbinary(f"STOR '{local_path.name}'", tmp)
        except Exception as e:
            print('Error uploading', local_path)
            print(indent(format_exc(), '    '))
            self.show_error(f'Error uploading dataset:\n{e}')
            return False
        return True

    def delete(self, dataset: Dataset):
        try:
            self.check_alive()
            self.set_ftp_vars('SEQ')
            self.ftp.delete(f"'{dataset.name}'")
            print('Deleted', dataset.name)
        except Exception as e:
            print('Error deleting', dataset)
            print(indent(format_exc(), '    '))
            self.show_error(f'Error deleting dataset:\n{e}')
            return False
        return True

    def submit_job(self, dataset: Dataset):
        try:
            self.check_alive()
            path: Path = self.download_file(dataset.name)
            self.ftp.set_debuglevel(2)
            self.set_ftp_vars('JES')
            response = self.ftp.storlines(f"STOR '{dataset.name}'", path.open('rb'))
            self.show_response(response)
        except Exception as e:
            print('Error submitting job')
            print(indent(format_exc(), '    '))
            self.show_error(f'Error submitting job:\n{e}')
            return False
        return True

    def list_jobs(self, name=None, id=None, owner=None):
        name = name or '*'
        owner = owner or '*'
        id = id or '*'
        print(f'Listing jobs with name={name}, owner={owner}, id={id}')
        raw_data: list[str] = []
        try:
            self.check_alive()
            self.set_ftp_vars(f'JES', JESJOBNAME=name, JESOWNER=owner)
            self.ftp.dir(id, raw_data.append)
        except Exception as e:
            if '550' in str(e):
                return []
            print('Error listing jobs')
            print(indent(format_exc(), '    '))
            self.show_error(f'Error listing jobs:\n{e}')
            return []

        # If only a single job is returned it provides a different format
        if '--------' in raw_data:
            raw_data = ['', raw_data[1] + '  ' + raw_data[-1]]

        return [Job(job_str) for job_str in raw_data[1:]]

    def download_spools(self, job: Job):
        print(f'Downloading spools for job {job.id}')
        spools = self.list_spools(job.id)

        self.check_alive()
        self.set_ftp_vars('JES')
        exceptions = []
        result = []
        for spool in spools:
            spool_name = f'{job.id}.{spool.id}'
            try:
                path = tempdir / f'{job.name}({job.id})-{spool.ddname}.txt'
                lines = []
                self.ftp.retrlines(f"RETR {spool_name}", lines.append)
                path.write_text('\n'.join(lines))
                spool.local_path = path
                result.append(spool)
            except Exception as e:
                print(f'Error downloading spool:\n\t{spool}')
                print(indent(format_exc(), '    '))
                exceptions.append((spool, e))
                continue

        errors = []
        for spool, exception in exceptions:
            errors.append(f'Error downloading spool "{spool}":\n    {exception}')
        if errors:
            self.show_error('\n'.join(errors))

        return result

    def list_spools(self, job_id):
        print(f'Listing spools for job {job_id}')

        raw_data: list[str] = []
        try:
            self.check_alive()
            self.set_ftp_vars('JES')
            self.ftp.dir(job_id, raw_data.append)
        except Exception as e:
            print('Error listing spool outputs')
            print(indent(format_exc(), '    '))
            self.show_error(f'Error listing spool outputs:\n{e}')
            return []

        return [Spool(spool_str) for spool_str in raw_data[4:-1]]

    def set_ftp_vars(self, mode=Literal['SEQ', 'JES', 'SQL'], **kwargs):
        self.check_alive()
        args = ' '.join(f"{key}={value}" for key, value in kwargs.items())
        self.ftp.sendcmd(f'SITE RESET')
        self.ftp.sendcmd(f'SITE FILETYPE={mode} {args}')

    def show_error(self, message):
        if dpg.does_item_exist('error'):
            dpg.delete_item('error')
        with dpg.window(label='FTP Error', tag='error', autosize=True, modal=True):
            dpg.add_text(message, color=(255, 0, 0))

        # center the error window
        w, h = dpg.get_text_size(message)
        try:
            vw, vh = dpg.get_viewport_width(), dpg.get_viewport_height()
        except:
            vw, vh = w, h
        dpg.set_item_pos('error', (vw/2 - w/2, vh/2 - h/2))

    def show_response(self, response):
        if dpg.does_item_exist('response'):
            dpg.delete_item('response')
        with dpg.window(label='FTP Response', tag='response', autosize=True, modal=True):
            dpg.add_text(response)

        # center the response window
        w, h = dpg.get_text_size(response)
        try:
            vw, vh = dpg.get_viewport_width(), dpg.get_viewport_height()
        except:
            vw, vh = w, h
        dpg.set_item_pos('response', (vw/2 - w/2, vh/2 - h/2))
