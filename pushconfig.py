import eeprom
import sigmaimporter
import sys

blocksize=32

def write_eeprom(i2c_address, data):
	addr=0
	code=sigmaimporter.txbuffer_data_to_eeprom(data);
	data.append(0) # end code
	# split into 32 byte blocks
	while len(code) > 0:
		block=code[0:blocksize-1]
		print block
		eeprom.eeprom_write_block(addr,block)
		code=code[blocksize:]
		addr += blocksize;
		

def main(argv):
	address=0x50
	file="demo/txbuffer.dat"

	data=sigmaimporter.read_txbuffer(file)
	if (len(data)==0):
		print "Could not parse the {}".format(file)
		exit(1)

	write_eeprom(address,data)

if __name__ == "__main__":
    main(sys.argv)
