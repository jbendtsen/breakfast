import tkinter as tk
from tkinter import messagebox

import threading
import time

import serial
import comms

class Breakfast:
	def __init__(self, master, iface) :
		self.master = master
		master.title("Breakfast")

		self.recv = tk.Text(self.master, width=60, height=20)
		self.recv.pack()

		self.prompt = tk.Entry(self.master, width=60)
		self.prompt.bind("<Return>", (lambda event: self.send())) # (lambda event: self.send())
		self.prompt.pack()

		send_btn = tk.Button(self.master, text="Send", command=self.send)
		send_btn.pack()

		self.master.protocol("WM_DELETE_WINDOW", self.close)

		self.comms = comms.Comms(self, iface)
		self.comms.start()

	def close(self) :
		if self.comms != None:
			self.comms.close()
			self.comms.join()

		self.master.destroy()

	def add_byte(self, byte) :
		self.recv.insert("end", "{0:02x} ".format(byte))

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
	gui = Breakfast(root, interface)
	root.mainloop()
