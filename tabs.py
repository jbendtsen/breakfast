import tkinter as tk
from tkinter import messagebox

import subprocess
import threading

import macro
import utils

EDIT = 0
FILTER = 1
MACRO = 2

modeNames = [
	"Editing",
	"Filtered",
	"Macro"
]

class Tab:
	def __init__(self, gui, idx) :
		self.main = gui
		self.name = "Tab {0}".format(idx+1)
		self.mode = EDIT

		self.frame = [
			self.init_frame(self.main.master, EDIT),
			self.init_frame(self.main.master, FILTER),
			self.init_frame(self.main.master, MACRO)
		]

		self.data = bytearray([])
		self.filter = ""
		self.flt_output = None
		self.binding = None
		self.macro = ""
		self.macro_thread = None
		self.macro_event = threading.Event()

	def init_frame(self, root, mode) :
		head_label = ""
		recv_label = ""
		if mode == EDIT:
			recv_label = "Receiving"
		elif mode == FILTER:
			head_label = "Filter"
			recv_label = "Receiving"
		elif mode == MACRO:
			head_label = "Binding"
			recv_label = "Python Code"

		frame = tk.Frame(root)
		frame.grid_rowconfigure(3, weight=1)
		frame.grid_columnconfigure(1, weight=1)

		if mode == FILTER:
			self.filter_lbl = tk.Label(frame, text=head_label)
			self.filter_lbl.grid(row=0, columnspan=7, sticky="w")

			self.filter_var = tk.StringVar()
			self.filter_var.trace("w", self.update_heading)

			self.filter_ent = tk.Entry(frame, width=200, textvariable=self.filter_var, name="filter")
			#self.filter_ent.bind("<Return>", (lambda event: self.update()))
			self.filter_ent.grid(row=1, columnspan=7)

		frame.recv_lbl = tk.Label(frame, text=recv_label)
		frame.recv_lbl.grid(row=2, columnspan=6, sticky="w")

		frame.recv = tk.Text(frame, width=200, height=100)
		frame.recv.bind("<Control-Key>", self.main.key_down)
		frame.recv.bind("<FocusOut>", lambda event: self.update_model())
		frame.recv.grid(row=3, columnspan=7)

		if mode == EDIT:
			self.reply_btn = tk.Button(frame, text="Reply", command=self.reply)
			self.clear_btn = tk.Button(frame, text="Clear", command=self.clear_data)
			self.reply_btn.grid(row=4, column=4)
			self.clear_btn.grid(row=4, column=5, columnspan=2)
		elif mode == FILTER:
			self.overwrite_btn = tk.Button(frame, text="Overwrite", command=self.overwrite_data)
			self.overwrite_btn.grid(row=4, column=4)
		elif mode == MACRO:
			self.binding_btn = tk.Button(frame, text="Binding", command=self.prompt_binding)
			self.action_btn = tk.Button(frame, text="Execute", command=self.run_macro)
			self.cancel_btn = tk.Button(frame, text="Cancel", state="disabled", command=self.cancel_macro)
			self.binding_btn.grid(row=4, column=0)
			self.action_btn.grid(row=4, column=4)
			self.cancel_btn.grid(row=4, column=5, columnspan=2)

		return frame

	def mode_name(self) :
		if self.mode >= EDIT and self.mode <= MACRO:
			return modeNames[self.mode]

		# shouldn't get here
		return self.mode

	def append_byte(self, byte) :
		self.data.append(byte)
		if self.macro_running():
			self.macro_thread.queue.put(byte)

		if self.mode == EDIT:
			self.frame[EDIT].recv.insert("end", "{0:02x} ".format(byte))
		elif self.mode == FILTER and len(self.filter) == 0:
			text = self.frame[FILTER].recv
			text.config(state="normal")
			text.insert("end", bytes([byte]).decode('cp437'))
			text.config(state="disabled")

	def update_model(self) :
		if self.mode == FILTER:
			return

		content = self.frame[self.mode].recv.get("1.0", "end")
		if self.mode == EDIT:
			self.data = utils.str2ba(content)
		elif self.mode == MACRO:
			self.macro = content

	def reply(self) :
		self.update_model()
		self.main.comms.send(self.data)

	def clear_data(self) :
		self.frame[EDIT].recv.delete("1.0", "end")
		self.data = []

	def set_data(self, data) :
		self.frame[EDIT].recv.delete("1.0", "end")
		self.data = data
		self.frame[EDIT].recv.insert("end", utils.ba2str(self.data))

	def overwrite_data(self) :
		if self.mode != FILTER:
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
		if mode == EDIT:
			text = utils.ba2str(self.data)

		elif mode == FILTER:
			text = self.run_filter()
			editing = "disabled"

		elif mode == MACRO:
			text = self.macro

		frame.recv.insert("end", text)
		frame.recv.config(state=editing)
