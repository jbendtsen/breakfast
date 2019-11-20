import tkinter as tk
from tkinter import messagebox, filedialog

import os
import sys
import threading
import subprocess

import serial
import comms

def str2ba(string) :
	buf = bytearray()
	idx = 0

	for c in string:
		val = ord(c)

		# if the current character is not a hex digit [0-9a-fA-F],
		#  then try the next character
		if not (val >= 0x30 and val <= 0x39) \
			and not (val >= 0x41 and val <= 0x46) \
			and not (val >= 0x61 and val <= 0x66) :
			continue

		if (idx % 2 == 0) :
			buf.append(int(c, 16))
		else:
			buf[-1] = (buf[-1] << 4) | int(c, 16)

		idx += 1

	return buf

def ba2str(buf) :
	length = len(buf) * 3
	text = [' '] * length

	idx = 0
	for b in buf:
		d = b >> 4
		if d >= 0xa:
			text[idx] = chr(87 + d)
		else:
			text[idx] = chr(48 + d)

		d = b & 0xf
		if d >= 0xa:
			text[idx+1] = chr(87 + d)
		else:
			text[idx+1] = chr(48 + d)

		idx += 3

	return "".join(text)

class Tab:
	def __init__(self, gui, idx) :
		self.main = gui
		self.name = "Tab {0}".format(idx+1)
		self.data = bytearray([])
		self.filter = ""
		self.use_filter = False

	def append_byte(self, byte) :
		self.data.append(byte)
		if not self.use_filter:
			self.main.recv.insert(tk.END, "{0:02x} ".format(byte))

	def maybe_edit(self) :
		if not self.use_filter :
			self.data = str2ba(self.main.recv.get("1.0", "end"))

	def update(self) :
		self.main.recv.config(state="normal")
		self.main.recv.delete("1.0", tk.END)

		text = ""
		label = ""
		if self.use_filter:
			cmd = self.filter

			# if a filter was given, use it as a shell command and provide our data to stdin
			if len(cmd) > 0:
				try:
					proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
					proc.stdin.write(self.data)
					proc.stdin.close()
					text = proc.stdout.read().decode('cp437')
					text += "\n" + proc.stderr.read().decode('cp437')

				except (FileNotFoundError, OSError) as e:
					text = "Filter Error: {0}".format(e)
			# otherwise treat our data as straight-up ASCII
			else:
				text = self.data.decode('cp437')

			label = "Receiving (Filtered Mode)"
		else:
			text = ba2str(self.data)
			label = "Receiving (Edit Mode)"

		self.main.recv.insert(tk.END, text)

		editing = "disabled" if self.use_filter else "normal"
		self.main.recv.config(state=editing)
		self.main.load_btn.config(state=editing)

		self.main.recv_lbl.config(text=label)

class Breakfast:
	def __init__(self, master, iface) :
		self.init = False
		self.master = master

		self.tabs = []
		self.n_created_tabs = 0
		self.add_tab()

		self.tab_strs = tk.StringVar()
		name = self.tabs[0].name
		self.tab_strs.set(name)
		self.tab_strs.trace('w', self.select_tab_str)

		self.tabs_om = tk.OptionMenu(master, self.tab_strs, name)
		self.tabs_om.grid(row=0, column=0, columnspan=3, sticky="w")

		self.tab_add_btn = tk.Button(master, text="+", command=self.add_tab)
		self.tab_add_btn.grid(row=0, column=3)

		self.tab_del_btn = tk.Button(master, text="x", command=self.close_tab)
		self.tab_del_btn.grid(row=0, column=4)

		self.filter_lbl = tk.Label(text="Filter")
		self.filter_lbl.grid(row=1, columnspan=5, sticky="w")

		self.filter_cb_var = tk.IntVar()

		self.filter_cb = tk.Checkbutton(self.master, padx=10, variable=self.filter_cb_var, command=self.toggle_filter)
		self.filter_cb.grid(row=2)

		self.filter_txt_var = tk.StringVar()
		self.filter_txt_var.trace("w", self.update_filter)

		self.filter_txt = tk.Entry(self.master, width=200, textvariable=self.filter_txt_var)
		self.filter_txt.bind("<Return>", (lambda event: self.refresh()))
		self.filter_txt.grid(row=2, column=1, columnspan=4)

		self.recv_lbl = tk.Label(self.master, text="Receiving (Edit Mode)")
		self.recv_lbl.grid(row=3, columnspan=5, sticky="w")

		self.recv = tk.Text(self.master, width=200, height=100)
		self.recv.bind("<FocusOut>", lambda event: self.tabs[self.cur_tab].maybe_edit())
		self.recv.bind("<Control-a>", self.recv_select_all)
		self.recv.grid(row=4, columnspan=5)

		self.load_btn = tk.Button(self.master, text="Load", command=self.load)
		self.load_btn.grid(row=5, column=2)

		self.save_btn = tk.Button(self.master, text="Save", command=self.save)
		self.save_btn.grid(row=5, column=3)

		self.reply_btn = tk.Button(self.master, text="Reply", command=self.reply)
		self.reply_btn.grid(row=5, column=4)

		self.prompt_lbl = tk.Label(self.master, text="Command")
		self.prompt_lbl.grid(row=6, columnspan=5, sticky="w")

		self.prompt = tk.Entry(self.master, width=200)
		self.prompt.bind("<Key>", self.send_key_down)
		self.prompt.grid(row=7, columnspan=4)

		self.send_btn = tk.Button(self.master, text="Send", command=self.send)
		self.send_btn.grid(row=7, column=4)

		self.master.protocol("WM_DELETE_WINDOW", self.close)

		self.init = True

		self.comms = comms.Comms(self, iface)
		self.comms.start()

	def close(self) :
		if self.comms != None:
			self.comms.close()
			self.comms.join()

		self.master.destroy()

	def send_key_down(self, e) :
		if e.keysym == "Return" and (e.state & 1) == 0:
			self.send()

	def recv_select_all(self, *args) :
		self.recv.tag_add("sel", "1.0", "end")
		self.recv.focus_set()

	def update_filter(self, *args) :
		s = self.filter_txt_var.get()
		self.tabs[self.cur_tab].filter = s

	def toggle_filter(self) :
		tab = self.tabs[self.cur_tab]
		tab.maybe_edit()
		tab.use_filter = self.filter_cb_var.get() == 1
		tab.update()

	def refresh_tab_list(self) :
		if not self.init:
			return

		menu = self.tabs_om["menu"]
		menu.delete(0, tk.END)
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

		print("Could not find " + name)

	def select_tab(self, idx) :
		self.cur_tab = idx
		self.master.title("Breakfast - " + self.tabs[idx].name)
		self.refresh()

	def add_tab(self) :
		tab_id = self.n_created_tabs
		self.n_created_tabs += 1

		t = Tab(self, tab_id)
		self.tabs.append(t)

		self.select_tab(len(self.tabs) - 1)

		if self.init:
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

		if self.init:
			self.tab_strs.set(self.tabs[self.cur_tab].name)

	def refresh(self) :
		if not self.init:
			return

		t = self.tabs[self.cur_tab]
		t.update()

		self.filter_txt_var.set(t.filter)
		self.filter_cb_var.set(1 if t.use_filter else 0)

		self.refresh_tab_list()

	def append_byte(self, byte) :
		self.tabs[self.cur_tab].append_byte(byte)

	def load(self) :
		f = filedialog.askopenfile(mode="rb")
		t = self.tabs[self.cur_tab]
		t.data = f.read()
		t.update()
		f.close()

	def save(self) :
		t = self.tabs[self.cur_tab]
		t.maybe_edit()
		fmode = "w" if t.use_filter else "wb"

		f = filedialog.asksaveasfile(mode=fmode)
		if f is None:
			return

		if t.use_filter:
			f.write(self.recv.get("1.0", "end"))
		else:
			f.write(t.data)

		f.close()

	def reply(self) :
		t = self.tabs[self.cur_tab]
		t.maybe_edit()
		self.comms.send(t.data)

	def send(self) :
		buf = str2ba(self.prompt.get())
		self.comms.send(buf)

dev = "/dev/ttyUSB0"
if len(sys.argv) > 1:
	dev = sys.argv[1]

interface = serial.Serial(dev)
if interface.open() <= 0:
	messagebox.showerror("Error", "Could not open serial device " + interface.dev + ": fd={0}".format(interface.fd))
else:
	root = tk.Tk()
	root.grid_rowconfigure(4, weight=1) # receiving window row
	root.grid_columnconfigure(1, weight=1)
	root.geometry("400x400")
	gui = Breakfast(root, interface)
	root.mainloop()
