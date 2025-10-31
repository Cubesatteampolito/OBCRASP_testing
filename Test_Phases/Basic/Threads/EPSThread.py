
#!/bin/python3

import smbus2
import time
import threading
import queue
import sys
import socket
import ctypes
import os
import signal

#ADC thread ---------------------------
address=0x48
command=0x8C
#creating SMBus instance on I2C bus 1
bus=smbus2.SMBus(1)
ADCperiod=5 #sampling period in seconds
#--------------------------------------


#setting up the ADC
def setupADC(printerr=True):
	try:
		#turning on internal reference
		bus.write_byte(address, command)
	except:
		if printerr:
			print("ERROR: Failed to set up ADC")
		
	#waiting to stabilize Vref
	time.sleep(0.005)

#reading the ADC
def readADC(printerr=True):
	#requesting conversions
	convres=[0 for _ in range(8)]
	try:
		for ch in range(8):
			convOut=bus.read_i2c_block_data(address,command+0x10*ch,2)
			convres[ch]=convOut[0]*256+convOut[1]
	except:
		if printerr:
			print("ERROR: Failed to read the ADC, trying to set it up again")
		setupADC(printerr)
		
	return convres
	
def adcThread(stopThreads):
	
	import LogThread
	
	print("EPS thread started")
	logQueue =LogThread.logQueue
	
	
	print("Setting up ADC")
	setupADC()
	while 1: #thread loop
		#if stopThreads.is_set(): #need to close thread
			#break
		#lightweight method to get periodic task without strict control on period overflow or system time changes
		time.sleep(ADCperiod-time.time()%ADCperiod)		
		#getting ADC data
		#(for now error print in case of failed read is disabled to not fill the log
		#if you want to enable error print every time pass True to the function)
		ADCdata=readADC(False)
		#measurements reconstruction
		for ch in range(8):
			ADCdata[ch]=ADCdata[ch]*2.5/4095 #reconstructing measured voltage
		#reconstructing measurements
		
		ADCdata[0]=ADCdata[0]*2 		#V5
		ADCdata[1]=ADCdata[1]*0.30060	#I5
		ADCdata[2]=ADCdata[2]*5.255319 	#VB battery voltage
		ADCdata[3]=ADCdata[3]*0.30060	#IB battery current
			
		#writing data on telegraf/file
		strFormat="housekeepingOBC,source={0} VB={1},IB={2},V5={3},I5={4} {5}\n"
		finalString=strFormat.format("OBC",ADCdata[2],ADCdata[3],ADCdata[0],ADCdata[1],time.time_ns())
		print(finalString,sep="")
		#sending data to logThread
		#logQueue.put(finalString)
