#!/usr/bin/env python
#
# Simple I2C DSP routines for Sigma DSP processors
# addressing is always done in 16bit

from smbus import SMBus
smb=SMBus(1);

slaveaddr=0x34;

def dsp_write_block(addr,data):
	# split into 32 byte blocks
	blocksize=30
	while len(data) > 0:
		block=data[0:blocksize-1]
		print block
		dsp_write_small_block(addr,block)
		data=data[blocksize:]
		addr += blocksize;

def dsp_write_small_block(addr,data):
	a1=addr/256
	a0=addr%256

	data.insert(0,a0);
	smb.write_i2c_block_data(slaveaddr,a1,data)
