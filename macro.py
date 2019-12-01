import tkinter as tk
from tkinter import messagebox

import threading
import queue
import ctypes
import time

import struct

EDIT_TAB   = 0
FILTER_TAB = 1
MACRO_TAB  = 2

class BindingDialog:
	def __init__(self, tab) :
		self.tab = tab
		self.master = self.tab.main.master
		self.top = tk.Toplevel(self.master)
		self.keys = []

		self.label = tk.Label(self.top, text="Press a key to bind this macro to")
		self.label.pack()

		self.existing_ent = tk.Entry(self.top, width=32)
		if self.tab.binding is not None:
			self.existing_ent.insert("end", "+".join(self.tab.binding))

		self.existing_ent.config(state="disabled")
		self.existing_ent.pack()

		self.clear_btn = tk.Button(self.top, text="Clear", command=self.clear)
		self.clear_btn.pack(side="bottom", padx=6, pady=4)

		self.top.title("Bind Macro ({0})".format(self.tab.name))
		self.top.geometry("250x100")
		self.top.protocol("WM_DELETE_WINDOW", self.close)
		self.top.bind("<Key>", self.key_down)
		self.top.bind("<KeyRelease>", self.key_up)

	def key_down(self, e) :
		self.keys.append(e.keysym)

	def key_up(self, e) :
		self.tab.binding = self.keys
		self.close()

	def clear(self) :
		self.tab.binding = None
		self.close()

	def close(self) :
		self.tab.main.binding_dlg = None
		self.top.destroy()

class Macro(threading.Thread) :
	def __init__(self, main, tab) :
		super(Macro, self).__init__()
		self.main = main
		self.tab = tab
		self.queue = queue.Queue()

	def kill(self) :
		th_id = -1
		for id, thread in threading._active.items() :
			if thread == self:
				th_id = id
				break

		if th_id >= 0:
			ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(th_id), ctypes.py_object(SystemExit))

	def write_bytes(self, *byte_tuple) :
		self.main.comms.send(bytes(byte_tuple))

	def write(self, data) :
		self.main.comms.send(data)

	def read(self, count, timeout=None) :
		data = bytearray([])
		while (len(data) < count) :
			try:
				data.append(self.queue.get(timeout=timeout))
			except queue.Empty:
				return None

		return data

	def run(self) :
		cancel_btn = self.tab.cancel_btn
		cancel_btn.config(state="normal")
		try:
			exec(self.tab.macro)
		except Exception as e:
			if e is not SystemExit:
				messagebox.showerror("Error", "{0}".format(e))
		finally:
			cancel_btn.config(state="disabled")
