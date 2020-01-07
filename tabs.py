import tkinter as tk
from tkinter import messagebox

import subprocess
import threading

import macro
import utils

DATA = 0
MACRO = 1

modeNames = [
	"Data",
	"Macro"
]

class Tab:
	def __init__(self, gui, idx) :
		self.main = gui
		self.name = "Tab {0}".format(idx+1)
		self.mode = DATA

		self.frame = [
			self.init_frame(self.main.master, DATA),
			self.init_frame(self.main.master, MACRO)
		]

		self.data = bytearray([])
		self.filter = ""
		self.flt_output = None
		self.is_filtered = False
		self.binding = None
		self.macro = ""
		self.macro_thread = None

	def init_frame(self, root, mode) :
		head_label = ""
		recv_label = ""
		if mode == DATA:
			head_label = "  Filter  "
			recv_label = "Receiving"
		elif mode == MACRO:
			head_label = "Binding"
			recv_label = "Python Code"

		frame = tk.Frame(root)
		frame.grid_rowconfigure(3, weight=1)
		frame.grid_columnconfigure(2, weight=1)

		if mode == DATA:
			self.flt_switch = tk.IntVar();
			self.flt_switch.trace("w", self.toggle_filter)

			self.filter_cb = tk.Checkbutton(frame, text=head_label, variable=self.flt_switch)
			self.filter_cb.grid(row=0, column=0)

			self.filter_var = tk.StringVar()
			self.filter_var.trace("w", self.update_heading)

			self.filter_ent = tk.Entry(frame, width=200, textvariable=self.filter_var, name="filter")
			self.filter_ent.bind("<Return>", (lambda event: self.update()))
			self.filter_ent.grid(row=0, column=2, columnspan=5)

		frame.recv_lbl = tk.Label(frame, text=recv_label)
		frame.recv_lbl.grid(row=2, column=0, columnspan=7, sticky="w")

		frame.recv = tk.Text(frame, width=200, height=100)
		frame.recv.bind("<Control-Key>", self.main.key_down)
		frame.recv.bind("<FocusOut>", lambda event: self.update_model())
		frame.recv.grid(row=3, column=0, columnspan=7, sticky="w")

		if mode == DATA:
			self.clear_btn = tk.Button(frame, text="Clear", command=self.clear_data)
			self.clear_btn.grid(row=4, column=5, columnspan=2)
		elif mode == MACRO:
			self.binding_btn = tk.Button(frame, text="Binding", command=self.prompt_binding)
			self.action_btn = tk.Button(frame, text="Execute", command=self.run_macro)
			self.cancel_btn = tk.Button(frame, text="Cancel", state="disabled", command=self.cancel_macro)
			self.binding_btn.grid(row=4, column=0)
			self.action_btn.grid(row=4, column=4)
			self.cancel_btn.grid(row=4, column=5, columnspan=2)

		return frame

	def mode_name(self) :
		if self.mode >= DATA and self.mode <= MACRO:
			return modeNames[self.mode]

		# shouldn't get here
		return self.mode

	def append_byte(self, byte) :
		self.data.append(byte)
		if self.macro_running():
			self.macro_thread.queue.put(byte)

		if self.is_filtered and len(self.filter) == 0:
			text = self.frame[DATA].recv
			text.config(state="normal")
			text.insert("end", bytes([byte]).decode('cp437'))
			text.config(state="disabled")
		elif not self.is_filtered:
			self.frame[DATA].recv.insert("end", "{0:02x} ".format(byte))

	def update_model(self) :
		if self.is_filtered and self.mode == DATA:
			return

		content = self.frame[self.mode].recv.get("1.0", "end")
		if self.mode == DATA:
			self.data = utils.str2ba(content)
		elif self.mode == MACRO:
			if content[-1] == '\n':
				content = content[0:-1]

			self.macro = content

	def reply(self) :
		self.update_model()
		self.main.comms.send(self.data)

	def clear_data(self) :
		self.frame[DATA].recv.delete("1.0", "end")
		self.data = bytearray([])

	def set_data(self, data) :
		if not (isinstance(data, bytes) or isinstance(data, bytearray)) :
			return

		if not self.is_filtered:
			self.frame[DATA].recv.delete("1.0", "end")
			try:
				self.frame[DATA].recv.insert("end", utils.ba2str(self.data))
			except e:
				messagebox.showerror("Error", e)

		self.data = bytearray(data)

	def overwrite_data(self) :
		if self.mode != DATA:
			return

		if self.flt_output != None and len(self.flt_output) > 0:
			self.set_data(self.flt_output)

	def prompt_binding(self) :
		if self.main.binding_dlg is not None:
			return

		self.main.binding_dlg = macro.BindingDialog(self)

	def macro_running(self) :
		return self.macro_thread is not None and self.macro_thread.is_alive()

	def run_macro(self) :
		self.update_model()

		if self.macro_running() :
			messagebox.showinfo("Info", "Macro is already running")
			return

		if self.macro is not None and len(self.macro) > 0:
			self.macro_thread = macro.Macro(self.main, self)
			self.macro_thread.start()

	def cancel_macro(self) :
		if self.macro_running() :
			self.macro_thread.kill()

	def init_filter(self, flt, enabled) :
		value = 1 if enabled else 0
		self.filter_var.set(flt)
		self.flt_switch.set(value)

	def toggle_filter(self, *args) :
		self.update_model()
		self.is_filtered = self.flt_switch.get() != 0
		self.update()

	def update_heading(self, *args) :
		self.filter = self.filter_var.get()

	def run_filter(self) :
		text = ""
		cmd = self.filter
		# if a filter was given, use it as a shell command and provide our data to stdin
		if len(cmd) > 0:
			try:
				proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
				proc.stdin.write(self.data)
				proc.stdin.close()

				# To allow for overwriting our data later
				self.flt_output = proc.stdout.read()

				text = self.flt_output.decode('cp437')
				text += "\n" + proc.stderr.read().decode('cp437')

			except (FileNotFoundError, OSError) as e:
				text = "Filter Error: {0}".format(e)
		# otherwise treat our data as straight-up ASCII
		else:
			text = self.data.decode('cp437')

		return text

	def update(self, mode=None) :
		if mode is None:
			mode = self.mode

		frame = self.frame[mode]
		frame.recv.config(state="normal")
		frame.recv.delete("1.0", "end")

		text = ""
		editing = "normal"
		if mode == DATA:
			if self.is_filtered:
				self.filter_ent.grid()
				text = self.run_filter()
				editing = "disabled"
			else:
				self.filter_ent.grid_remove()
				text = utils.ba2str(self.data)

		elif mode == MACRO:
			text = self.macro

		frame.recv.insert("end", text)
		frame.recv.config(state=editing)
