import re
import contextlib
from dearpygui import dearpygui as dpg
from zosedit.models import Dataset
from traceback import format_exc
from textwrap import indent


class Explorer:

    def __init__(self, root):
        self.root = root

    def build(self):

        input_options = dict(on_enter=True, callback=self.refresh_datasets, uppercase=True)
        with dpg.group(tag='explorer_search_group'):
            with dpg.tab_bar(tag='explorer_tab_bar', callback=self.on_tab_changed):
                # Datasets tab
                with dpg.tab(label='Datasets', tag='explorer_datasets_tab'):
                    with dpg.group(horizontal=True, tag='explorer_dataset_search_group'):
                        dpg.add_input_text(hint='Search', tag='explorer_dataset_input', width=260, **input_options)
                        dpg.add_button(label=' O ', callback=self.refresh_datasets)
                    dpg.add_child_window(label='Results', tag='dataset_results')

                # Jobs tab
                input_options['callback'] = self.refresh_jobs
                with dpg.tab(label='Jobs', tag='explorer_jobs_tab'):
                    with dpg.group(tag='explorer_job_search_group', width=-1):
                        dpg.add_input_text(hint='Name', tag='explorer_jobname_input', **input_options)
                        dpg.add_input_text(hint='ID', tag='explorer_jobid_input', **input_options)
                        dpg.add_input_text(hint='Owner', tag='explorer_jobowner_input', **input_options)
                        dpg.add_button(label='Search', callback=self.refresh_jobs)
                    dpg.add_child_window(label='Results', tag='job_results')

    def on_tab_changed(self):
        pass

    def reset(self):
        with self.empty_results('dataset_results'):
            with self.empty_results('job_results'):
                pass
        dpg.set_value('explorer_tab_bar', 'explorer_datasets_tab')
        dpg.set_value('explorer_jobname_input', '')
        dpg.set_value('explorer_jobid_input', '')
        dpg.set_value('explorer_jobowner_input', '')
        dpg.set_value('explorer_dataset_input', '')

    def refresh_jobs(self):
        print('Refreshing jobs')
        name = dpg.get_value('explorer_jobname_input')
        id = dpg.get_value('explorer_jobid_input')
        owner = dpg.get_value('explorer_jobowner_input')
        if not name and not id and not owner:
            return

        # Clear existing results
        with self.empty_results('job_results'):
            # Search for jobs
            status = dpg.add_text('Searching...')
            try:
                jobs = self.root.ftp.list_jobs(name, id, owner)
            except Exception as e:
                dpg.set_value(status, f'Error: {e}')
                print('Error listing jobs')
                print(indent(format_exc(), '    '))
                dpg.configure_item(status, color=(255, 0, 0))
                return
            dpg.set_value(status, f'Found {len(jobs)} job(s)')

            # List results
            with dpg.table(header_row=True, policy=dpg.mvTable_SizingStretchProp):
                dpg.add_table_column(label='ID')
                dpg.add_table_column(label='Name')
                dpg.add_table_column(label='Owner')
                dpg.add_table_column(label='RC')
                for job in jobs:
                    with dpg.table_row():
                        dpg.add_button(label=job.id, callback=self._open_job(job))
                        dpg.add_text(job.name)
                        dpg.add_text(job.owner)
                        dpg.add_text(job.rc)

    def refresh_datasets(self, value=None):
        if value:
            dpg.set_value('explorer_dataset_input', value)
        # Get datasets
        search = value or dpg.get_value('explorer_dataset_input')
        if not search:
            return
        if not re.match(r"'[^']+'", search):
            if '*' not in search and len(search.split('.')[-1]) < 8:
                search = f"'{search}*'"
            else:
                search = f"'{search}'"

        with self.empty_results('dataset_results'): # Clears existing results
            # Search for datasets
            status = dpg.add_text('Searching...')
            datasets = [d for d in self.root.ftp.list_datasets(search) if d.type is not None]
            dpg.set_value(status, f'Found {len(datasets)} dataset(s)')

            # List results
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
                dpg.add_table_column(label='Name')
                for dataset in datasets:
                    with dpg.table_row():
                        with dpg.table_cell():
                            self.entry(dataset, leaf=not dataset.is_partitioned())


    def entry(self, dataset: Dataset, leaf=False, **kwargs):
        # Create the button/dropdown for the dataset
        header = dpg.add_collapsing_header(label=dataset.member or dataset.name, leaf=leaf, **kwargs)

        # Decide left-click functionality
        callback = self._open_file(dataset) if leaf else self._populate_pds(dataset, header)

        # Create context menu
        dpg.popup
        with dpg.window(show=False, autosize=True, popup=True) as context_menu:
            if leaf:
                dpg.add_menu_item(label='Open', callback=self._open_file(dataset))
            dpg.add_menu_item(label='Delete', callback=self.try_delete_file, user_data=dataset)

        # Add functionality to the button/dropdown
        with dpg.item_handler_registry() as reg:
            dpg.add_item_clicked_handler(dpg.mvMouseButton_Left, callback=callback)
            dpg.add_item_clicked_handler(dpg.mvMouseButton_Right, callback=lambda: dpg.configure_item(context_menu, show=True))
        dpg.bind_item_handler_registry(header, reg)


    def populate_pds(self, dataset: Dataset, id: int):
        if dataset._populated:
            return
        members = self.root.ftp.get_members(dataset)
        if not members:
            dpg.add_text('No members found', parent=id, indent=10)
            return

        for member in members:
            self.entry(dataset=dataset(member), leaf=True, parent=id, indent=10)


    def _populate_pds(self, dataset: Dataset, parent: int):
        return lambda: self.populate_pds(dataset, parent)

    def _open_file(self, dataset: Dataset):
        def callback():
            self.root.editor.open_file(dataset)
        return callback

    def _open_job(self, job):
        def callback():
            self.root.editor.open_job(job)
        return callback

    def try_delete_file(self, sender, data, dataset):
        w, h = 300, 150
        with dpg.window(modal=True, tag='delete_file_dialog', autosize=True, no_title_bar=True):
            dpg.add_text('Confirm deletion of:', color=(255, 80, 80))
            dpg.add_text(dataset.name, bullet=True)
            with dpg.group(horizontal=True):
                bw = 100
                dpg.add_button(label='Delete', callback=self.delete_file, user_data=dataset, width=bw)
                dpg.add_button(label='Cancel', callback=lambda: dpg.delete_item('delete_file_dialog'), width=bw)

    def delete_file(self, sender, data, dataset):
        dpg.delete_item('delete_file_dialog')
        self.root.ftp.delete(dataset)
        self.root.editor.close_tab_by_dataset(dataset)
        self.refresh_datasets()

    @contextlib.contextmanager
    def empty_results(self, item):
        for child in dpg.get_item_children(item)[1]:
            dpg.delete_item(child)

        dpg.push_container_stack(item)
        yield
        dpg.pop_container_stack()
