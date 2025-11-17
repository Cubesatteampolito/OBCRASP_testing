#!/bin/python3


import time
import sys
import ctypes
import os
import importlib.util


#CDH thread ---------------------------
availableCommands=[0,1] #command codes available from client
clientQueueRxTimeout=0.02 #timeout for reaing from client rx queue
#--------------------------------------


#set stdout in line buffering mode
sys.stdout.reconfigure(line_buffering=True)

messages_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "messages", "messages.py")
)

# ----example
spec = importlib.util.spec_from_file_location("messages", messages_path)
msg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(msg)

serial_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'serial', 'serialInterface.so'))
serial = ctypes.CDLL(serial_path)
print("Maximum serial payload length: {0}\n".format(serial.getMaxLen()))

def cdhThread(stopThreads):
	print("CDH thread started")
	from Threads.ClientThread import uartTimeout, uartRetries,clientQueueTx, clientQueueRx
	from Threads.LogThread import logQueue
	global clientQueueRxTimeout
	#initializing serial line towards ADCS
	print("Initializing UART")
	serial.initUART(ctypes.c_float(uartTimeout),ctypes.c_uint8(uartRetries))
	
	while 1: #thread loop
		if stopThreads.is_set(): #need to close thread
			break
	
		#try receiving data from client queue
		try:
			data=clientQueueRx.get(timeout=clientQueueRxTimeout)
		except:
			pass
		else: #something received
			if data.split(maxsplit=1)[0]=="help":
				helpstring='Available commands (array elements should be passed inside quotes " "):\n'
				for available in availableCommands:
					try:
						helpstring+="{0}\n\n".format(msg.msgDict[available]())
					except:
						pass
						
				clientQueueTx.put(helpstring)
			
			else:
				#Here we handle all the possible commands from client
				try:
					#extract message struct from command string
					msgStruct=msg.parseStruct(data)
					if msgStruct.code not in availableCommands:
						raise Exception
				except:
					clientQueueTx.put("ERROR: the requested command was not recognized or the arguments format is wrong\nYou can list avilable commands with 'help'\n")
				else:
					#send message over serial
					bufftx=bytes(msgStruct)
					retVal=serial.sendUART(bufftx,len(bufftx),1) #requesting also an ack from ADCS
					if retVal:
						clientQueueTx.put("{0} message sent\n".format(data.split(maxsplit=1)[0]))
					else:
						clientQueueTx.put("ERROR, ADCS didn't acknowledge {0}\n".format(data.split(maxsplit=1)[0]))
					
						
		#try reading message from serial
		buffrx=bytes(serial.getMaxLen())
		l=serial.receiveUART(buffrx,len(buffrx))

		if l != 0:
			#check message code
			code=buffrx[0]
			#if the code and the length correspond to a valid message
			if code in msg.msgDict.keys(): #and ctypes.sizeof(msg.msgDict[code]) == l:
				# ------ HERE WE HANDLE EACH MESSAGE CODE FROM ADCS -------			
				match msg.msgDict[code].__name__:
					case "attitudeADCS" | "housekeepingADCS" | "opmodeADCS": #attitude telemetry message
						#saving current timestamp
						currt=time.time_ns()
						
						#creating the corresponding message struct
						newstruct=msg.msgDict[code].from_buffer_copy(buffrx[:l])
						
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
						print("PACKET ARRIVED: "+influxstr)
						#sending to telegraf queue
						logQueue.put(influxstr)
						
					case _: #default case
						print("WARNING: {0} message from ADCS not handled".format(msg.msgDict[code].__name__))
			else:
				print("WARNING: Received unknown message from ADCS (code {0} length {1})".format(code, l))
				print("Packet {0} {1} {2}".format(code,msg.msgDict[code].__name__,msg.msgDict[code].__str__))
	
	print("Closing UART")	
	serial.deinitUART()

