import threading
import os
import select

import serial

# all methods here are called from the main thread, except ship() and run()
class Comms(threading.Thread) :
	def __init__(self, gui, iface) :
		super(Comms, self).__init__()
		self.main = gui
		self.iface = iface
		self.running = False

		self.readfd, self.writefd = os.pipe()

	def interrupt(self) :
		os.write(self.writefd, bytes([0]))

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
			r, w, e = select.select([self.iface.fd, self.readfd], [], [])
			fd = r[0]

			if fd == self.iface.fd:
				res = self.iface.read(byte, 1)
				if res == 1:
					self.main.add_byte(byte[0])
					# print("{0:x}".format(byte[0]), end=' ')
					# time.sleep(0.1)
			elif fd == self.readfd and self.package != None:
				self.iface.write(self.package, len(self.package))
				self.package = None
