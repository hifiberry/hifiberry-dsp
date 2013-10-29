#!/usr/bin/env python
# 
# Dump the contents of an I2C EEPROM
#

import eeprom

size=16*1024

for i in range(0,size/16):
	print "{0:04X} {1:5d}".format(i,i*16), " :  ", 
	for j in range(0,16):
		print "{0:02X}".format(eeprom.eeprom_read_byte(i*16+j)), " ",

	print "  ",
	for j in range(0,16):
                v=eeprom.eeprom_read_byte(i*16+j)
		if ((v>=32) and (v<=127)):
			print "{:c}".format(v),
		else:
			print ".",

	print
		
	

		
