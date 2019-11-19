import os
import sys
import termios
import fcntl

class Serial:
	def __init__(self, dev="/dev/ttyUSB0") :
		Serial.dev = dev
		Serial.fd = -1
		Serial.in_use = False

	def open(self) :
		if Serial.fd >= 0:
			return Serial.fd

		Serial.in_use = True
		flags = os.O_RDWR | os.O_NONBLOCK | os.O_SYNC | os.O_NOCTTY

		try:
			Serial.fd = os.open(Serial.dev, flags)
		except FileNotFoundError as e:
			Serial.fd = -1
			Serial.in_use = False
			return Serial.fd

		# fcntl.fcntl(Serial.fd, fcntl.F_SETFL, fcntl.O_NONBLOCK)

		# simple terminal mode
		cflags = termios.CRTSCTS | termios.CLOCAL | termios.CREAD
		cc = [0] * 32

		 # this means the minimum bytes a read() can return is 1, meaning we can do blocking reads
		cc[termios.VMIN] = 1
		cc[termios.VTIME] = 1

		tio = [
			0,        # iflag
			0,        # oflag
			cflags,   # cflag
			0,        # lflag
			0,        # ispeed
			0,        # ospeed
			cc        # cc
		]
		termios.tcsetattr(Serial.fd, termios.TCSANOW, tio)

		Serial.in_use = False
		self.flush()
		return Serial.fd

	def flush(self) :
		if (Serial.fd >= 0 and not Serial.in_use) :
			termios.tcflush(Serial.fd, termios.TCIOFLUSH)

	def close(self) :
		if Serial.in_use:
			return

		if Serial.fd >= 0:
			os.close(Serial.fd)

		Serial.fd = -1

	def plunge(self) :
		# send a fake byte to the file descriptor, such that it may unblock a call to read()
		print("Before ioctl")
		fcntl.ioctl(Serial.fd, termios.TIOCSTI, bytes([0]))
		print("After ioctl")

	def read(self, buf, size, block_size = 0xf800) :
		return self.transfer(buf, size, block_size, 0)

	def write(self, buf, size, block_size = 0xf800) :
		return self.transfer(buf, size, block_size, 1)

	def transfer(self, buf, size, block_size, wr_mode) :
		if (Serial.fd < 0 or Serial.in_use) :
			return 0

		Serial.in_use = True
		off = 0
		left = size

		while (left > 0) :
			span = left
			if (span > block_size) :
				span = block_size

			if (wr_mode) :
				chunk = buf[off:off+span]
				res = os.write(Serial.fd, chunk)
			else:
				chunk = os.read(Serial.fd, span)
				res = len(chunk)
				buf[off:off+res] = chunk

			if (res < len(chunk)) :
				Serial.in_use = False
				return res

			off += span
			left -= span

		Serial.in_use = False
		return size
