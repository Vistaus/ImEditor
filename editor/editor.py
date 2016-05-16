# -*- coding: utf-8 -*-
#!/usr/bin/python3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from PIL import Image
from os import path

from interface import dialog
from filters import base
from editor.image import ImageObject
from editor.tools import get_coords, get_middle_mouse, get_infos
from editor.draw import draw_point, draw_shape

def img_open(func):
    def inner(self, *args, **kwargs):
        if len(self.images) > 0:
            return func(self, *args, **kwargs)
    return inner

class Editor(object):
    def __init__(self):
        super(Editor, self).__init__()
        self.images = list()
        self.MAX_HIST = 10

        self.task = 'select'
        self.selection = list()
        self.selected_img = None

    def set_win(self, win):
        self.win = win

    @img_open
    def close_image(self, index):
        self.images[index].close_all_img()
        self.images = self.images[:index] + self.images[index+1:]
        self.select(None, None)
        self.task = 'select'
        self.win.root.set_cursor(self.win.default_cursor)

    def add_image(self, *args):
        self.images.append(ImageObject(*args))

    def get_img(self):
        page_num = self.win.notebook.get_current_page()
        img = self.images[page_num].get_current_img()
        return img

    @img_open
    def apply_filter(self, action, parameter, func, value=None):
        func = eval(func)
        img = self.get_img()
        if value is None:
            new_img = func(img)
        else:
            new_img = func(img, value)
        self.do_change(new_img)

    def do_change(self, img):
        page_num = self.win.notebook.get_current_page()
        self.win.update_image(img)
        self.images[page_num].forget_img()
        self.images[page_num].add_img(img)
        self.images[page_num].increment_index()
        self.images[page_num].set_saved(False)
        if self.images[page_num].get_n_img() > self.MAX_HIST:
            self.images[page_num].remove_first_img()
            self.images[page_num].decrement_index()

    @img_open
    def filter_with_params(self, action, parameter, params):
        func = params[0]
        title = params[1]
        limits = params[2]
        params_dialog = dialog.params_dialog(self.win, title, limits)
        value = params_dialog.get_values()
        if value is not None:
            self.apply_filter(None, None, func, value)

    @img_open
    def history(self, action, parameter, num):
        page_num = self.win.notebook.get_current_page()
        if self.images[page_num].get_n_img() >= 2:
            index_img = self.images[page_num].get_index()
            if num == -1: # Undo:
                if index_img >= 1:
                    self.images[page_num].decrement_index()
                    img = self.images[page_num].get_current_img()
                    self.win.update_image(img)
            else: # Redo:
                if index_img + 1 < self.images[page_num].get_n_img():
                    self.images[page_num].increment_index()
                    img = self.images[page_num].get_current_img()
                    self.win.update_image(img)

    @img_open
    def select(self, action, parameter):
        if self.task == 'paste':
            page_num = self.win.notebook.get_current_page()
            tmp_img = self.images[page_num].get_tmp_img()
            if tmp_img is not None:
                self.do_change(tmp_img)
                self.images[page_num].set_tmp_img(None)
        if self.task != 'select':
            self.win.root.set_cursor(self.win.default_cursor)
            self.task = 'select'

    @img_open
    def draw(self, action, parameter):
        if self.task != 'draw-brush':
            self.task = 'draw-brush'
            self.win.root.set_cursor(self.win.draw_cursor)

    def get_vars(self, mouse_coords, is_tmp=False):
        """Return required variables."""
        page_num = self.win.notebook.get_current_page()
        if is_tmp:
            img = self.images[page_num].get_tmp_img().copy()
        else:
            img = self.get_img().copy()
        tab = self.win.notebook.get_nth_page(page_num)
        x_mouse, y_mouse = get_coords(img, tab.get_allocation(), mouse_coords)
        return [x_mouse, y_mouse], page_num, img

    def press_task(self, widget, event):
        mouse_coords, page_num, img = self.get_vars([event.x, event.y])
        if self.task == 'select':
            self.selection = mouse_coords
            self.win.update_image(img)
        elif self.task == 'draw-brush':
            self.move_task(None, event)
        elif self.task == 'paste' and self.selected_img is not None:
            self.move_task(None, event)

    def move_task(self, widget, event):
        mouse_coords, page_num, img = self.get_vars([event.x, event.y], True)
        if self.task == 'select':
            draw_shape(img, 'rectangle', xy=[self.selection[0], self.selection[1], mouse_coords[0], mouse_coords[1]], outline='black')
            self.win.update_image(img)
        elif self.task == 'draw-brush':
            draw_point(img, mouse_coords)
            self.set_tmp_img(img)
        elif self.task == 'paste':
            self.paste(None, None, mouse_coords=mouse_coords)

    def release_task(self, widget, event):
        mouse_coords, page_num, img = self.get_vars([event.x, event.y], True)
        if self.task == 'select':
            self.selection.extend(mouse_coords)
        elif self.task == 'draw-brush':
            self.images[page_num].set_tmp_img(None)
            self.do_change(img)

    def set_tmp_img(self, img):
        self.win.update_image(img)
        page_num = self.win.notebook.get_current_page()
        self.images[page_num].set_tmp_img(img)

    @img_open
    def copy(self, action, parameter):
        if self.selection != list():
            img = self.get_img()
            self.selected_img = img.crop(tuple(self.selection))

    @img_open
    def paste(self, action, parameter, mouse_coords=None):
        if self.selected_img is not None:
            if self.task != 'paste':  # ctrl + V:
                self.task = 'paste'
                self.win.root.set_cursor(self.win.move_cursor)
                x, y = 0, 0
            else:
                x, y = get_middle_mouse(self.selected_img.size, mouse_coords)
            new_img = self.get_img().copy()
            new_img.paste(self.selected_img, (x, y))
            self.set_tmp_img(new_img)

    @img_open
    def cut(self, action, parameter):
        if self.selection != list():
            self.copy(None, None)
            blank_img = Image.new('RGB', self.selected_img.size, 'white')
            img = self.get_img().copy()
            img.paste(blank_img, tuple(self.selection[:2]))
            self.do_change(img)

    @img_open
    def file_save(self, action, parameter):
        page_num = self.win.notebook.get_current_page()
        if self.images[page_num].get_is_new_image():
            self.file_save_as(None, None)
        else:
            img = self.images[page_num].get_current_img()
            self.images[page_num].set_saved(True)
            img.save(self.images[page_num].get_filename())

    @img_open
    def file_save_as(self, action, parameter):
        filename = dialog.file_dialog(self.win, 'save')
        if filename is not None:
            page_num = self.win.notebook.get_current_page()
            img = self.images[page_num].get_current_img()
            img.save(filename)
            self.images[page_num].set_filename(filename)
            page_num = self.win.notebook.get_current_page()
            self.win.notebook.get_nth_page(page_num).get_tab_label().set_label(path.basename(filename))
            self.images[page_num].set_saved(True)

    @img_open
    def properties(self, action, parameter):
        page_num = self.win.notebook.get_current_page()
        img_infos = get_infos(self.images[page_num])
        dialog_infos = dialog.info_dialog(self.win, 'Propriétés de l\'image', img_infos)
