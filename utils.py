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
