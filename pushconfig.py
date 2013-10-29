#!/usr/bin/env python
#
import eeprom
import dsp_i2c
import sigmaimporter
import sys

blocksize=32
EEPROM=1
DSP=2

def write_device(data, destination=DSP):
	if destination==EEPROM:
		addr=0
		code=sigmaimporter.txbuffer_data_to_eeprom(data);
		data.append(0) # end code
		# split into 32 byte blocks
		while len(code) > 0:
			block=code[0:blocksize-1]
			print block
			eeprom.eeprom_write_block(0x50,block)
			code=code[blocksize:]
			addr += blocksize;
	elif destination==DSP:
		for block in data:
			dsp_i2c.dsp_write_block(block["address"],block["data"])
		

def main(argv):
	address=0x50
	file="demo/txbuffer-ledon.dat"

	data=sigmaimporter.read_txbuffer(file)
	if (len(data)==0):
		print "Could not parse the {}".format(file)
		exit(1)

	write_device(data)

if __name__ == "__main__":
    main(sys.argv)
