import re
from dearpygui import dearpygui as dpg
from zosedit.dataset import Dataset


class Explorer:

    def __init__(self, root):
        self.root = root

    def build(self):
        with dpg.group(horizontal=True, show=False, tag='explorer_search_group'):
            dpg.add_input_text(hint='Enter a dataset', tag='explorer_search_input',
                               on_enter=True, callback=self.refresh, width=260, uppercase=True)
            dpg.add_button(label=' O ', callback=self.refresh)

    def refresh(self):
        # Get datasets
        search = dpg.get_value('explorer_search_input')
        if not search:
            return
        if not re.match(r"'[^']+'", search):
            if '*' not in search and len(search.split('.')[-1]) < 8:
                search = f"'{search}*'"
            else:
                search = f"'{search}'"

        # Clear existing results
        if dpg.does_item_exist('results'):
            dpg.delete_item('results')

        # List results
        with dpg.child_window(label='Results', tag='results', parent='win_explorer'):

            # Search for datasets
            dpg.add_text('Searching...', tag='search_status')
            datasets = [d for d in self.root.ftp.list_datasets(search) if d.type is not None]
            dpg.set_value('search_status', f'Found {len(datasets)} dataset(s)')

            # Create buttons for each dataset
            with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
                dpg.add_table_column(label='Name')
                for dataset in datasets:
                    with dpg.table_row():
                        if dataset.is_partitioned():
                            with dpg.table_cell():
                                with dpg.collapsing_header(label=dataset.name, bullet=False) as id:
                                    with dpg.item_handler_registry() as reg:
                                        dpg.add_item_toggled_open_handler(callback=self._populate_pds(dataset, id))
                                    dpg.bind_item_handler_registry(id, reg)
                        else:
                            with dpg.table_cell():
                                self.leaf(dataset)

    def leaf(self, dataset: Dataset, member: str = None, **kwargs):
        header = dpg.add_collapsing_header(label=member or dataset.name, leaf=True, **kwargs)
        with dpg.item_handler_registry() as reg:
            dpg.add_item_clicked_handler(callback=self._open_file(dataset, member))
        dpg.bind_item_handler_registry(header, reg)

    def populate_pds(self, dataset: Dataset, id: int):
        if dataset._populated:
            return
        for member in self.root.ftp.get_members(dataset):
            self.leaf(dataset=dataset, member=member, parent=id, indent=10)

    def _populate_pds(self, dataset: Dataset, parent: int):
        return lambda: self.populate_pds(dataset, parent)

    def _open_file(self, dataset: Dataset, member: str):
        def callback():
            filename = self.root.ftp.download_file(dataset, member)
            self.root.editor.open_file(filename, dataset)
        return callback
