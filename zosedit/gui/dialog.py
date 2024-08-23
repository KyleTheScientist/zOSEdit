from dearpygui import dearpygui as dpg
from contextlib import contextmanager

@contextmanager
def dialog(*, tag=None, popup=False, modal=True, width=0, height=0, **kwargs):
    if tag and dpg.does_item_exist(tag):
        dpg.delete_item(tag)
    window = dpg.add_window(tag=tag, popup=popup, modal=modal, width=width, height=height, **kwargs)
    dpg.push_container_stack(window)
    yield
    dpg.pop_container_stack()
    w, h = dpg.get_item_rect_size(window)
    w = width or w
    h = height or h
    vw, vh = dpg.get_viewport_width(), dpg.get_viewport_height()
    dpg.set_item_pos(window, (vw/2-w/2, vh/2-h/2))


