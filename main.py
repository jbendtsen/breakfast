import tkinter as tk
from tkinter import messagebox

import threading
import os
import subprocess
import shlex

import serial
import comms

class Tab:
	def __init__(self, gui) :
		self.main = gui
		self.data = bytearray([])
		self.use_filter = False

	def append_byte(self, byte) :
		self.data.append(byte)
		if not self.use_filter:
			self.main.recv.insert(tk.END, "{0:02x} ".format(byte))

	def update(self) :
		self.main.recv.delete("1.0", tk.END)

		if self.use_filter:
			cmd = self.main.filter_txt.get()

			# if a filter was given, use it as a shell command and provide our data to stdin
			if len(cmd) > 0:
				proc = subprocess.Popen(args=shlex.split(cmd), stdout=subprocess.PIPE, stdin=subprocess.PIPE)
				proc.stdin.write(self.data)
				proc.stdin.close()
				text = proc.stdout.read()
			# otherwise treat our data as straight-up ASCII
			else:
				text = self.data.decode('cp437')
		else:
			text = self.raw_text()

		self.main.recv.insert(tk.END, text)

	def raw_text(self) :
		length = len(self.data) * 3
		text = [' '] * length

		idx = 0
		for b in self.data:
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

class Breakfast:
	def __init__(self, master, iface) :
		self.master = master
		master.title("Breakfast")

		self.recv_lbl = tk.Label(self.master, text="Receiving", width=200, anchor="w")
		self.recv_lbl.pack()

		self.recv = tk.Text(self.master, width=200, height=20)
		self.recv.pack()

		self.use_filter = tk.IntVar()
		self.filter_cb = tk.Checkbutton(self.master, text="Filter", width=200, anchor="w", variable=self.use_filter, command=self.toggle_filter)
		self.filter_cb.pack()

		self.filter_txt = tk.Entry(self.master, width=200)
		self.filter_txt.bind("<Return>", (lambda event: self.apply_filter()))
		self.filter_txt.pack()

		self.prompt_lbl = tk.Label(self.master, text="Command", width=200, anchor="w")
		self.prompt_lbl.pack()

		self.prompt = tk.Entry(self.master, width=200)
		self.prompt.bind("<Key>", self.send_key_down)
		self.prompt.pack(expand=True)

		send_btn = tk.Button(self.master, text="Send", command=self.send)
		send_btn.pack()

		self.master.protocol("WM_DELETE_WINDOW", self.close)

		self.tab = Tab(self)

		self.comms = comms.Comms(self, iface)
		self.comms.start()

	def send_key_down(self, e) :
		if e.keysym == "Return" and (e.state & 1) == 0:
			self.send()

	def close(self) :
		if self.comms != None:
			self.comms.close()
			self.comms.join()

		self.master.destroy()

	def toggle_filter(self) :
		self.tab.use_filter = self.use_filter.get() == 1
		self.tab.update()

	def apply_filter(self) :
		print("apply_filter()")

	def append_byte(self, byte) :
		self.tab.append_byte(byte)

	def send(self) :
		msg = self.prompt.get()
		buf = bytearray()
		idx = 0

		for c in msg:
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

		# interrupt our communications thread so that it can send our message
		self.comms.send(buf)

interface = serial.Serial()
if interface.open() <= 0:
	messagebox.showerror("Error", "Could not open serial device")
else:
	root = tk.Tk()
	root.geometry("400x400")
	gui = Breakfast(root, interface)
	root.mainloop()
