import re
import ebcdic
from typing import Literal
from ftplib import FTP
from pathlib import Path
from tempfile import NamedTemporaryFile
from dearpygui import dearpygui as dpg
from zosedit.constants import tempdir
from traceback import format_exc
from textwrap import indent
from .models import Dataset, Job, Spool
from zosedit.gui.dialog import dialog
from . import constants
from time import time


def waits(func):
    def wrapper(self, *args, **kwargs):
        self.waiting = True
        self.wait_start = dpg.get_frame_count()
        try:
            result = func(self, *args, **kwargs)
        except Exception as e:
            self.waiting = False
            raise e
        self.waiting = False
        return result
    return wrapper


class zFTP:

    KEEP_ALIVE_INTERVAL = 60

    def __init__(self, root):
        self.root = root
        self.host = None
        self.user = None
        self.password = None
        self.waiting = False
        self.wait_start = 0
        self.ftp = None
        self.last_keep_alive = time()

    def keep_alive(self):
        if time() - self.last_keep_alive > self.KEEP_ALIVE_INTERVAL:
            self.check_alive()
            self.last_keep_alive = time()

    # === Datasets ===
    @waits
    def list_datasets(self, search_string: str):
        files = []
        try:
            self.set_ftp_vars('SEQ')
            self.ftp.dir(search_string, files.append)
        except Exception as e:
            if '550' in str(e):
                return []
            print('Error listing datasets')
            print(indent(format_exc(), '    '))
            self.show_error(f'Error listing datasets:\n{e}')
            return []
        datasets = [Dataset.parse(file_) for file_ in set(files[1:])]
        datasets = sorted(datasets, key=lambda x: (x.is_partitioned(), x.name, x.volume or ''))
        return datasets

    @waits
    def get_members(self, dataset: Dataset):
        members = []

        def append(line):
            members.append(line.split()[0])
        try:
            self.set_ftp_vars('SEQ', VOLUME=dataset.volume)
            self.ftp.dir(f"'{dataset.name}(*)'", append)
        except Exception as e:
            print('Error getting members for', dataset.name)
            print(indent(format_exc(), '    '))
            print(e)
        dataset._populated = True
        return members[1:] if members else []

    @waits
    def download(self, dataset: Dataset):
        raw_data = []

        # Download file
        def write(data):
            raw_data.append(data)

        try:
            self.set_ftp_vars('SEQ', VOLUME=dataset.volume)
            self.ftp.retrlines(f"RETR '{dataset.name}'", write)
            content = '\n'.join(raw_data)
            path = tempdir / dataset.name
            path.write_text(content, errors='replace')
            dataset.local_path = path
            return True
        except Exception as e:
            self.show_error(f'Error downloading dataset {dataset.name}:\n{e}')
            return False

    @waits
    def mkdir(self, dataset: Dataset):
        try:
            self.set_ftp_vars('SEQ', RECFM=dataset.recformat, LRECL=dataset.reclength, BLKSIZE=dataset.block_size)
            self.ftp.mkd(f"'{dataset.name}'")
        except Exception as e:
            self.show_error(f'Error creating partitioned dataset:\n{e}')
            return

    @waits
    def upload(self, dataset: Dataset):
        try:
            if dataset.member:
                self.set_ftp_vars('SEQ')
            else:
                self.set_ftp_vars('SEQ', RECFM=dataset.recformat, LRECL=dataset.reclength, BLKSIZE=dataset.block_size)
            self.ftp.storbinary(f"STOR '{dataset.name}'", dataset.local_path.open('rb'))
        except Exception as e:
            self.show_error(f'Error uploading dataset:\n{e}')
            return False
        return True

    @waits
    def delete(self, dataset: Dataset):
        try:
            self.set_ftp_vars('SEQ', VOLUME=dataset.volume)
            self.ftp.delete(f"'{dataset.name}'")
            print('Deleted', dataset.name)
        except Exception as e:
            self.show_error(f'Error deleting dataset:\n{e}')
            return False
        return True

    # === Jobs ===
    @waits
    def submit_job(self, dataset: Dataset, download=True):
        try:
            if download and not self.download(dataset):
                return False
            path = dataset.local_path
            self.set_ftp_vars('JES')
            response = self.ftp.storlines(f"STOR '{dataset.name}'", path.open('rb'))
            self.show_response(response)
        except Exception as e:
            self.show_error(f'Error submitting job:\n{e}')
            return False
        return True

    @waits
    def operator_command_prompt(self):
        def _submit_command():
            try:
                jcl = constants.OPERCMD_JCL.format(
                    name=dpg.get_value('operator_command_job_name').ljust(10),
                    params=dpg.get_value('operator_command_job_params'),
                    command=dpg.get_value('operator_command_input')
                )

                with NamedTemporaryFile(delete=False) as f:
                    path = Path(f.name)
                    path.write_text(jcl)

                self.set_ftp_vars('JES')
                response = self.ftp.storlines(f"STOR 'ZEDITOPR'", path.open('rb'))

                path.unlink()
                dpg.delete_item('operator_command_prompt')
                self.show_response(response)
            except Exception as e:
                dpg.delete_item('operator_command_prompt')
                self.show_error(f'Error submitting operator command:\n{e}')
                return

        w, h = 420, 150
        with dialog(tag='operator_command_prompt', label='Operator Command', width=w, height=h, modal=False):
            dpg.add_input_text(label='Command', tag='operator_command_input', hint='S <JOBNAME>',
                               on_enter=True, callback=_submit_command)
            dpg.add_spacer(height=5)

            with dpg.collapsing_header(label="Advanced"):
                dpg.add_input_text(label='Job Name', tag='operator_command_job_name', default_value='ZEDITOPR')
                dpg.add_input_text(label='Job Card Params', tag='operator_command_job_params',
                                   default_value='CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1),NOTIFY=&SYSUID')

            dpg.add_button(label='Submit', callback=_submit_command)

    @waits
    def list_jobs(self, name=None, id=None, owner=None):
        name = name or '*'
        owner = owner or '*'
        id = id or '*'
        raw_data: list[str] = []
        try:
            self.set_ftp_vars(f'JES', JESJOBNAME=name, JESOWNER=owner, JESENTRYLIMIT=1000)
            self.ftp.dir(id, raw_data.append)
        except Exception as e:
            if '550' in str(e):
                return []
            self.show_error(f'Error listing jobs:\n{e}')
            return []

        # If only a single job is returned it provides a different format
        if '--------' in raw_data:
            raw_data = ['', raw_data[1] + '  ' + raw_data[-1]]

        result = [Job(job_str) for job_str in raw_data[1:]]
        result.sort(key=lambda job: (job.rc == 'Active'), reverse=True)
        return result

    @waits
    def download_spools(self, job: Job):
        spools = self.list_spools(job)

        self.set_ftp_vars('JES')
        exceptions = []
        for spool in spools:
            spool_name = f'{job.id}.{spool.id}'
            try:
                path = tempdir / f'{job.id}-{spool.ddname}.txt'
                lines = []
                self.ftp.retrlines(f"RETR {spool_name}", lines.append)
                path.write_text('\n'.join(lines))
                spool.local_path = path
                yield spool
            except Exception as e:
                exceptions.append((spool, e))
                continue

        errors = []
        for spool, exception in exceptions:
            errors.append(f'Error downloading spool "{spool}":\n    {exception}')
        if errors:
            self.show_error('\n'.join(errors))

    @waits
    def download_spool(self, spool: Spool) -> bool:
        try:
            path = tempdir / f'{spool.id}.txt'
            lines = []
            self.set_ftp_vars('JES')
            self.ftp.retrlines(f"RETR {spool.job.id}.{spool.id}", lines.append)
            path.write_text('\n'.join(lines))
            spool.local_path = path
            return True
        except Exception as e:
            self.show_error(f'Error downloading spool {spool.job.id}.{spool.ddname}:\n{e}')
            return False

    @waits
    def list_spools(self, job: Job):
        raw_data: list[str] = []
        try:
            self.set_ftp_vars('JES')
            self.ftp.dir(job.id, raw_data.append)
        except Exception as e:
            self.show_error(f'Error listing spool outputs:\n{e}')
            return []

        return [Spool(spool_str, job) for spool_str in raw_data[4:-1]]

    # === Dialogs ===
    def show_error(self, message):
        print(indent(message, '    '))
        print(format_exc())
        with dialog(label='FTP Error', tag='error', autosize=True):
            dpg.add_text(message, color=(255, 0, 0))

    def show_response(self, response):
        with dialog(label='FTP Response', tag='ftp_response', width=300, height=150):
            dpg.add_text(response)
            match = re.search(r'(J\d+|JOB\d+)', response)
            if match:
                id = match.group(0)
                dpg.add_button(label=f'Open Job {id}',
                               width=-1,
                               callback=self._open_job_by_id,
                               user_data=id)
        print(response)

    def _open_job_by_id(self, sender, data, id):
        dpg.delete_item('ftp_response')
        job = self.list_jobs(id=id)[0]
        self.root.editor.open_job(job)

    # === Connection ===
    @waits
    def connect(self, host=None, user=None, password=None):
        host = host or self.host
        user = user or self.user
        password = password or self.password
        print(f'Connecting: {user}@{host}')
        self.ftp = FTP(host or self.host)
        self.ftp.login(user=user or self.user, passwd=password or self.password)
        self.host = host
        self.user = user
        self.password = password
        self.ftp.set_debuglevel(2)

        return True

    @waits
    def check_alive(self):
        try:
            if self.ftp:
                self.ftp.voidcmd('NOOP')
        except Exception:
            self.quit()
            self.connect()

    @waits
    def quit(self):
        try:
            if self.ftp:
                self.ftp.quit()
        except Exception:
            print('Error quitting')
            print(indent(format_exc(), '    '))

    def set_ftp_vars(self, mode=Literal['SEQ', 'JES', 'SQL'], **kwargs):
        self.check_alive()
        args = ' '.join(f"{key}={value}" for key, value in kwargs.items() if value is not None)
        self.ftp.sendcmd(f'SITE FILETYPE={mode} {args}')
