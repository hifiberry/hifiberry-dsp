#!/usr/bin/env python
#
# Simple I2C DSP routines for Sigma DSP processors
# addressing is always done in 16bit

from smbus import SMBus
smb=SMBus(1);

slaveaddr=0x34;

def addr2memsize(addr):
	if (addr < 1024):
		blocksize=4
	elif (addr < 2048):
		blocksize=5
	elif (addr < 2056):
		blocksize=4
	elif (addr < 2061):
		blocksize=2
	elif (addr < 2069):
		blocksize=5
	elif (addr < 2077):
		blocksize=2
	elif (addr < 2078):
		blocksize=1
	elif (addr < 2079):
		blocksize=2
	elif (addr < 2080):
		blocksize=1
	elif (addr < 2082):
		blocksize=3
	elif (addr < 2088):
		blocksize=2
	else:
		blocksize=1
	return blocksize

def dsp_write_block(addr,data):
	# split into 32 byte blocks
	while len(data) > 0:
		blocksize=addr2memsize(addr)
		block=data[0:blocksize]
		#print block
		dsp_write_small_block(addr,block)
		data=data[blocksize:]
		addr += 1;

def dsp_write_small_block(addr,data):
	print addr, data
	a1=addr/256
	a0=addr%256

	data.insert(0,a0);
	smb.write_i2c_block_data(slaveaddr,a1,data)
