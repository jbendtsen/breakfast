#!/usr/bin/python

import tkinter as tk
from tkinter import messagebox, filedialog

import sys
import threading
import re

import serial
import comms
import tabs
import utils

dataTypes = [
	"Data", "Macro"
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

		data_btn = tk.Button(self.master, text=tabs.modeNames[tabs.DATA], command=lambda: self.switch_mode(tabs.DATA))
		macro_btn = tk.Button(self.master, text=tabs.modeNames[tabs.MACRO], command=lambda: self.switch_mode(tabs.MACRO))

		data_btn.grid(row=1, column=0)
		macro_btn.grid(row=1, column=1, sticky="w")

		self.mode_btns = [data_btn, macro_btn]

		self.tab_add_btn = tk.Button(self.master, text="+", command=self.add_tab)
		self.tab_add_btn.grid(row=1, column=4)

		self.tab_del_btn = tk.Button(self.master, text="x", command=self.close_tab)
		self.tab_del_btn.grid(row=1, column=5)

		self.tabs = []
		self.n_created_tabs = 0
		self.cur_tab = 0

		self.res_prompt = ""

		self.prompt_lbl = tk.Label(self.master, text="Command")
		self.prompt_lbl.grid(row=10, columnspan=6, sticky="w")

		self.prompt = tk.Entry(self.master, width=200, name="prompt")
		self.prompt.grid(row=11, columnspan=4)

		self.send_btn = tk.Button(self.master, text="Send", command=self.send)
		self.send_btn.grid(row=11, column=4, columnspan=2)

		self.master.protocol("WM_DELETE_WINDOW", self.close)

		# self.refresh()

		self.comms = comms.Comms(self, iface)
		self.comms.start()

	def close(self) :
		self.res_prompt = self.prompt.get()

		if self.comms != None:
			self.comms.close()
			self.comms.join()

		for t in self.tabs:
			if t.macro_running() :
				t.macro_thread.kill()
				t.macro_thread.join()

			t.update_model()

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

	def remove_tabframes(self) :
		t = self.tabs[self.cur_tab]
		i = 0
		while i < 2:
			t.frame[i].grid_remove()
			self.mode_btns[i].config(relief="raised")
			i += 1

	def apply_tabframe(self) :
		t = self.tabs[self.cur_tab]
		t.frame[t.mode].grid(row=2, columnspan=6, rowspan=5)

		self.mode_btns[t.mode].config(relief="sunken")

		self.master.grid_rowconfigure(2, weight=1)
		self.master.grid_columnconfigure(3, weight=1)

		self.file_menu.entryconfig(0, label="Open "+dataTypes[t.mode])
		self.file_menu.entryconfig(1, label="Save "+dataTypes[t.mode])

	def switch_mode(self, mode) :
		if self.cur_tab >= len(self.tabs) :
			return

		t = self.tabs[self.cur_tab]
		t.update_model()

		self.remove_tabframes()
		t.mode = mode
		self.apply_tabframe()

		self.refresh()

	def select_tab(self, idx, remove=True) :
		try:
			self.tabs[self.cur_tab].update_model()
		except IndexError:
			pass

		if remove:
			self.remove_tabframes()

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

		self.remove_tabframes()
		idx = self.cur_tab
		self.tabs.pop(idx)

		count = len(self.tabs)
		if idx >= count:
			idx = count-1

		self.select_tab(idx, False)

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

		fmode = "rb" if t.mode == tabs.DATA else "r"
		f = filedialog.askopenfile(mode=fmode)
		if f is None:
			return

		if t.mode == tabs.DATA:
			t.data = bytearray(f.read())
		elif t.mode == tabs.MACRO:
			t.macro = f.read()

		t.update()
		f.close()

	def save(self) :
		t = self.tabs[self.cur_tab]
		t.update_model()
		fmode = "wb" if t.mode == tabs.DATA else "w"

		f = filedialog.asksaveasfile(mode=fmode)
		if f is None:
			return

		if t.mode == tabs.DATA:
			f.write(t.data)
		#elif t.mode == tabs.FILTER:
		#	f.write(t.frame[t.mode].recv.get("1.0", "end"))
		elif t.mode == tabs.MACRO:
			f.write(t.macro)

		f.close()

	#def overwrite(self) :
	#	t = self.tabs[self.cur_tab]
	#	t.overwrite_data()

	def reply(self) :
		t = self.tabs[self.cur_tab]
		t.update_model()
		self.comms.send(t.data)

	def send(self) :
		buf = utils.str2ba(self.prompt.get())
		self.comms.send(buf)

	def load_session(self) :
		f = None
		try:
			f = open(sys.path[0] + "/.tabs", "rb")
		except FileNotFoundError:
			self.add_tab()
			return

		buf = f.read()
		f.close()

		def get_next_line(b, idx) :
			end = b.find(bytes([0x0a]), idx)
			if end == -1:
				end = len(b)

			s = b[idx:end].decode('cp437')

			info = list([end + 1])
			info.extend(re.split(r' +', s, 1))
			return info

		curtab = 0
		nexttab = 1

		idx = 0
		while idx < len(buf) :
			line = get_next_line(buf, idx)
			idx = line[0]
			key = line[1]

			try:
				value = line[2]
			except:
				continue

			#print(line[1:])
			if key == "prompt":
				self.prompt.insert("end", value)
			elif key == "curtab":
				curtab = int(value)
			elif key == "nexttab":
				nexttab = int(value)
			elif key == "tab":
				self.add_tab()
				self.tabs[-1].name = value
			elif key == "filter":
				t = self.tabs[-1]
				t.init_filter(value[2:], value[0] == '+')
				t.update()
			elif key == "mode":
				mode = -1
				if value == "data":
					mode = tabs.DATA
				elif value == "macro":
					mode = tabs.MACRO
				self.switch_mode(mode)
			elif key == "data":
				size = int(value)
				if size > 0:
					self.tabs[-1].data = bytearray(buf[idx:idx+size])
					self.tabs[-1].update()
					idx += size
			elif key == "macro":
				size = int(value)
				if size > 0:
					self.tabs[-1].macro = buf[idx:idx+size]
					self.tabs[-1].update()
					idx += size
			elif key == "binding":
				self.tabs[-1].binding = value.split()

		if len(self.tabs) == 0:
			self.add_tab()
		else:
			self.n_created_tabs = nexttab
			self.select_tab(curtab)

	def save_session(self) :
		f = open(sys.path[0] + "/.tabs", "wb")
		info = "prompt {0}\ncurtab {1}\nnexttab {2}\n\n".format(self.res_prompt, self.cur_tab, self.n_created_tabs)
		f.write(info.encode())
		info = ""

		def lazy_len(data) :
			try:
				l = len(data)
			except:
				l = 0
			return l

		for t in self.tabs:
			flt_mode = "+" if t.is_filtered else "-"
			data_len = lazy_len(t.data)
			macro_len = lazy_len(t.macro)
			try:
				tab_mode = ("data", "macro")[t.mode]
			except:
				tab_mode = "?"

			info += "tab {0}\nfilter {1} {2}\nmode {3}\ndata {4}\n".format(t.name, flt_mode, t.filter, tab_mode, data_len)
			f.write(info.encode())
			if data_len > 0:
				f.write(t.data)
				info = "\n"
			else:
				info = ""

			if t.binding is not None and len(t.binding) > 0:
				info += "binding " + " ".join(t.binding) + "\n"

			info += "macro {0}\n".format(macro_len)
			f.write(info.encode())
			if macro_len > 0:
				macro = t.macro.encode() if isinstance(t.macro, str) else t.macro
				f.write(macro)
				info = "\n\n"
			else:
				info = "\n"

		f.close()

def main() :
	dev = "/dev/ttyUSB0"
	if len(sys.argv) > 1:
		dev = sys.argv[1]

	interface = None
	res = -1
	try:
		interface = serial.Serial(dev)
		res = interface.open()
	except PermissionError:
		messagebox.showerror("Error", "Inadequate permissions for opening device \"{0}\"".format(dev))

	if res <= 0:
		messagebox.showerror("Error", "Could not open device \"{0}\" ({1})".format(dev, res))
		return

	root = tk.Tk()
	root.geometry("400x400")

	gui = Breakfast(root, interface)
	gui.load_session()
	root.mainloop()
	gui.save_session()

main()
