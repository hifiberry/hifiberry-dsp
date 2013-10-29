#!/usr/bin/env python
#
# Simple I2C EEPROM routines
# works with 16-bit addressable EEPROMs (up to 64kB)

from smbus import SMBus

smb=SMBus(1);
slaveaddr=0x50;

def eeprom_set_current_address(addr):
	a1=addr/256
	a0=addr%256
	smb.write_i2c_block_data(slaveaddr,a1,[a0])

def eeprom_write_block(addr,data):
	a1=addr/256
	a0=addr%256

	data.insert(0,a0);
	smb.write_i2c_block_data(slaveaddr,a1,data)

	# wait until acknowledged
	ready=0
	while not ready:
		try:
			smb.read_byte(slaveaddr)
			ready=1
		except IOError:
			ready=0

def eeprom_read_byte(addr):
	eeprom_set_current_address(addr)
	return smb.read_byte(slaveaddr)
