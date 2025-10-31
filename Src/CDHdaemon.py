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

#set stdout in line buffering mode
sys.stdout.reconfigure(line_buffering=True)


stopThreads=threading.Event() #thread safe flag to signal to all threads to stop
threadTermTimeout=3 #timeout for thread join() after termination

sys.path.append("./Threads")
import Threads.ADCThread
import Threads.CDHThread
import Threads.ClientThread
import Threads.LogThread

#running all threads
print("Starting threads")
adcT=threading.Thread(target=Threads.ADCThread.adcThread,args=(stopThreads,), daemon=True)
cliT=threading.Thread(target=Threads.ClientThread.clientThread,args= (stopThreads,), daemon=True)	
cdhT=threading.Thread(target=Threads.CDHThread.cdhThread,args=(stopThreads,), daemon=True)	
logT=threading.Thread(target=Threads.LogThread.logThread,args = (stopThreads,), daemon=True)
	
adcT.start()
cliT.start()
cdhT.start()
logT.start()

print("All threads started")

def stop_handler(sig, frame): #handler function for stop signals

	stopThreads.set() #stopping all threads
	
	print("Received termination signal")
	
	#waiting for all threads to join
	adcT.join(timeout=threadTermTimeout)
	cliT.join(timeout=threadTermTimeout)
	cdhT.join(timeout=threadTermTimeout)
	logT.join(timeout=threadTermTimeout)
	
	print("All threads terminated or timed out, BYE!")
	sys.exit()
	
#setting signal handler
signal.signal(signal.SIGTERM, stop_handler)
signal.signal(signal.SIGINT, stop_handler)

while 1:
	#checking if all threads are still alive
	allAlive=True
	if not adcT.is_alive():
		allAlive=False
	if not cliT.is_alive():
		allAlive=False
	if not cdhT.is_alive():
		allAlive=False
	if not logT.is_alive():
		allAlive=False
		
	if not allAlive:
		print("A thread unexpectedly closed, terminating execution")
		os.kill(os.getpid(),signal.SIGTERM)
	
	time.sleep(1)
			
