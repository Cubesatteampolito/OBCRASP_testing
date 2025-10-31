#!/bin/python3

import smbus2
import time

address=0x48
command=0x8C

print("ADC tester (ADS7828E)")

#creating SMBus instance on I2C bus 1
bus=smbus2.SMBus(1)

#turning on internal reference
bus.write_byte(address, command)

#waiting 5 milliseconds to stabilize Vref
time.sleep(0.005)

#requesting conversions
convres=[]
for ch in range(8):
	convres.append(bus.read_i2c_block_data(address,command+0x10*ch,2))

#printing conversion results from the list of read messages
print("Conversion results:")
for ch in range(len(convres)):
	convres[ch]=convres[ch][0]*256+convres[ch][1]
	convres[ch] = convres[ch]*2.5/4096
	print("Ch {0}: {1}".format(ch,convres[ch]))
	

convres[0]= convres[0] * 2 #V5
convres[1]= convres[1]*5.255319  #vb
convres[4] = convres[4]/0.30060  #I5
convres[5] = convres[5]/0.30060  #IB

print("VB VALUE: {0}".format(convres[1])) 
print("IB VALUE: {0}".format(convres[5])) 
print("V5 VALUE: {0}".format(convres[0])) 
print("I5 VALUE: {0}".format(convres[4])) 
print("PC104 VALUE: {0}".format(convres[2])) #unknown
print("PC104 VALUE: {0}".format(convres[3])) #unknown
print("PC104 VALUE: {0}".format(convres[2])) #unknown
print("PC104 VALUE: {0}".format(convres[3])) #unknown

'''
ELEMENTO 0: CH0 --> V5
ELEMENTO 1: CH2 --> VB
ELEMENTO 2: CH4 --> T0 --> PC104 resistenza incorporata
ELEMENTO 3: CH6 --> PC104
ELEMENTO 4: CH1 --> I5
ELEMENTO 5: CH3 --> IB
ELEMENTO 6: CH5 --> PC104
ELEMENTO 7: CH7 --> PC104
'''