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

    def hide(self):
        dpg.hide_item('explorer_search_group')
        if dpg.does_item_exist('results'):
            dpg.delete_item('results')

    def show(self, value=''):
        dpg.show_item('explorer_search_group')
        if value:
            dpg.set_value('explorer_search_input', value)
            self.refresh()

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
                        with dpg.table_cell():
                            self.entry(dataset, leaf=not dataset.is_partitioned())

    def entry(self, dataset: Dataset, member: str = None, leaf=False, **kwargs):
        # Create the button/dropdown for the dataset
        header = dpg.add_collapsing_header(label=member or dataset.name, leaf=leaf, **kwargs)


        # Decide left-click functionality
        callback = self._open_file(dataset, member) if leaf else self._populate_pds(dataset, header)

        # Create context menu
        dpg.popup
        with dpg.window(show=False, autosize=True, popup=True) as context_menu:
            if leaf:
                dpg.add_menu_item(label='Open', callback=self._open_file(dataset, member))
            dpg.add_menu_item(label='Delete', callback=self.try_delete_file, user_data=(dataset, member))

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
            self.entry(dataset=dataset, member=member, leaf=True, parent=id, indent=10)


    def _populate_pds(self, dataset: Dataset, parent: int):
        return lambda: self.populate_pds(dataset, parent)

    def _open_file(self, dataset: Dataset, member: str):
        def callback():
            filename = self.root.ftp.download_file(dataset, member)
            self.root.editor.open_file(filename, dataset)
        return callback

    def try_delete_file(self, sender, data, user_data):
        dataset, member = user_data
        w, h = 300, 150
        with dpg.window(modal=True, tag='delete_file_dialog', autosize=True, no_title_bar=True):
            dpg.add_text('Confirm deletion of:', color=(255, 80, 80))
            name = f'{dataset.name}({member})' if member else dataset.name
            dpg.add_text(name, bullet=True)
            with dpg.group(horizontal=True):
                bw = 100
                dpg.add_button(label='Delete', callback=self.delete_file, user_data=user_data, width=bw)
                dpg.add_button(label='Cancel', callback=lambda: dpg.delete_item('delete_file_dialog'), width=bw)

    def delete_file(self, sender, data, user_data):
        dpg.delete_item('delete_file_dialog')
        self.root.ftp.delete(*user_data)
        self.refresh()
