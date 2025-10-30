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

def logThread(stopThreads):
	
	print("Log thread started")
	sys.exit()
	telegrafTryTime=0
	socketState=0
	
	fileTryTime=0
	fileState=0
	
	telegrafSock=None
	logFile=None
	
	while 1: #thread loop
		if stopThreads.is_set(): #need to close thread
			break
		
		#checking if telegraf is not connected
		if socketState==0 and (time.time()-telegrafTryTime)>telegrafRetryTime:
			telegrafTryTime=time.time()
			telegrafSock=socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
			try:
				telegrafSock.connect(telegrafSockPath)
			except:
				print("ERROR: Failed to connect to telegraf ({0}), retrying in {1} seconds".format(telegrafSockPath,telegrafRetryTime))
			else:
				socketState=1
				print("telegraf socket ({0}) connected".format(telegrafSockPath))	
		
		#checking if log file is not opened
		if enableFileLog and fileState==0 and (time.time()-fileTryTime)>fileRetryTime:
			fileTryTime=time.time()
			try:
				logFile=open(logFilePath,"w",fileBuffering) #opening log file
			except:
				print("ERROR: Failed to open log file ({0}), retrying in {1} seconds".format(logFilePath,fileRetryTime))
			else:
				fileState=1
				print("log file ({0}) opened".format(logFilePath))
				
		
		#checking if there's some data to be logged
		try:
			log=logQueue.get(timeout=logQueueTimeout)
		except:
			pass
		else:
			#if some data has been received, encode it
			logbyte=log.encode("utf-8")
			#send it to telegraf
			if socketState==1:
				try:
					telegrafSock.send(logbyte)
				except:
					print("ERROR: Failed to send data to telegraf")
					telegrafSock.close()
					socketState=0
					
			if enableFileLog and fileState==1:
				try:
					logFile.write(log)
				except:
					print("ERROR: Failed to write data on file")
					logFile.close()
					fileState=0
				
	print("Closing telegraf socket")
	telegrafSock.close()
	
	if enableFileLog:
		print("Closing log file")
		logFile.close()
		
