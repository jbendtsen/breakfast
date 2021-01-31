import threading
import os
import select

import serial

class Comms(threading.Thread) :
	def __init__(self, gui, iface) :
		super(Comms, self).__init__()
		self.main = gui
		self.iface = iface
		self.running = False
		self.packages = []

		self.readfd, self.writefd = os.pipe()

	# Write a byte to our writefd, which will unblock the call to select() inside run()
	# This allows us to write data out (if len(packages) > 0) or exit this thread
	def update(self) :
		os.write(self.writefd, bytes([0]))

	# Once our interrupt has been handled, we read the byte that we wrote
	#  so that there won't be any new data to read, meaning that select() will start blocking again
	def clear(self) :
		os.read(self.readfd, 1)

	def enqueue(self, buf) :
		if self.packages is None:
			self.packages = [buf]
		else:
			self.packages.append(buf)

	def send(self, buf) :
		self.enqueue(buf)
		self.update()

	def close(self) :
		self.packages = []
		self.running = False
		self.update()

	def run(self) :
		self.running = True

		byte = bytearray(1)
		while (self.running) :
			# Wait for either a byte from the serial's fd or from our own self-pipe (thanks to self.update())
			fdset = [self.readfd]
			if not self.iface.dummy:
				fdset.append(self.iface.fd)

			r, w, e = select.select(fdset, [], [])
			fd = r[0]

			if fd == self.iface.fd:
				res = self.iface.read(byte, 1)
				if res == 1:
					self.main.append_byte(byte[0])

			elif fd == self.readfd:
				self.clear()

				data = bytearray()
				for buf in self.packages:
					data.extend(buf)

				if len(data) > 0:
					self.iface.write(data, len(data))

				self.packages = []
