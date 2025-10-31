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
print(f"{LIGHT_BLUE}-"*25)
print(f"{LIGHT_BLUE}| TEST PHASE --> BASIC  |")
print("-"*25)
print("Testing:")
print("- EPS connection: test if connection with EPS works")
print("- AOCS connection: test if connection with AOCS works both TX and RX")
print ("- COMMSYS connection: test if connection with COMMSYS works both TX and RX{RESET}")
print()
#set stdout in line buffering mode
sys.stdout.reconfigure(line_buffering=True)

AOCStestStatus= True
EPStestStatus = True
COMMSYStestStatus = True
LOGtestStatus = True

threadTermTimeout=3 #timeout for thread join() after termination
stopThreads= threading.Event()
sys.path.append("./Threads")
import Threads.EPSThread
import Threads.AOCSThread
import Threads.COMMSYSThread
import Threads.LogThread

#running all threads
print(f"{WHITE}Starting threads")

epsT=threading.Thread(target=Threads.EPSThread.adcThread,args=(stopThreads,), daemon=True)
#aocsT=threading.Thread(target=Threads.AOCSThread.aocsThread,args=(AOCStestStatus,), daemon=True)	
#logT=threading.Thread(target=Threads.LogThread.logThread,args = (LOGtestStatus,), daemon=True)
#cmsysT=threading.Thread(target=Threads.COMMSYSThread.commsysThread, args=(COMMSYStestStatus,),daemon=True)

epsT.start()
# aocsT.start()
# logT.start()
# cmsysT.start()

print("All threads started")



#Waiting for threads to end

#aocsT.join(timeout=threadTermTimeout)
#logT.join(timeout=threadTermTimeout)
#cmsysT.join(timeout=threadTermTimeout)
epsT.join(timeout=threadTermTimeout)

def stop_handler(sig, frame): #handler function for stop signals
	#global stopThreads
	#global adcT
	global cliT
	global cdhT
	global logT
	global threadTermTimeout

	print("Received termination signal")
	
	#waiting for all threads to join
	epsT.join(timeout=threadTermTimeout)
	# cliT.join(timeout=threadTermTimeout)
	# cdhT.join(timeout=threadTermTimeout)
	# logT.join(timeout=threadTermTimeout)
	
	print("All threads terminated or timed out previously, test produces no result")
	sys.exit()
	
#setting signal handler
signal.signal(signal.SIGTERM, stop_handler)
signal.signal(signal.SIGINT, stop_handler)
print()
print()
#Check test result

while 1:
	#checking if all threads are still alive
	allAlive=True
	if not epsT.is_alive():
		allAlive=False
	# if not cliT.is_alive():
	# 	allAlive=False
	# if not cdhT.is_alive():
	# 	allAlive=False
	# if not logT.is_alive():
	# 	allAlive=False
		
	if not allAlive:
		print("A thread unexpectedly closed, terminating execution")
		os.kill(os.getpid(),signal.SIGTERM)
	
	time.sleep(1)

if AOCStestStatus and COMMSYStestStatus and EPStestStatus and LOGtestStatus:
	print(f"{GREEN}TEST PASSED SUCCESSFULLY")
	sys.exit()
else:
	print(f"{RED} TEST FAILED: Something wrong happens, check previous messages!")
	sys.exit()			
