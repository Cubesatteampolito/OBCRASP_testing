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
#Client thread ------------------------
cdhSockPath="/tmp/CDH.sock"
clientQueueTx=queue.Queue() #queue to send data to client
clientQueueTxTimeout=0.1 #timeout for reading from client tx queue
clientQueueRx=queue.Queue() #queue to receive data from client
uartTimeout=0.100 # timeout for uart transmission with ack
uartRetries=2 #number of retries in case of failed ack (total 3 tries)
#--------------------------------------

def clientThread(stopThreads):
	print("Client thread started")
	
		
	server=None
	#creating socket for client
	print("Creating client socket")
	try:
		if os.path.exists(cdhSockPath):
			os.remove(cdhSockPath)
	
		server=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
		server.bind(cdhSockPath)
		server.setblocking(False)
	except:
		print("ERROR: Failed to create client socket {0}".format(cdhSockPath))
	
	addr=None
	
	while 1:
		if stopThreads.is_set(): #need to close thread
			break
			
		#try receiving data from client socket
		try:
			datain,addr=server.recvfrom(4096)
		except BlockingIOError:
			pass #if timeout reached don't do anything
		except: #other exceptions
			print("ERROR: Failed to read from client socket, trying to recreate socket")
			try:
				if os.path.exists(cdhSockPath):
					os.remove(cdhSockPath)
			
				server=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
				server.bind(cdhSockPath)
				server.setblocking(False)
			except:
				print("ERROR: Failed to create client socket {0}".format(cdhSockPath))
		else:
			clientQueueRx.put(datain.decode("utf-8"))
			
		#see if there's some output for client
		try:
			dataout=clientQueueTx.get(timeout=clientQueueTxTimeout)
		except: #nothing to get
			pass
		else:
			try:
				server.sendto(dataout.encode("utf-8"),addr)
			except: #in case client was closed or other errors, just ignore the output
				pass

	print("Closing and deleting client socket")
	try:
		server.close()
	except:
		pass
	
	try:
		os.remove(cdhSockPath)
	except:
		pass	
		
