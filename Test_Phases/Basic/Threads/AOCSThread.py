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

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BLUE = '\033[34m'
WHITE = '\033[37m'
LIGHT_BLUE = '\033[36m'
RESET = '\033[0m'


def aocsThread(testStatus):
	print("AOCS thread started")
	sys.exit()
	sys.path.append("./messages")
	import messages as msg
	serial = ctypes.CDLL("./serial/serialInterface.so")
	print("Maximum serial payload length: {0}\n".format(serial.getMaxLen()))
	
	import LogThread
    
	logQueue = LogThread.logQueue
	uartTimeout=0.100
	uartRetries=2 


	#initializing serial line towards ADCS
	print("Initializing UART")
	serial.initUART(ctypes.c_float(uartTimeout),ctypes.c_uint8(uartRetries))
	
	#trying to send data to AOCS
	print(f"{YELLOW} Sending data to AOCS")
	dataout="need to figure it out"
	msg_out_Struct=msg.parseStruct(dataout)
	buffOut = bytes(msg_out_Struct)
	ackVal = serial.sendUART(buffOut, len(buffOut),1) #requesting ACK

	if ackVal:
		print(f"{WHITE}Message sent to AOCS: {0} ".format(dataout))
	else: 
		print(f"{RED} ERROR DURING SENDING DATA TO AOCS: No ack from AOCS")
		testStatus=False

	

	#trying to read data from AOCS through serial
	buffIN=bytes(serial.getMaxLen())
	l=serial.receiveUART(buffIN,len(buffIN))

	if l!=0:
		#check message code
		code= buffIN[0]
		#if the code and the length correspond to a valid message
		if code in msg.msgDict.keys() and ctypes.sizeof(msg.msgDict[code]) == l:
			# ------ HERE WE HANDLE EACH MESSAGE CODE FROM ADCS -------
			match msg.msgDict[code].__name__:
				case "attitudeADCS" | "housekeepingADCS" | "opmodeADCS": #attitude telemetry message
					#saving current timestamp
					currt=time.time_ns()
						
					#creating the corresponding message struct
					newstruct=msg.msgDict[code].from_buffer_copy(buffIN[:l])
						
					#building influxdb write string
					influxstr=msg.msgDict[code].__name__+"," #inserting message name as dataset name
					influxstr+="source=ADCS "#inserting source tag
					#iteratively inserting all fields
					for f in newstruct._fields_:
						#checking if value is an array
						if isinstance(getattr(newstruct,f[0]),ctypes.Array):
							arraylist=getattr(newstruct,f[0])[:]
							for index in range(len(arraylist)):
								influxstr+="{0}={1}".format("{0}[{1}]".format(f[0],index),arraylist[index])
								if (index+1)!=len(arraylist):
										influxstr+=","							
						else:
							influxstr+="{0}={1}".format(f[0],getattr(newstruct,f[0]))

						if f!=newstruct._fields_[-1]:
							influxstr+=","
						
					#appending timestamp
					influxstr+=" {0}\n".format(currt)
						
					#sending to telegraf queue
					logQueue.put(influxstr)
				case _:
					print("WARNING: {0} message from ADCS not handled".format(msg.msgDict[code].__name__))


		else:
			print(f"{RED}ERROR: Received unknown message from ADCS (code {0} length {1})".format(code, l))
			testStatus=False
	
	print(f"{WHITE}Closing UART")	
	serial.deinitUART()
