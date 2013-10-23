#
# Methods for handling SigmaStudio compiler output
#

import re

#
# hexdump a block of data to console
#
def dump_data(data):
	size=len(data)
	for i in range(0,size/16):
        	print "{0:04X}".format(i*16), " :  ", 
        	for j in range(0,16):
                	print "{0:02X}".format(data[i*16+j]), " ",
        	print

#
# convert a comma seperated list of hex values to a list containing the integer values
#
def hex_line_to_int(line):
	d=[]
	for value in line.split(","):
		value=value.strip()
		if (value.startswith("0x")):
			d.append(int(value,16))
	return d

# 
# read a file consisting only of hex values
#
def read_hex(filename):
	f = open(filename, 'r')
	data=[]
	for line in f:
		data.extend(hex_line_to_int(line))
	return data

#
# read the txbuffer file created by Sigma Studio and return a list of the different parts
#
def read_txbuffer(filename):
	comment=re.compile('/\\*(.*)\\*/')
	f = open(filename, 'r')
	result=[]
        data=[]
	address=0
	name=None
        for line in f:
		match=comment.search(line)
		if (match):	
			# save last group object
			if (name):
				result.append({'name': name, 'address': address, 'data': data})	
				name=None
				address=0
				data=[]

			name=match.group(1)
			addresslist=hex_line_to_int(line);
			address=addresslist[0]*256+addresslist[1]
		else:
			data.extend(hex_line_to_int(line))

	# save last group
	if (name):
		result.append({'name': name, 'address': address, 'data': data})

        return result

#
# generates a write command for a block of data at a specific address
#
def commands(address,data,minlen=0):
	# 0x01          write
        # x y           2 byte length = len(data)
        # 0x00          device address
        # a1 a0     	address of the program memory
	size=len(data)
	cmd=[0x01,size/256,size%256,0x00,address/256,address%256]+data
	while (len(cmd)<minlen):
		cmd=cmd+[0x03]	# append NOOPs 
	return cmd

#
# generate the full commands for a list of blocks.first block will be extended to 32 byte to ensure compatibility with writeback 
# mechanism of the DSP
#
def txbuffer_data_to_eeprom(blocks,verbose=0):
	i=0
	res=[]
	for b in blocks:
		if (verbose):
			print "{0} @ {1:04X}".format(b['name'],b['address'])
		i+=1
		minlen=0
		if (i==1):
			minlen=26
		cmd=commands(b['address'],b['data'],minlen);
		res.extend(cmd)
	return res
		

if __name__ == "__main__":
	data=read_txbuffer("demo/txbuffer.dat")
	dump_data(txbuffer_data_to_eeprom(data,1))
