import tkinter as tk
from tkinter import messagebox, filedialog

import sys
import threading

import serial
import comms
import tabs
import utils

dataTypes = [
	"Data", "Results", "Macro"
]

class Breakfast:
	def __init__(self, master, iface) :
		self.master = master
		self.binding_dlg = None

		self.menu = tk.Menu(self.master)

		self.file_menu = tk.Menu(self.menu, tearoff=0)
		self.file_menu.add_command(label="Open", command=self.load)
		self.file_menu.add_command(label="Save", command=self.save)

		self.tab_menu = tk.Menu(self.menu, tearoff=0)

		self.menu.add_cascade(label="File", menu=self.file_menu)
		self.menu.add_cascade(label="Tabs", menu=self.tab_menu)

		self.master.config(menu=self.menu)

		self.keys_held = []
		self.master.bind("<Key>", self.key_down)
		self.master.bind("<KeyRelease>", self.key_up)

		self.tab_strs = tk.StringVar()
		self.tab_strs.trace('w', self.select_tab_str)

		editing_btn = tk.Button(self.master, text=tabs.modeNames[tabs.EDIT], command=lambda: self.switch_mode(tabs.EDIT))
		filtered_btn = tk.Button(self.master, text=tabs.modeNames[tabs.FILTER], command=lambda: self.switch_mode(tabs.FILTER))
		macro_btn = tk.Button(self.master, text=tabs.modeNames[tabs.MACRO], command=lambda: self.switch_mode(tabs.MACRO))

		editing_btn.grid(row=1, column=0)
		filtered_btn.grid(row=1, column=1)
		macro_btn.grid(row=1, column=2, sticky="w")

		self.mode_btns = [editing_btn, filtered_btn, macro_btn]

		self.tab_add_btn = tk.Button(self.master, text="+", command=self.add_tab)
		self.tab_add_btn.grid(row=1, column=4)

		self.tab_del_btn = tk.Button(self.master, text="x", command=self.close_tab)
		self.tab_del_btn.grid(row=1, column=5)

		self.tabs = []
		self.n_created_tabs = 0
		self.cur_tab = 0
		self.add_tab()

		self.prompt_lbl = tk.Label(self.master, text="Command")
		self.prompt_lbl.grid(row=10, columnspan=6, sticky="w")

		self.prompt = tk.Entry(self.master, width=200, name="prompt")
		self.prompt.grid(row=11, columnspan=4)

		self.send_btn = tk.Button(self.master, text="Send", command=self.send)
		self.send_btn.grid(row=11, column=4, columnspan=2)

		self.master.protocol("WM_DELETE_WINDOW", self.close)

		self.refresh()

		self.comms = comms.Comms(self, iface)
		self.comms.start()

	def close(self) :
		if self.comms != None:
			self.comms.close()
			self.comms.join()

		for t in self.tabs:
			if t.macro_running() :
				t.macro_thread.kill()
				t.macro_thread.join()

		self.master.destroy()

	def clear_key(self, key) :
		without = []
		for k in self.keys_held:
			if k != key:
				without.append(k)

		self.keys_held = without

	def key_down(self, e) :
		key = e.keysym
		self.clear_key(key)
		self.keys_held.append(key)

		# attempt to run each macro
		for t in self.tabs:
			if t.binding is None:
				continue

			if set(t.binding) == set(self.keys_held) :
				self.keys_held = []
				t.run_macro()
				return "break"

		shift_held = (e.state & 1) == 1
		ctrl_held = (e.state & 4) == 4

		if ctrl_held:
			if e.keysym == "o":
				self.keys_held = []
				self.load()
				return "break"
			elif e.keysym == "s":
				self.keys_held = []
				self.save()
				return "break"

		wname = str(e.widget).split(".")[-1]  # Thanks Bryan
		if wname == "prompt":
			if key == "Return" and not shift_held:
				self.send()
		elif wname == "filter":
			if key == "Return" and not shift_held:
				self.tabs[self.cur_tab].update()

	def key_up(self, e) :
		# A bit of a hack
		self.keys_held = []

	def refresh_tab_list(self) :
		menu = self.tab_menu
		menu.delete(0, "end")
		for t in self.tabs:
			menu.add_command(label=t.name, command=(lambda value=t.name: self.tab_strs.set(value)))

	def select_tab_str(self, *args) :
		name = self.tab_strs.get()
		idx = 0
		for t in self.tabs:
			if t.name == name:
				self.select_tab(idx)
				return
			idx += 1

		# World's best error handling right here
		print("Could not find " + name)

	def remove_tabframe(self) :
		t = self.tabs[self.cur_tab]
		t.frame[t.mode].grid_remove()

		self.mode_btns[t.mode].config(relief="raised")

	def apply_tabframe(self) :
		t = self.tabs[self.cur_tab]
		t.frame[t.mode].grid(row=2, columnspan=6, rowspan=5)

		self.mode_btns[t.mode].config(relief="sunken")

		self.master.grid_rowconfigure(2, weight=1)
		self.master.grid_columnconfigure(3, weight=1)

		open_mode = "disabled" if t.mode == tabs.FILTER else "normal"
		self.file_menu.entryconfig(0, label="Open "+dataTypes[t.mode], state=open_mode)
		self.file_menu.entryconfig(1, label="Save "+dataTypes[t.mode])

	def switch_mode(self, mode) :
		t = self.tabs[self.cur_tab]
		t.update_model()

		self.remove_tabframe()
		t.mode = mode
		self.apply_tabframe()

		self.refresh()

	def select_tab(self, idx) :
		self.tabs[self.cur_tab].update_model()

		self.remove_tabframe()
		self.cur_tab = idx
		self.apply_tabframe()

		self.refresh()

	def add_tab(self) :
		tab_id = self.n_created_tabs
		self.n_created_tabs += 1

		t = tabs.Tab(self, tab_id)
		self.tabs.append(t)

		self.select_tab(len(self.tabs) - 1)

		self.tab_strs.set(self.tabs[self.cur_tab].name)

	def close_tab(self) :
		if len(self.tabs) <= 1:
			return

		idx = self.cur_tab
		self.tabs.pop(idx)

		count = len(self.tabs)
		if idx >= count:
			idx = count-1

		self.select_tab(idx)

		self.tab_strs.set(self.tabs[self.cur_tab].name)

	def refresh(self) :
		t = self.tabs[self.cur_tab]
		t.update()
		self.refresh_tab_list()

		self.master.title("Breakfast - " + t.name + " (" + t.mode_name() + ")")
		#self.filter_txt_var.set(t.filter)

	def append_byte(self, byte) :
		self.tabs[self.cur_tab].append_byte(byte)

	def load(self) :
		t = self.tabs[self.cur_tab]
		if t.mode == tabs.FILTER:
			messagebox.showinfo("Read-only mode", "Filtered mode is read-only, opening data here is unsupported")
			return

		fmode = "rb" if t.mode == tabs.EDIT else "r"
		f = filedialog.askopenfile(mode=fmode)
		if f is None:
			return

		if t.mode == tabs.EDIT:
			t.data = f.read()
		elif t.mode == tabs.MACRO:
			t.macro = f.read()

		t.update()
		f.close()

	def save(self) :
		t = self.tabs[self.cur_tab]
		t.update_model()
		fmode = "wb" if t.mode == tabs.EDIT else "w"

		f = filedialog.asksaveasfile(mode=fmode)
		if f is None:
			return

		if t.mode == tabs.EDIT:
			f.write(t.data)
		elif t.mode == tabs.FILTER:
			f.write(t.frame[t.mode].recv.get("1.0", "end"))
		elif t.mode == tabs.MACRO:
			f.write(t.macro)

		f.close()

	def reply(self) :
		t = self.tabs[self.cur_tab]
		t.update_model()
		self.comms.send(t.data)

	def send(self) :
		buf = utils.str2ba(self.prompt.get())
		self.comms.send(buf)

dev = "/dev/ttyUSB0"
if len(sys.argv) > 1:
	dev = sys.argv[1]

interface = serial.Serial(dev)
try:
	res = interface.open()
	if res <= 0:
		messagebox.showerror("Error", "Could not open device \"{0}\" ({1})".format(dev, res))
	else:
		root = tk.Tk()
		root.geometry("400x400")
		gui = Breakfast(root, interface)
		root.mainloop()
except PermissionError:
	messagebox.showerror("Error", "Inadequate permissions for opening device \"{0}\"".format(dev))
