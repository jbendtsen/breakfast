from tkinter import messagebox
import threading
import queue
import ctypes
import time

EDIT_TAB   = 0
FILTER_TAB = 1
MACRO_TAB  = 2

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
			data.append(self.queue.get(timeout=timeout))

		return data

	def run(self) :
		cancel_btn = self.tab.frame[MACRO_TAB].cancel_btn
		cancel_btn.config(state="normal")
		try:
			exec(self.tab.macro)
		except Exception as e:
			if e is not SystemExit:
				messagebox.showerror("Error", "{0}".format(e))
		finally:
			cancel_btn.config(state="disabled")
