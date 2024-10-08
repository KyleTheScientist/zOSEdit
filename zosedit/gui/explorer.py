import re
import contextlib
from dearpygui import dearpygui as dpg
from zosedit.gui.dialog import dialog
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
                        input_width = dpg.get_item_width('win_explorer') - 40
                        dpg.add_input_text(hint='Search',
                                           tag='explorer_dataset_input',
                                           width=input_width,
                                           **input_options)
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

        with dpg.theme(tag='explorer_theme_volume'):
            with dpg.theme_component(dpg.mvSelectable):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (170, 170, 170, 255))

        with dpg.theme(tag='rc_theme_error'):
            with dpg.theme_component(dpg.mvSelectable):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (140, 120, 80, 255))

        with dpg.theme(tag='rc_theme_success'):
            with dpg.theme_component(dpg.mvSelectable):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (50, 140, 80, 255))

        with dpg.theme(tag='rc_theme_active'):
            with dpg.theme_component(dpg.mvSelectable):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (70, 100, 160, 255))

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

    def search_for_job_id(self, id):
        dpg.set_value('explorer_tab_bar', 'explorer_jobs_tab')
        dpg.set_value('explorer_jobname_input', '')
        dpg.set_value('explorer_jobid_input', id)
        dpg.set_value('explorer_jobowner_input', '')
        self.refresh_jobs()

    def refresh_jobs(self):
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
                jobs = self.root.zftp.list_jobs(name, id, owner)
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
                        dpg.add_selectable(span_columns=True, label=job.id, callback=self.open_job, user_data=job)
                        dpg.add_selectable(span_columns=True, label=job.name, callback=self.open_job, user_data=job)
                        dpg.add_selectable(span_columns=True, label=job.owner, callback=self.open_job, user_data=job)
                        rc = dpg.add_selectable(span_columns=True, label=job.rc, callback=self.open_job, user_data=job)
                        dpg.bind_item_theme(rc, f'rc_theme_{job.theme()}')

    def refresh_datasets(self):
        # Get datasets
        search = dpg.get_value('explorer_dataset_input')
        if not search:
            return
        if not re.match(r"'[^']+'", search):
            if '*' not in search and len(search.split('.')[-1]) < 8:
                search = f"'{search}*'"
            else:
                search = f"'{search}'"

        with self.empty_results('dataset_results'):  # Clears existing results
            # Search for datasets
            status = dpg.add_text('Searching...')
            datasets = [d for d in self.root.zftp.list_datasets(search) if d.type is not None]
            dpg.set_value(status, f'Found {len(datasets)} dataset(s)')

            # List results
            with dpg.table(header_row=True, policy=dpg.mvTable_SizingStretchProp, tag='dataset_results_table'):
                dpg.add_table_column(label='Volume')
                dpg.add_table_column(label='Name')
                for dataset in datasets:
                    self.entry(dataset, leaf=not dataset.is_partitioned())

    def entry(self, dataset: Dataset, leaf: bool, **kwargs):
        with dpg.table_row(parent='dataset_results_table', **kwargs) as row:
            with dpg.table_cell():
                volume = '' if dataset.member else dataset.volume
                selectable = dpg.add_selectable(label=volume, span_columns=True)
                dpg.bind_item_theme(selectable, 'explorer_theme_volume')

            with dpg.table_cell():
                # Create the button/dropdown for the dataset
                name = dataset.name + '/' if dataset.is_partitioned() else dataset.name
                dpg.add_selectable(label=dataset.member or name, span_columns=True)

        # Create context menu
        dpg.popup
        with dpg.window(show=False, autosize=True, popup=True) as context_menu:
            if leaf:
                dpg.add_menu_item(label='Open', callback=self._open_file(dataset))
                dpg.add_menu_item(label='Submit', callback=self._submit_file(dataset))
            else:
                dpg.add_menu_item(label='Create member', callback=self._new_member(dataset))
            dpg.add_menu_item(label='Delete', callback=self.try_delete_file, user_data=dataset)
            dpg.add_menu_item(label='Properties', callback=self.properties_popup, user_data=dataset)

        # Add functionality to the button/dropdown
        with dpg.item_handler_registry() as reg:
            on_left_click = self._open_file(dataset) if leaf else self._populate_pds(dataset, row)
            dpg.add_item_clicked_handler(dpg.mvMouseButton_Left, callback=on_left_click)
            dpg.add_item_clicked_handler(dpg.mvMouseButton_Left, callback=lambda: dpg.set_value(selectable, False))
            dpg.add_item_clicked_handler(dpg.mvMouseButton_Right,
                                         callback=lambda: dpg.configure_item(context_menu, show=True))
        dpg.bind_item_handler_registry(selectable, reg)

    def populate_pds(self, dataset: Dataset, parent_row: int):
        if dataset._populated:
            dataset._populated = False
            for child in dpg.get_item_children('dataset_results_table')[1]:
                if dpg.get_item_user_data(child) == dataset:
                    dpg.delete_item(child)
            return

        # Load members
        # status = dpg.add_text('Loading members...', parent=id, indent=10)
        members = self.root.zftp.get_members(dataset)
        # dpg.delete_item(status)

        children = dpg.get_item_children('dataset_results_table')[1]
        index = children.index(parent_row) + 1
        if index < len(children):
            before = children[index]
        else:
            before = 0

        if not members:
            with dpg.table_row(parent='dataset_results_table', before=before, user_data=dataset):
                dpg.add_table_cell()
                with dpg.table_cell():
                    dpg.add_text('<empty>')
            return
        # List members
        for member in members:
            self.entry(dataset=dataset(member), leaf=True, before=before, user_data=dataset)

    def _populate_pds(self, dataset: Dataset, parent: int):
        return lambda: self.populate_pds(dataset, parent)

    def _new_member(self, dataset: Dataset):
        def callback():
            self.root.editor.new_dataset_tab()
            self.root.editor.save_as(default_name=dataset.name + '()')
        return callback

    def _open_file(self, dataset: Dataset):
        def callback():
            self.root.editor.open_file(dataset)
        return callback

    def _submit_file(self, dataset: Dataset):
        def callback():
            self.root.zftp.submit_job(dataset)
        return callback

    def open_job(self, sender, data, job):
        dpg.set_value(sender, False)
        self.root.editor.open_job(job)

    def try_delete_file(self, sender, data, dataset):
        with dpg.window(modal=True, tag='delete_file_dialog', autosize=True, no_title_bar=True):
            dpg.add_text('Confirm deletion of:', color=(255, 80, 80))
            dpg.add_text(dataset.name, bullet=True)
            with dpg.group(horizontal=True):
                bw = 100
                dpg.add_button(label='Delete', callback=self.delete_file, user_data=dataset, width=bw)
                dpg.add_button(label='Cancel', callback=lambda: dpg.delete_item('delete_file_dialog'), width=bw)

    def delete_file(self, sender, data, dataset):
        dpg.delete_item('delete_file_dialog')
        self.root.zftp.delete(dataset)
        self.root.editor.close_tab_by_dataset(dataset)
        self.refresh_datasets()

    def properties_popup(self, sender, data, dataset):
        with dialog(label=dataset.name, tag='properties_dialog', width=500, height=300):
            properties = dataset.properties()
            with dpg.table(header_row=True, policy=dpg.mvTable_SizingFixedFit):
                dpg.add_table_column(label='Property')
                dpg.add_table_column(label='Value')

                for key, value in properties.items():
                    with dpg.table_row():
                        with dpg.table_cell():
                            dpg.add_text(key.upper())
                        with dpg.table_cell():
                            dpg.add_input_text(readonly=True, default_value=value, width=400)

    @contextlib.contextmanager
    def empty_results(self, item):
        for child in dpg.get_item_children(item)[1]:
            dpg.delete_item(child)

        dpg.push_container_stack(item)
        yield
        dpg.pop_container_stack()
