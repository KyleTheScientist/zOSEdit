import re
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


class zFTP:

    def __init__(self, root):
        self.root = root
        self.host = None
        self.user = None
        self.password = None
        self.ftp = None

    ### Datasets
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

    def download(self, dataset: Dataset):
        raw_data = []
        # Download file
        def write(data):
            raw_data.append(data)

        try:
            self.check_alive()
            self.set_ftp_vars('SEQ')
            self.ftp.retrlines(f"RETR '{dataset.name}'", write)
            content = '\n'.join(raw_data)
            path = tempdir / dataset.name
            path.write_text(content)
            dataset.local_path = path
            return True
        except Exception as e:
            self.show_error(f'Error downloading dataset {dataset.name}:\n{e}')
            return False

    def mkdir(self, dataset: Dataset):
        try:
            self.check_alive()
            self.set_ftp_vars('SEQ')
            self.ftp.mkd(f"'{dataset.name}'")
        except Exception as e:
            self.show_error(f'Error creating partitioned dataset:\n{e}')
            return

    def upload(self, dataset: Dataset):
        try:
            self.check_alive()
            self.set_ftp_vars('SEQ')
            self.set_ftp_vars('SEQ', RECFM='FB', LRECL=dataset.reclength, BLKSIZE=dataset.block_size)
            self.ftp.storlines(f"STOR '{dataset.name}'", dataset.local_path.open('rb'))
        except Exception as e:
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
            self.show_error(f'Error deleting dataset:\n{e}')
            return False
        return True

    ### Jobs
    def submit_job(self, dataset: Dataset, download=True):
        try:
            self.check_alive()
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

                self.check_alive()
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
            dpg.add_input_text(label='Command', tag='operator_command_input', hint='/D A,<JOBNAME>',
                               on_enter=True, callback=_submit_command)
            dpg.add_spacer(height=5)

            with dpg.collapsing_header(label="Advanced"):
                dpg.add_input_text(label='Job Name', tag='operator_command_job_name', default_value='ZEDITOPR')
                dpg.add_input_text(label='Job Card Params', tag='operator_command_job_params',
                                   default_value='CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1),NOTIFY=&SYSUID')

            dpg.add_button(label='Submit', callback=_submit_command)

    def list_jobs(self, name=None, id=None, owner=None):
        name = name or '*'
        owner = owner or '*'
        id = id or '*'
        raw_data: list[str] = []
        try:
            self.check_alive()
            self.set_ftp_vars(f'JES', JESJOBNAME=name, JESOWNER=owner)
            self.ftp.dir(id, raw_data.append)
        except Exception as e:
            if '550' in str(e):
                return []
            self.show_error(f'Error listing jobs:\n{e}')
            return []

        # If only a single job is returned it provides a different format
        if '--------' in raw_data:
            raw_data = ['', raw_data[1] + '  ' + raw_data[-1]]

        return [Job(job_str) for job_str in raw_data[1:]]

    def download_spools(self, job: Job):
        spools = self.list_spools(job)

        self.check_alive()
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

    def download_spool(self, spool: Spool):
        try:
            path = tempdir / f'{spool.id}.txt'
            lines = []
            self.check_alive()
            self.set_ftp_vars('JES')
            self.ftp.retrlines(f"RETR {spool.job.id}.{spool.id}", lines.append)
            path.write_text('\n'.join(lines))
            spool.local_path = path
            return True
        except Exception as e:
            self.show_error(f'Error downloading spool {spool.id}:\n{e}')
            return False

    def list_spools(self, job: Job):
        raw_data: list[str] = []
        try:
            self.check_alive()
            self.set_ftp_vars('JES')
            self.ftp.dir(job.id, raw_data.append)
        except Exception as e:
            self.show_error(f'Error listing spool outputs:\n{e}')
            return []

        return [Spool(spool_str, job) for spool_str in raw_data[4:-1]]

    ### Dialogs
    def show_error(self, message):
        print(indent(message, '    '))
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

    ### Connection
    def connect(self, host=None, user=None, password=None):
        self.ftp = FTP(host or self.host)
        print('Connecting to', host or self.host)
        self.ftp.login(user=user or self.user, passwd=password or self.password)
        self.host = host
        self.user = user
        self.password = password
        self.ftp.set_debuglevel(2)

        return True

    def quit(self):
        try:
            if self.ftp:
                self.ftp.quit()
        except Exception as e:
            print('Error quitting')
            print(indent(format_exc(), '    '))

    def check_alive(self):
        try:
            self.ftp.voidcmd('NOOP')
        except Exception as e:
            self.connect()

    def set_ftp_vars(self, mode=Literal['SEQ', 'JES', 'SQL'], **kwargs):
        self.check_alive()
        args = ' '.join(f"{key}={value}" for key, value in kwargs.items())
        self.ftp.sendcmd(f'SITE RESET')
        self.ftp.sendcmd(f'SITE FILETYPE={mode} {args}')
