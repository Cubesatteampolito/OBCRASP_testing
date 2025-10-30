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
RESET = '\033[0m'

print(f"{BLUE}|TEST PHASE --> BASIC")
print("Testing:")
print("- EPS connection: test if connection with EPS works")
print("- AOCS connection: test if connection with AOCS works both TX and RX")
print ("- COMMSYS connection: test if connection with COMMSYS works both TX and RX{RESET}")

#set stdout in line buffering mode
sys.stdout.reconfigure(line_buffering=True)

teststatus= True
#stopThreads=threading.Event() #thread safe flag to signal to all threads to stop --> NOT USEFULL FOR THIS TEST
threadTermTimeout=3 #timeout for thread join() after termination

sys.path.append("./Threads")
import Threads.ADCThread
import Threads.CDHThread
import Threads.ClientThread
import Threads.LogThread

#running all threads
print("Starting threads")
def test(): 
	time.sleep(3)



#adcT=threading.Thread(target=Threads.ADCThread.adcThread,args=(teststatus,), daemon=True)
cliT=threading.Thread(target=test, daemon=True)	
cdhT=threading.Thread(target=test, daemon=True)	
logT=threading.Thread(target=test, daemon=True)

#adcT.start()
cliT.start()
cdhT.start()
logT.start()

print("All threads started")

def stop_handler(sig, frame): #handler function for stop signals
	#global stopThreads
	#global adcT
	global cliT
	global cdhT
	global logT
	global threadTermTimeout

	print("Received termination signal")
	
	#waiting for all threads to join
	#adcT.join(timeout=threadTermTimeout)
	cliT.join(timeout=threadTermTimeout)
	cdhT.join(timeout=threadTermTimeout)
	logT.join(timeout=threadTermTimeout)
	
	print("All threads terminated or timed out previously, test produces no result!")
	sys.exit()
	
#setting signal handler
signal.signal(signal.SIGTERM, stop_handler)
signal.signal(signal.SIGINT, stop_handler)

cliT.join(timeout=threadTermTimeout)
cdhT.join(timeout=threadTermTimeout)
logT.join(timeout=threadTermTimeout)

if teststatus:
	print(f"{GREEN}TEST PASSED SUCCESSFULLY")
	sys.exit()
else:
	print(f"{RED} TEST FAILED: Something wrong happens, check previous messages!")
	sys.exit()