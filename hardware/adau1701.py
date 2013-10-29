#!/usr/bin/env python
#
# Hardware routines for the ADAU1701
# addressing is always done in 16bit

import math 
try:
	from smbus import SMBus
	i2c_available=True
	smb=SMBus(1);
except ImportError:
	i2c_available=False
	smb=None

# ADAU1701 address range
MAXADDRESS=2087
I2C_SLAVEADDR=0x34
COREREG_ADDR=2076
LSB_SIGMA=float(1)/math.pow(2,23)

def float_to_28bit_fixed(f):
	'''
	converts a float to an 28bit fixed point value used in SigmaDSP processors
	'''
	if (f>16-LSB_SIGMA) or (f<-16):
		raise Exception("value {} not in range [-16,16]".format(f))

	# dual complement
	if (f<0):
		f=32+f
	
	# multiply by 2^23, then convert to integer
	f=f*(1<<23)
	return int(f)

def dsp28bit_fixed_to_float(p):
	'''
    converts an 28bit fixed point value used in SigmaDSP processors to a float value
    '''
	f=float(p)/pow(2,23)
	if f>=16:
		f=-32+f
	return f



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

def dsp_write_blocks(blocks, verbose=True):
	if not i2c_available:
			print "I2C not available, simulating only"
	for block in blocks:
		addr=block["address"]
		data=block["data"]
		if verbose:
			print "Writing {0} at {1:04X} ({1}), {2} byte".format(block["name"],addr,len(data))
		if i2c_available:
			dsp_write_block(addr,data,verbose)

def dsp_write_block(addr,data,verbose=0):
	# split into blocks, block size depends on the address
	while len(data) > 0:
		blocksize=addr2memsize(addr)
		block=data[0:blocksize]
		if (verbose):
			print addr, block
		dsp_write_small_block(addr,block)
		data=data[blocksize:]
		addr += 1;
		

def dsp_write_small_block(addr,data):
	a1=addr/256
	a0=addr%256

	data.insert(0,a0);
	if smb:
		smb.write_i2c_block_data(I2C_SLAVEADDR,a1,data)
	else:
		print "Simulated I2C write address={} value={}".format(addr,data[1:])
		
def write_param(paramaddr,value):
	# convert to 4 byte representation first
	values=[]
	for _i in range(0,4):
		values.insert(0,int(value%256))
		value/=256
	dsp_write_small_block(paramaddr, values)
		
# generate a full memory dump based on the content parsed from TXBuffer
def memory_map_from_blocks(blocks):
	mem=[0]*(MAXADDRESS+1)
	for block in blocks:
		addr=block["address"]
		data=block["data"]
		# split into blocks, block size depends on the address
		while len(data) > 0:
			blocksize=addr2memsize(addr)
			block=data[0:blocksize]
			mem[addr]=block
			data=data[blocksize:]
			addr += 1;
	return mem


#
# Demo code
#
def main():
	print "0	   {:07x}".format(float_to_28bit_fixed(0))
	print "16-1LSB {:07x}".format(float_to_28bit_fixed(16-LSB_SIGMA))
	print "8	   {:07x}".format(float_to_28bit_fixed(8))
	print "-16	   {:07x}".format(float_to_28bit_fixed(-16))
	print "0.25	   {:07x}".format(float_to_28bit_fixed(0.25))
	print "-0.25   {:07x}".format(float_to_28bit_fixed(-0.25))	
