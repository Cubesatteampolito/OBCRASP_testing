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

#Logging thread -----------------------
telegrafSockPath="/tmp/telegraf.sock" #telegraf socket path
logQueue=queue.Queue() #queue to send strings for telegraf/log file
logQueueTimeout=0.05 #timeout for log queue read (to reduce CPU starving)
telegrafRetryTime=3 #time waited after telegraf connection failure before retrying
enableFileLog=False #file logging enabled/disabled
logFilePath="telegrafLog.txt" #log file path
fileBuffering=512 #file buffer size (see python file buffering modes for details)
		#file buffer has been set to a big value because a lot of I/O from 
		#ADCS is expected, in case of service interruption this amount
		#of data can be lost
fileRetryTime=3 #time waited after log file opening failure before retrying
#--------------------------------------

def logThread(testStatus):
	
	print("Log thread started")
	sys.exit()
	
	
	telegrafSock=None
	logFile=None

	#trying to open telegraf socket
	telegrafSock=socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
	try:
				telegrafSock.connect(telegrafSockPath)
	except:
			print(f"{RED}ERROR: Failed to connect to telegraf ({0}), retrying in {1} seconds".format(telegrafSockPath,telegrafRetryTime))
			testStatus=False
	else:
		print("telegraf socket ({0}) connected".format(telegrafSockPath))

	#trying to open log file
	try:
				logFile=open(logFilePath,"w",fileBuffering) #opening log file
	except:
		print(f"{RED}ERROR: Failed to open log file ({0}), retrying in {1} seconds".format(logFilePath,fileRetryTime))
		testStatus=False

	else:
		print("log file ({0}) opened".format(logFilePath))

	getCounter=0
	
	while getCounter<3: #thread loop
		#checking if there's some data to be logged
		try:
			log=logQueue.get(timeout=logQueueTimeout)
		except:
			pass
		else:
			#if some data has been received, encode it
			logbyte=log.encode("utf-8")
			#send it to telegraf
			try:
				telegrafSock.send(logbyte)
			except:
				print(f"{RED}ERROR: Failed to send data to telegraf")
				testStatus=False
				telegrafSock.close()
				socketState=0
				sys.exit()
			else:
				getCounter+=1

			if enableFileLog:
				try:
					logFile.write(log)
				except:
					print("ERROR: Failed to write data on file")
					logFile.close()
					sys.exit()
				else: 
					getCounter+=1
				
	print("Closing telegraf socket")
	telegrafSock.close()
	
	if enableFileLog:
		print("Closing log file")
		logFile.close()
		
