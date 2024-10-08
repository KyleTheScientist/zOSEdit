import re
import ebcdic
import colorama
from dearpygui import dearpygui as dpg
from zosedit.models import Dataset, Job, Spool
from zosedit.constants import tempdir
from zosedit.zftp import zFTP
from zosedit.gui.dialog import dialog
from pathlib import Path
from datetime import datetime

colorama.init()


class Tab:

    def __init__(self, *, ftp: zFTP = None, dataset: Dataset = None, job: Job = None):
        self.ftp = ftp
        self.dataset = dataset
        self.job = job
        self.dirty = False
        self.uuid = None
        self.label = None
        self._line_height = dpg.get_text_size('')[1] + 18

        if dataset:
            self.build_dataset_tab()
        elif job:
            self.build_job_tab()
        else:
            self.uuid = dpg.add_tab(label='   ', closable=False, parent='editor_tab_bar')

    def build_dataset_tab(self):
        dataset: Dataset = self.dataset

        # Clear existing tab / create new tab
        if self.uuid:
            for child in dpg.get_item_children(self.uuid)[1]:
                dpg.delete_item(child)
        else:
            self.uuid = dpg.add_tab(label=dataset.name, closable=True, parent='editor_tab_bar')
            self.label = dataset.name

        # Setup tab
        dpg.bind_item_theme(self.uuid, 'dataset_tab_theme')
        dpg.set_value('editor_tab_bar', self.uuid)

        with dpg.group(horizontal=True, parent=self.uuid):
            dpg.add_button(label='Refresh', callback=self.build_dataset_tab)
            dpg.add_button(label='Submit', callback=self._submit_job)

        with dpg.child_window(parent=self.uuid, height=self._line_height, border=False, horizontal_scrollbar=True):
            dpg.add_text(str(dataset))

        # Get file content
        if dataset.new:
            self.mark_dirty()
            text = ''
        else:
            status = dpg.add_text('Downloading...', parent=self.uuid)
            self.ftp.download(dataset)
            dpg.delete_item(status)
            content = dataset.local_path.read_text(errors='replace')
            lines = [line.rstrip() for line in content.split('\n')]
            text = '\n'.join(lines)

        # Create editor
        self.editor = dpg.add_input_text(
            parent=self.uuid,
            default_value=text,
            multiline=True,
            width=-1,
            height=-1,
            callback=self.mark_dirty,
            tab_input=True,
            user_data=self)

    def build_job_tab(self):
        label = f'{self.job.id} ({self.job.name})'

        # Clear existing tab / create new tab
        if self.uuid:
            for child in dpg.get_item_children(self.uuid)[1]:
                dpg.delete_item(child)
        else:
            self.uuid = dpg.add_tab(label=label, closable=True, parent='editor_tab_bar')
            self.label = label

        # Setup tab
        dpg.bind_item_theme(self.uuid, 'job_tab_theme')
        dpg.set_value('editor_tab_bar', self.uuid)

        with dpg.group(horizontal=True, parent=self.uuid):
            dpg.add_button(label='Refresh', callback=self.build_job_tab)

        # Info/status
        with dpg.child_window(parent=self.uuid, height=self._line_height, border=False, horizontal_scrollbar=True):
            dpg.add_text(str(self.job))
        status = dpg.add_text('Downloading spool...', parent=self.uuid)


        # Create spool dropdowns
        self.spool_headers = []
        for spool in self.ftp.list_spools(self.job):
            header = dpg.add_collapsing_header(before=status, label=spool.ddname, parent=self.uuid)
            self.spool_headers.append(header)
            with dpg.item_handler_registry() as reg:
                dpg.add_item_toggled_open_handler(callback=self._populate_spool, user_data=(header,spool))
            dpg.bind_item_handler_registry(header, reg)
        dpg.delete_item(status)

    def _submit_job(self, sender, data):
        self.ftp.submit_job(self.dataset, False)

    def _populate_spool(self, sender, data, user_data):
        header, spool = user_data
        # for h in self.spool_headers:
        #     dpg.set_value(h, h == header)

        if dpg.get_item_children(header)[1]:  # Already populated
            return

        # Info/status
        with dpg.child_window(parent=header, height=self._line_height, border=False, horizontal_scrollbar=True):
            dpg.add_text(str(spool), indent=10)
        status = dpg.add_text('Downloading spool output...', parent=header, indent=10)
        if not self.ftp.download_spool(spool):
            dpg.set_value(status, 'Download failed')
            dpg.configure_item(status, color=(255, 255, 0))
            return
        dpg.delete_item(status)

        # Display spool
        text = spool.local_path.read_text()
        tw, th = dpg.get_text_size(text)

        with dpg.child_window(parent=header,
                              horizontal_scrollbar=True, border=False) as window:
            input_field = dpg.add_input_text(multiline=True,
                                             width=tw + 20,
                                             height=th + 20,
                                             default_value=text,
                                             readonly=True,)
            dpg.bind_item_theme(input_field, 'spool_input_theme')
        self.resize_spool_window(None, None, (header, window, input_field))

        # Resize window handler
        with dpg.item_handler_registry() as reg:
            dpg.add_item_toggled_open_handler(callback=self.resize_spool_window, user_data=(header, window, input_field))
        dpg.bind_item_handler_registry(header, reg)

    def resize_spool_window(self, sender, data, user_data):
        print(f'resize_spool_window {datetime.now()}')
        header, window, input_field = user_data
        width = dpg.get_item_rect_size(header)[0]
        text = dpg.get_value(input_field)
        tw, th = dpg.get_text_size(text)
        w = min(tw + 34, width - 15)
        h = min(th + 34, dpg.get_viewport_height() - 220)
        dpg.configure_item(window, width=w, height=h)

    def mark_dirty(self):
        dpg.configure_item(self.uuid, label=self.dataset.name + '*')
        self.dirty = True

    def mark_clean(self):
        dpg.configure_item(self.uuid, label=self.dataset.name)
        self.dirty = False
        self.dataset.new = False

    def __repr__(self):
        return f"Tab({self.label} - {self.uuid})"


class Editor:

    def __init__(self, root):
        self.root = root
        self.tabs = []

    def build(self):
        dpg.add_tab_bar(tag='editor_tab_bar', reorderable=True, callback=self.on_tab_changed)

        with dpg.theme(tag='job_tab_theme'):
            with dpg.theme_component(dpg.mvTab):
                dpg.add_theme_color(dpg.mvThemeCol_Tab, (40, 70, 50, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, (40, 140, 78, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (30, 130, 68, 255), category=dpg.mvThemeCat_Core)

        with dpg.theme(tag='dataset_tab_theme'):
            with dpg.theme_component(dpg.mvTab):
                dpg.add_theme_color(dpg.mvThemeCol_Tab, (50, 60, 80, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TabActive, (50, 60, 150, 255), category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_TabHovered, (30, 70, 130, 255), category=dpg.mvThemeCat_Core)

        with dpg.theme(tag='spool_input_theme'):
            with dpg.theme_component(dpg.mvInputText):
                dpg.add_theme_style(dpg.mvStyleVar_CellPadding, 0, 0, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0, category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 0, 0, category=dpg.mvThemeCat_Core)



        with dpg.handler_registry():
            dpg.add_key_press_handler(dpg.mvKey_N, callback=self.new_dataset_tab_keybind)
            dpg.add_key_press_handler(dpg.mvKey_S, callback=self.save_keybind)
            dpg.add_key_press_handler(dpg.mvKey_W, callback=self.close_tab_keybind)
            dpg.add_key_press_handler(dpg.mvKey_Tab, callback=self.switch_tab_keybind)

    def reset(self):
        tabs = [tab for tab in self.tabs]
        for tab in tabs:
            self.delete_tab(tab)
        self.tabs = []

    def on_tab_changed(self):
        self.update_internal_state()

    # Jobs
    def open_job(self, job: Job):
        tab = self.get_tab_by_job(job)
        if not tab:
            tab = Tab(ftp=self.root.zftp, job=job)
            self.tabs.append(tab)
        elif tab.dirty:
            self.switch_to_tab(tab)
        else:
            tab.build_job_tab()
        self.switch_to_tab(tab)

    # Files
    def open_file(self, dataset: Dataset):
        tab = self.get_tab_by_dataset(dataset.name)
        if not tab:
            tab = self.new_dataset_tab(dataset)
        elif tab.dirty:
            self.switch_to_tab(tab)
        else:
            tab.build_dataset_tab()
        self.switch_to_tab(tab)
        if dataset.new:
            self.get_current_tab().mark_dirty()

    def new_dataset_tab(self, dataset: Dataset = None) -> Tab:
        if not dataset:
            dataset = Dataset(name='Untitled')
            dataset.new = True
        tab = Tab(ftp=self.root.zftp, dataset=dataset)
        self.tabs.append(tab)
        return tab

    def save_as(self, default_name: str = ''):
        print(f'{colorama.Fore.YELLOW}Save as{colorama.Fore.RESET}')

        # Callback for creating a new file
        def _save_as():
            name = dpg.get_value('save_as_dataset_input')
            member = None
            if match := re.match(r'(.*)\((\w)\)', name):
                name = match.group(1)
                member = match.group(2)

            type_ = dpg.get_value('save_as_type')
            type_ = 'PO' if type_ == 'Partitioned' else 'PS'
            format_ = dpg.get_value('save_as_format')
            format_ = 'FB' if format_ == 'Fixed Width' else 'VB'

            tab = self.get_current_tab()

            dummy = Dataset(
                name=name,
                member=member,
                reclength=dpg.get_value('save_as_record_length'),
                recformat=format_,
                type=type_
            )
            dummy.local_path = Path(tempdir, dummy.name)
            dummy.local_path.write_text('')
            tab.dataset = dummy

            if type_ == 'PO':
                self.root.zftp.mkdir(dummy)
            else:
                self.save_open_file()
                properties = self.root.zftp.list_datasets(f"'{dummy.parent or dummy.name}'").pop().properties()
                properties.update(name=name, member=member)
                tab.dataset = Dataset(**properties)
                tab.mark_clean()
                tab.build_dataset_tab()

            dpg.delete_item('save_as_dialog')

        # Close existing dialog
        if dpg.does_item_exist('save_as_dialog'):
            dpg.delete_item('save_as_dialog')

        def on_switch_format():
            format_ = dpg.get_value('save_as_format')
            label = 'Record Length' if format_ == 'Fixed Width' else 'Max Record Length'
            dpg.configure_item('save_as_record_length', label=label)

        # Create new dialog
        w, h = 500, 200
        with dialog(tag='save_as_dialog', width=w, height=h, label='Save As'):
            dpg.add_input_text(hint='Dataset Name',
                               tag='save_as_dataset_input',
                               width=-1,
                               uppercase=True,
                               on_enter=True,
                               callback=_save_as,
                               default_value=default_name)
            dpg.add_combo(label='Type',
                                 items=('Sequential', 'Partitioned'),
                                 tag='save_as_type',
                                 default_value='Sequential',
                                 width=120)
            dpg.add_combo(label='Record Format',
                                 items=('Fixed Width', 'Variable Width'),
                                 tag='save_as_format',
                                 default_value='Fixed Width',
                                 width=120,
                                 callback=on_switch_format)
            dpg.add_input_int(label='Record Length', tag='save_as_record_length',
                              default_value=80, min_value=1, max_value=32767, step=0,
                              width=120)

            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label='Save', callback=_save_as, width=w / 2 - 13)
                dpg.add_button(label='Cancel', callback=lambda: dpg.delete_item('save_as_dialog'), width=w / 2 - 12)

            dpg.focus_item('save_as_dataset_input')

    def save_open_file(self):
        tab = self.get_current_tab()
        if not tab or not tab.dataset:
            return

        if not tab.dirty:
            return

        if tab.dataset.new:
            self.save_as()
            return

        print(f'{colorama.Fore.YELLOW}Uploading{colorama.Fore.RESET}')

        text: str = dpg.get_value(tab.editor)
        result = []
        pad_to = tab.dataset.reclength if tab.dataset.recformat == 'FB' else tab.dataset.reclength - 4
        for line in text.split('\n'):
            result.append(line.ljust(pad_to))
        text = ''.join(result)

        tab.dataset.local_path.write_bytes(text.encode('cp1047'))

        if not self.root.zftp.upload(tab.dataset):
            return
        tab.mark_clean()

        current_search = dpg.get_value('explorer_dataset_input')
        if current_search and current_search in tab.dataset.name:
            self.root.explorer.refresh_datasets()

    # Tabs
    def switch_to_tab(self, tab: Tab):
        dpg.set_value('editor_tab_bar', tab.uuid)

    def cycle_tabs(self, direction: int):
        self.update_internal_state()
        tabs = [tab.uuid for tab in self.tabs]
        tab = dpg.get_value('editor_tab_bar')
        index = tabs.index(tab) + direction
        index = index % len(tabs)
        tab = tabs[index]
        dpg.set_value('editor_tab_bar', tab)

    def get_current_tab(self) -> Tab:
        tab = dpg.get_value('editor_tab_bar')
        return self.get_tab_by_id(tab)

    def get_tab_by_job(self, job: Job) -> Tab:
        matching_tabs = [tab for tab in self.tabs if tab.job and tab.job.id == job.id]
        if len(matching_tabs) == 0:
            return None
        return matching_tabs.pop()

    def get_tab_by_dataset(self, dataset: str) -> Tab:
        matching_tabs = [tab for tab in self.tabs if tab.dataset and tab.dataset.name == dataset]
        if len(matching_tabs) == 0:
            return None
        return matching_tabs.pop()

    def get_tab_by_id(self, id: int):
        matching_tabs = [tab for tab in self.tabs if tab.uuid == id]
        if len(matching_tabs) == 0:
            return None
        return matching_tabs.pop()

    def save_keybind(self):
        if dpg.is_key_down(dpg.mvKey_Control):
            self.save_open_file()

    def switch_tab_keybind(self):
        if dpg.is_key_down(dpg.mvKey_Control):
            self.cycle_tabs(-1 if dpg.is_key_down(dpg.mvKey_Shift) else 1)

    def new_dataset_tab_keybind(self):
        if dpg.is_key_down(dpg.mvKey_Control):
            self.new_dataset_tab()

    def close_tab_keybind(self):
        if dpg.is_key_down(dpg.mvKey_Control):
            tab = self.get_current_tab()
            if tab:
                self.delete_tab(tab)

    def delete_tab(self, tab: Tab):
        dpg.delete_item(tab.uuid)
        self.tabs.remove(tab)

    def close_tab_by_dataset(self, dataset: Dataset):
        tab = self.get_tab_by_dataset(dataset.name)
        if tab:
            self.delete_tab(tab)

    def update_internal_state(self):
        try:
            children = dpg.get_item_children('editor_tab_bar')[1]
            _tabs = [tab for tab in self.tabs if tab.uuid in children]
            for tab in _tabs:
                if not dpg.is_item_visible(tab.uuid):
                    self.delete_tab(tab)
            _tabs.sort(key=lambda x: dpg.get_item_rect_min(x.uuid)[0])
            self.tabs = _tabs
        except Exception:
            pass
