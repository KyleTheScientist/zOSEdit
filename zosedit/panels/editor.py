from dearpygui import dearpygui as dpg
from zosedit.dataset import Dataset
from zosedit.constants import tempdir
from pathlib import Path


class Tab:

    def __init__(self, path: Path, id: int, dataset_metadata: Dataset):
        self.local_path = path
        self.id = id
        self.dataset_metadata = dataset_metadata
        self.dirty = False

    def mark_dirty(self):
        dpg.configure_item(self.id, label=self.dataset_metadata.name + '*')
        self.dirty = True

    def __repr__(self):
        return f"Tab({self.local_path}, {self.id}, {dpg.get_item_rect_min(self.id)})"


class Editor:

    def __init__(self, root):
        self.root = root
        self.tabs = []

    def build(self):
        with dpg.tab_bar(tag='editor_tab_bar', reorderable=True, callback=self.on_tab_changed):
            id = dpg.add_tab(label='...', closable=False)
            self.empty_tab = Tab(None, id, None)
            self.tabs.append(self.empty_tab)
        dpg.add_input_text(tag="editor", parent='win_editor', show=False,
                               multiline=True, width=-1, height=-1, callback=self.on_editor_changed)

        with dpg.handler_registry():
            dpg.add_key_press_handler(dpg.mvKey_N, callback=self.new_file_keybind)
            dpg.add_key_press_handler(dpg.mvKey_S, callback=self.save_keybind)
            dpg.add_key_press_handler(dpg.mvKey_W, callback=self.close_tab_keybind)
            dpg.add_key_press_handler(dpg.mvKey_Tab, callback=self.switch_tab_keybind)

    def hide(self):
        dpg.hide_item('editor')
        for tab in self.tabs:
            if tab is not self.empty_tab:
                dpg.hide_item(tab.id)

        self.tabs = [self.empty_tab]

    def on_editor_changed(self):
        self.get_current_tab().mark_dirty()

    def on_tab_changed(self):
        self.update_internal_state()
        tab = dpg.get_value('editor_tab_bar')
        tab = self.get_tab_by_id(tab)
        if tab:
            self.switch_to_tab(tab)

    def new_file(self):
        # Callback for creating a new file
        def create_file():
            dataset_name = dpg.get_value('new_file_dataset_input')
            # record_length = dpg.get_value('new_file_record_length')
            type_ = dpg.get_value('new_file_type')
            type_ = 'PO' if type_ == 'PDS' else 'PS'

            dataset = Dataset(dataset_name)
            dataset.record_length = 80 # HACK
            dataset.type = type_
            local_path = Path(tempdir, dataset_name)
            local_path.write_text('')
            if type_ == 'PO':
                self.root.ftp.mkdir(dataset)
            else:

                self.open_file(local_path, dataset, new=True)
            dpg.delete_item('new_file_dialog')

        # Close existing dialog
        if dpg.does_item_exist('new_file_dialog'):
            dpg.delete_item('new_file_dialog')

        # Create new dialog
        w, h = 400, 100
        with dpg.window(tag='new_file_dialog', width=w, height=h, label='New'):
            dpg.add_input_text(hint='Dataset Name', tag='new_file_dataset_input', uppercase=True,
                               on_enter=True, callback=create_file)
            # dpg.add_input_int(label='Record Length', tag='new_file_record_length', default_value=80, min_value=1, max_value=32767, step=0)
            dpg.add_combo(label='Type', items=('Normal', 'PDS'), tag='new_file_type', default_value='Normal')
            with dpg.group(horizontal=True):
                dpg.add_button(label='Create', callback=create_file)
                dpg.add_button(label='Cancel', callback=lambda: dpg.delete_item('new_file_dialog'))

        # Center dialog
        vw, vh = dpg.get_viewport_width(), dpg.get_viewport_height()
        dpg.set_item_pos('new_file_dialog', (vw/2 - w/2, vh/2 - h/2))

    def save_file(self):
        tab = self.get_current_tab()
        if not tab:
            return
        if tab.dirty:
            tab.local_path.write_text(dpg.get_value('editor'), newline='')
            if not self.root.ftp.upload(tab.local_path, tab.dataset_metadata):
                return
            tab.dirty = False
            dpg.configure_item(tab.id, label=tab.dataset_metadata.name)
            current_search = dpg.get_value('explorer_search_input')
            if current_search and current_search in tab.dataset_metadata.name:
                self.root.explorer.refresh()

    def open_file(self, local_path: Path, dataset: Dataset, new=False):
        print(f'Opening {local_path}')
        if not self.get_tab_by_name(local_path):
            self.add_tab(local_path, dataset)

        self.switch_to_tab(self.get_tab_by_name(local_path))
        if new:
            self.get_current_tab().mark_dirty()

    def add_tab(self, local_path, dataset: Dataset):
        id = dpg.add_tab(label=local_path.name, closable=True, parent='editor_tab_bar')
        tab = Tab(local_path, id, dataset)
        self.tabs.append(tab)
        self.switch_to_tab(tab)

    def switch_to_tab(self, tab: Tab):
        dpg.set_value('editor_tab_bar', tab.id)
        if tab is self.empty_tab:
            dpg.hide_item('editor')
            return
        content = open(tab.local_path).read()
        lines = [line.rstrip() for line in content.split('\n')]
        dpg.set_value('editor', '\n'.join(lines))
        dpg.show_item(tab.id)
        dpg.show_item('editor')

    def cycle_tabs(self, direction: int):
        self.update_internal_state()
        tabs = [tab.id for tab in self.tabs]
        tab = dpg.get_value('editor_tab_bar')
        index = tabs.index(tab) + direction
        index = index % len(tabs)
        tab = tabs[index]
        dpg.set_value('editor_tab_bar', tab)

    def get_current_tab(self) -> Tab:
        tab = dpg.get_value('editor_tab_bar')
        return self.get_tab_by_id(tab)

    def get_tab_by_name(self, path: Path):
        matching_tabs = [tab for tab in self.tabs if tab.local_path == path]
        if len(matching_tabs) == 0:
            return None
        return matching_tabs.pop()

    def get_tab_by_id(self, id: int):
        matching_tabs = [tab for tab in self.tabs if tab.id == id]
        if len(matching_tabs) == 0:
            return None
        return matching_tabs.pop()

    def save_keybind(self):
        if dpg.is_key_down(dpg.mvKey_Control):
            self.save_file()

    def switch_tab_keybind(self):
        if dpg.is_key_down(dpg.mvKey_Control):
            self.cycle_tabs(-1 if dpg.is_key_down(dpg.mvKey_Shift) else 1)

    def new_file_keybind(self):
        if dpg.is_key_down(dpg.mvKey_Control):
            self.new_file()

    def close_tab_keybind(self):
        if dpg.is_key_down(dpg.mvKey_Control):
            tab = self.get_current_tab()
            if tab is self.empty_tab:
                return
            self.delete_tab(tab)

    def delete_tab(self, tab: Tab):
        dpg.delete_item(tab.id)
        self.tabs.remove(tab)
        if tab.local_path:
            tab.local_path.unlink()

    def update_internal_state(self):
        try:
            children = dpg.get_item_children('editor_tab_bar')[1]
            _tabs = [tab for tab in self.tabs if tab.id in children]
            for tab in _tabs:
                if not dpg.is_item_visible(tab.id):
                    self.delete_tab(tab)
            _tabs.sort(key=lambda x: dpg.get_item_rect_min(x.id)[0])
            self.tabs = _tabs
        except Exception as e:
            print('Error updating internal state:', e)



