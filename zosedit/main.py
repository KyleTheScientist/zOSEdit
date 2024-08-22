from dearpygui import dearpygui as dpg
import zosedit.gui.explorer as explorer
import zosedit.gui.editor as editor
from zosedit.gui.dialog import dialog

from zosedit.constants import tempdir
from zosedit.zftp import zFTP

import platform

if platform.system() == 'Windows':
    from os import startfile

class Root:

    def __init__(self):
        self.zftp = None
        self.explorer = explorer.Explorer(self)
        self.editor = editor.Editor(self)
        self.zftp = zFTP(self)

    def start(self):
        dpg.create_context()
        dpg.create_viewport(title='z/OS Edit', resizable=True)

        with dpg.window(label="Main", tag='win_main') as main:
            with dpg.menu_bar():
                with dpg.menu(label="File", tag='file_menu'):
                    dpg.add_menu_item(label="New", shortcut="Ctrl+N", callback=self.editor.new_file)
                    dpg.add_menu_item(label="Save", shortcut="Ctrl+S", callback=self.editor.save_open_file)
                    if platform.system() == 'Windows':
                        dpg.add_menu_item(label="Open Data Directory", callback=self.open_data_directory)
                with dpg.menu(label="Run", tag='run_menu'):
                    dpg.add_menu_item(label="Command", shortcut="F1", callback=self.zftp.operator_command_prompt)
                    # dpg.add_menu_item(label="Submit", shortcut="F5", callback=self.editor.submit_open_file)
                with dpg.menu(label="Session", tag='session_menu'):
                    dpg.add_menu_item(label="Login", callback=self.login)
                    dpg.add_menu_item(label="Logout", callback=self.logout)

            with dpg.handler_registry():
                dpg.add_key_press_handler(dpg.mvKey_F1, callback=self.zftp.operator_command_prompt)

            width = dpg.get_viewport_width()
            with dpg.group(horizontal=True):
                with dpg.child_window(label="Explorer", width=width/4, height=-1, tag='win_explorer'):
                    self.explorer.build()

                with dpg.child_window(label="Editor", menubar=False, tag='win_editor',
                                      width=-1, height=-1, horizontal_scrollbar=True):
                    self.editor.build()

        self.login()

        dpg.set_primary_window(main, True)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

    def logout(self):
        self.zftp.quit()
        self.explorer.reset()
        self.editor.reset()
        self.login()

    def login(self):
        def _login():
            host = dpg.get_value('settings_host_input')
            username = dpg.get_value('settings_username_input')
            password = dpg.get_value('settings_password_input')
            if self.zftp:
                dpg.set_value('login_status', 'Closing existing connection...')
                self.zftp.quit()

            dpg.set_value('login_status', f'Connecting to {host}...')
            try:
                self.zftp.connect(host, username, password)
            except Exception as e:
                dpg.set_value('login_status', f'Error connecting: {e}')
                return

            dpg.delete_item('login_dialog')
            dpg.set_value('explorer_dataset_input', username)
            self.explorer.refresh_datasets()

        w, h = 420, 150
        # Create new dialog
        with dialog(tag='login_dialog', label='Login', width=w, height=h):
            kwargs = {'on_enter': True, 'callback': _login, 'width': -1}
            dpg.add_input_text(hint='Host', tag='settings_host_input', default_value='QAZOS205', **kwargs)
            dpg.add_input_text(hint='Username', tag='settings_username_input', uppercase=True, **kwargs)
            dpg.add_input_text(hint='Password', tag='settings_password_input', password=True, uppercase=True, **kwargs)
            with dpg.group(horizontal=True):
                bw = w // 2 - 12
                dpg.add_button(label='Login', callback=_login, width=bw)
                dpg.add_button(label='Cancel', callback=lambda: dpg.delete_item('login_dialog'), width=bw -1)
            dpg.add_text('', tag='login_status')
            dpg.focus_item('settings_username_input')


    def open_data_directory(self):
        startfile(tempdir)

root = Root()

def main():
    root.start()

if __name__ == '__main__':
    main()
