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

		self.readfd, self.writefd = os.pipe()

	# Write a byte to our writefd, which will unblock the call to select() inside run()
	def interrupt(self) :
		os.write(self.writefd, bytes([0]))

	# Once our interrupt has been handled, we read the byte that we wrote
	#  so that there won't be any new data to read, meaning that select() will start blocking again
	def clear(self) :
		os.read(self.readfd, 1)

	def send(self, buf) :
		self.package = buf
		self.interrupt()

	def close(self) :
		self.package = None
		self.running = False
		self.interrupt()

	def run(self) :
		self.running = True

		byte = bytearray(1)
		while (self.running) :
			# Wait for either a byte from the serial's fd or from our own self-pipe (thanks to self.interrupt())
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
				if self.package != None:
					self.iface.write(self.package, len(self.package))
					self.package = None
