#!/usr/bin/env python2
import Queue
import threading
import time
import sys
import struct
import socket
import string
import re
import string
import select
import datetime 
import signal

MPD_TCP_IP = '192.168.1.2'
MPD_TCP_PORT = 6600
BUFFER_SIZE = 4096

POWERMATE = "/dev/input/by-id/usb-Griffin_Technology__Inc._Griffin_PowerMate-event-if00"

q = Queue.Queue()

#must make sure you have permissions for actuall event rather than symbolic link

#INPUT:
#type 2, code 7, value is knob change, Pos for CW, Neg (see next line) for CCW
#iTurn=value
#if (value & 0x80000000):
#	iTurn = -0x100000000 + value # flips number to tegatave rather than turned over int.
#	
#type 1, code 256, value is 1 - button down; 0 - button up
#OUTPUT:
#type 4: code 1, value is light level 0-256
"""
LoopTimer----------------------------------------------------------------------------------------------------------------------------
"""
class LoopTimer: #given a LoopLenth will sleep the ammount to have the time between calls be that loop lenght
#does nothing if the time from last call is longer than LoopLenght
	def __init__(self,DesiredLoopSpeed=1.0/30.0):
		self.fLoopLenght=DesiredLoopSpeed
		self.fLoopStartTime=time.time()	
		self.fThisLoopTime=0.0
		self.rTime=0.0
	def DelayTillTime(self):
		self.rTime = self.GetRemainingTime()
		if self.rTime > 0.0:
			time.sleep(self.rTime)
		else:
			print "Long Loop"
		self.fLoopStartTime = time.time()
		return self.rTime
	def GetRemainingTime(self):
		nTime = time.time()
		lTime = nTime  - self.fLoopStartTime
		return self.fLoopLenght - lTime
"""
Real MPD------------------------------------------------------------------------------------------------------------------------
"""
class MPDPlayBack:
	MAXSYNCFREEQ = 0.001 #seconds
	MAXUNSYNCTIME = 4.0 #seconds
	MAXSOCKETTIME = 2.0 #seconds
	def __init__(self, ipMPD, portMPD):
		self.ipMPD = ipMPD
		self.portMPD = portMPD
		self.lastSyncTime = 0
		self.vol = 0
		self.playing = False
		self.rand = False
		self.needToSendUpDate = False
		self.sMPD = self.MPDConnectAndCheck()
		self.trackChange = 0 #pos is forward, neg is back
		self.thinkSocketOpen = False
		self.sockInUse = False
		if (self.sMPD):
			print "MPD connect OK"
			self.UpdateFromMPD(self.sMPD)
			self.CloseMPDSock()
		print "RealCont"
	def Update(self, tDelta):
		if self.needToSendUpDate:
			if (time.time() - self.lastSyncTime) > self.MAXSYNCFREEQ:
				sockMPD = self.ReviveSocket()
				if (sockMPD):
					self.SendToMPD(sockMPD)
		elif (time.time() - self.lastSyncTime) > self.MAXUNSYNCTIME:
			sockMPD = self.ReviveSocket()
			if (sockMPD):
				self.UpdateFromMPD(sockMPD)
		if ((time.time() - self.lastSyncTime) > self.MAXSOCKETTIME) and self.thinkSocketOpen:
			self.CloseMPDSock()
	def GetVol(self):
		return self.vol
	def ChangeVol(self, changeAmnt):
		self.vol = self.vol + changeAmnt
		self.vol = max(0, min(self.vol, 100))
		print "volume set to: "+ str(self.vol)
		self.needToSendUpDate = True
		return self.vol
	def Pause(self):
		self.needToSendUpDate = True
		self.playing = False
	def StartPlaying(self):
		self.needToSendUpDate = True
		self.playing = True
	def ToggleRandom(self):
		self.needToSendUpDate = True
		self.rand = not self.rand
	def TogglePlay(self):
		self.needToSendUpDate = True
		self.playing = not self.playing
	def NextTrack(self):
		self.trackChange = self.trackChange + 1
		self.needToSendUpDate = True
	def PrevTrack(self):
		self.trackChange = self.trackChange - 1
		self.needToSendUpDate = True
	def UpdateFromMPD(self, sockMPD):#pass connected / checked mpd socket
		self.lastSyncTime = time.time()
		self.vol = self.GetMPDvol(self.sMPD)
		self.playing = self.GetMPDisPlaying(self.sMPD)
		self.rand = self.GetMPDisRandom(self.sMPD)
	def SendToMPD(self, sockMPD):
		self.lastSyncTime = time.time()
		sendString = "command_list_begin\n"
		sendString = sendString + self.GenVolumeString(self.vol)
		if self.playing:
			sendString = sendString + "play\n"
		else:
			sendString = sendString + "pause 1\n"
		if self.rand:
			sendString = sendString + "random 1\n"
		else:
			sendString = sendString + "random 0\n"
		if self.trackChange > 0:
			sendString = sendString + "next\n"
			self.trackChange = self.trackChange - 1
		elif self.trackChange < 0:
			sendString = sendString + "previous\n"
			self.trackChange = self.trackChange + 1
		if self.trackChange == 0:
			self.needToSendUpDate = False
		sendString = sendString + "command_list_end\n"
		#self.SendMPDStringNoRet(sockMPD, sendString)
		t = threading.Thread(target=self.SendMPDStringNoRet, args = (sockMPD, sendString))
		t.daemon = True
		t.start()
	def ReadWithTimeout(self, ConnectedSocket, sTimeOut = 4):#pass connected socket with waiting response
		ready = select.select([ConnectedSocket], [], [], sTimeOut)
		data = 0
		if ready[0]:
			data= ConnectedSocket.recv(BUFFER_SIZE)
		return data
	def ParseMPDreturn(self, mpdRecev, ValueWanted): #pass mpd 'status' return + term
		rVal = 0
		if mpdRecev != 0:
			mpdRecev = mpdRecev.split('\n')
			for line in mpdRecev:
			#	print line
				if re.search(ValueWanted+":", line):
				      rVal = line
		if rVal != 0:
			rVal = rVal.split(': ')
			rVal = rVal[1]
		return rVal
	def ReviveSocket(self):
		if self.thinkSocketOpen:
			return self.sMPD
		else:
			return self.MPDConnectAndCheck()
	def CloseMPDSock(self):
		self.thinkSocketOpen = False
		self.sMPD.close()
		#print "MPD socket closed"
	def MPDConnectAndCheck(self):
		sockMPD = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sockMPD.setblocking(0)
		sockMPD.settimeout(40)
		try:
			sockMPD.connect((self.ipMPD, self.portMPD))
			mpdStartline = self.ReadWithTimeout(sockMPD) #reed "mpd ok" line
			mpdStartline = mpdStartline.split(' ')
			if mpdStartline[0] == 'OK':
				self.thinkSocketOpen = True
				self.sMPD = sockMPD
				#print "MPD socket opened"
				return sockMPD
			else:
				print 'MPD down'
				return False
			
		except:
			print "MPD way way down"
			return False		
	def MPDGetValue(self, sockMPD, stValue): #pass connected / checked mpd socket and status name
		mpdStatus = self.GetMPDstatus(sockMPD)
		return self.ParseMPDreturn(mpdStatus, stValue)
	def MPDStop(self,sockMPD): #pass connected / checked mpd socket
		self.SendMPDString(sockMPD,"stop\n")
		return	
	def GetMPDvol(self, sockMPD): #pass connected / checked mpd socket
		return int(self.MPDGetValue(sockMPD, 'volume'))
	def SetMPDvol(self, sockMPD, newVol):#pass connected / checked mpd socket
		vString = self.GenVolumeString(newVol)
		self.SendMPDString(sockMPD,vString)
	def GenVolumeString(self, newVol):
		newVol = max(0, min(newVol, 100))
		vString = 'setvol '+ str(newVol)+'\n'
		return vString
	def SendMPDStringNoRet(self, sockMPD, stringToSend):
		while self.sockInUse:
			time.sleep(0.01)
		self.sockInUse = True
		self.SendMPDString(sockMPD, stringToSend)
		self.ReadWithTimeout(sockMPD)
		self.sockInUse = False
	def SendMPDString(self, sockMPD, stringToSend): #pass connected / checked mpd socket
		sockMPD.send(stringToSend.encode('utf-8'))
	def GetMPDstatus(self, sockMPD): #pass connected / checked mpd socket
		self.SendMPDString(sockMPD,"status\n")
		return self.ReadWithTimeout(sockMPD)
	def GetMPDisPlaying(self, sockMPD):#pass connected / checked mpd socket
		bPlay = self.MPDGetValue(sockMPD,"state")
		if bPlay == 'play':
			return True
		else:
			return False
	def GetMPDisRandom(self, sockMPD):#pass connected / checked mpd socket
		bPlay = self.MPDGetValue(sockMPD,"random")
		if bPlay == '1':
			return True
		else:
			return False
	def SetMPDRandom(self, sockMPD, bRand):#pass connected / checked mpd socket
		if bRand:
			self.SendMPDString(sockMPD,"random 1\n")
		else:
			self.SendMPDString(sockMPD,"random 0\n")
	def GetMPDsongPlaying(self, sockMPD):#pass connected / checked mpd socket
		self.SendMPDString(sockMPD, "currentsong\n")
		songDat = self.ReadWithTimeout(sockMPD)
		songName = self.ParseMPDreturn(songDat, "Title")
		if songName == 0:
			songName = self.ParseMPDreturn(songDat, "file")
		print "*** " + songName + " ***"
		return songName
"""
Knob input and output   ------------------------------------------------------------------------------------------
"""
class KnobHandler:
#long int, long int, unsigned short, unsigned short, unsigned int
	FORMAT = 'llHHI'
	EVENT_SIZE = struct.calcsize(FORMAT)
	MODECHANGEDELAY = 1.0
	TRACKDELAY = 0.25
	PULSESPEED = 4.50 # PULSESPEED times per Second
	BADRUNSALLOWED=10
	FLASHNUM=2
	def __init__(self, infile_path, pb):
		self.runThreads = True
		self.curPulseSpeed = self.PULSESPEED
		self.curMaxPulse = 255
		self.lastEventAt=time.time()
		self.playBack = pb
		self.buttonTimerStart = time.time()
		self.in_file = 0
		self.out_file = 0
		self.filePath = infile_path
		self.badRuns = self.BADRUNSALLOWED
		self.OpenInputOutPut()
		self.iPosPlace=0
		self.curEvent = ""
		self.bKnobDown = 0
		self.bKnobVal = 0
		self.knobInputMode = 99 # 1 is vol / pause play / 2 is fwd bkw
		self.lightVolValue = int((self.playBack.GetVol()/100.0)*240)+15
		self.lastTrackChange=time.time()
		self.pulseDirecton = 1 # 1 up zero down
		self.UptateTimer = 0.0
		self.flashCount = self.FLASHNUM
		#mode Prep
		self.EventKnobTurn=0
		self.EventKnobUpDown=0
		self.LightMode=0
		self.UpdateMode=0
		self.lastLightValue = -1
		self.ChangeMode(1)
		self.LastLightMode=self.LightMode
	def __exit__(self):
		self.in_file.close()
		self.out_file.close()
	def OpenInputOutPut(self):
		self.in_file = 0
		self.out_file = 0
		self.lastLightValue = -1
		print "Atempting to load input output File"
		try:
			self.in_file = open(self.filePath, "rb")
			self.out_file = open(self.filePath, "wb")
			self.badRuns = self.BADRUNSALLOWED
			print "Sucsess"
		except:
			self.badRuns = self.badRuns - 1	
			if (self.badRuns > 0):
				print "Could not Open input output Files, check Plug and permissions. \n"+ str(self.badRuns)+ " more attempts."
				print "Failed to reatach, giving up. Attempting to exit cleanly"
	def GetEvent(self):
		self.curEvent = self.in_file.read(self.EVENT_SIZE)
		return self.curEvent
	def GetEventNB(self): #non blocking
		ready = select.select([self.in_file], [], [], 2)
		if ready:
			self.curEvent = self.in_file.read(self.EVENT_SIZE)
			return self.curEvent
		else:
			return 0
	def HandleEvent(self,event):
		(tv_sec, tv_usec, type, code, value) = struct.unpack(self.FORMAT, event)
		if (type != 0 or code != 0 or value != 0) and type != 4:
			self.lastEventAt=time.time()
			#print("input Event type %u, code %u, value: %u at %d, %d" % (type, code, value, tv_sec, tv_usec))
			if code==7: #knob turned
				self.EventKnobTurn(value)
			elif code == 256: #knob down or up
				self.EventKnobUpDown(value)
	def ChangeMode(self, newMode):
		if self.knobInputMode == newMode:
			return
		else:
			self.knobInputMode = newMode
			print "New Mode: "+str(newMode)
			self.bKnobDown=3
			self.buttonTimerStart = time.time()
			self.lastEventAt = time.time()
			if newMode == 1:
				self.LightMode = self.SyncVolWithLight
				self.EventKnobTurn=self.EventKnobTurnModeOne
				self.EventKnobUpDown=self.EventKnobUpDownModeOne
				self.UpdateMode=self.UpdateModeOne
			elif newMode == 2:
				self.curMaxPulse = self.lightVolValue
				self.LightMode = self.PulseLight
				self.EventKnobTurn=self.EventKnobTurnModeTwo
				self.EventKnobUpDown=self.EventKnobUpDownModeTwo
				self.UpdateMode=self.UpdateModeTwo
	def EventKnobUpDownModeOne(self, updown):
		prevKnob=self.bKnobDown
		self.bKnobDown=updown
		if self.bKnobDown == 1:
			self.buttonTimerStart = time.time()
			print "button down"
		elif prevKnob != 3:
			timeDown =  time.time() - self.buttonTimerStart
			print "button up, down for " + str(timeDown) + " seconds."
			if timeDown < self.MODECHANGEDELAY:
					self.playBack.TogglePlay()
					#self.StartFlash()
	def EventKnobUpDownModeTwo(self, updown):
		prevKnob=self.bKnobDown
		self.bKnobDown=updown
		if self.bKnobDown == 1:
			self.buttonTimerStart = time.time()
			print "button down"
		elif prevKnob != 3:
			print "mode 2 knob up"
			self.playBack.ToggleRandom()
			self.StartFlash()
	def EventKnobTurnModeOne(self, ammnt):
		iTurn = self.FixKnobAmmnt(ammnt)
		if self.bKnobDown==1:
			print "KnobDown " + str(iTurn)
			self.ChangeMode(2)
		else:
			bPlaying = self.playBack.playing
			curVol = self.playBack.ChangeVol(iTurn)######
			if curVol == 100:
				self.StartFlash()
			if ((iTurn > 0) and not bPlaying):
				self.playBack.StartPlaying()
			if (curVol == 0 and bPlaying):
				print ("..")
				self.playBack.Pause()			
	def EventKnobTurnModeTwo(self, ammnt):
		iTurn = self.FixKnobAmmnt(ammnt)
		self.TrackChange(iTurn)
		print "-"
	def FixKnobAmmnt(self,ammnt):
		iTurn=ammnt
		if (ammnt & 0x80000000):
			iTurn = -0x100000000 + ammnt
		return iTurn
	def TrackDelayCheck(self):
		timeSince = time.time() - self.lastTrackChange 
		if timeSince > self.TRACKDELAY:
			return True
		else:
			return False
	def TrackChange(self, iTurn):
		if self.TrackDelayCheck():
			self.lastTrackChange=time.time()
			if iTurn > 0:
				self.playBack.NextTrack()
			else:
				self.playBack.PrevTrack()
	def UpdateModeOne(self, tDelta):
		if self.bKnobDown == 1:
			timeDown =  time.time() - self.buttonTimerStart
			if (timeDown > self.MODECHANGEDELAY):
				self.ChangeMode(2)
	def UpdateModeTwo(self, tDelta):
		self.curPulseSpeed = self.PULSESPEED
		timeSinceLastEvent = time.time() - self.lastEventAt
		print str(timeSinceLastEvent)
		mcDelTime = float(5 * self.MODECHANGEDELAY)
		pulseSpeedMod = 1.0 - ((mcDelTime - timeSinceLastEvent)/mcDelTime)
		pulseSpeedMod = (((pulseSpeedMod*pulseSpeedMod*pulseSpeedMod)*20.0) + 1)
		self.curPulseSpeed = self.PULSESPEED * pulseSpeedMod
		if self.bKnobDown == 1:
			timeDown =  time.time() - self.buttonTimerStart
			if (timeDown > self.MODECHANGEDELAY):
				self.ChangeMode(1)
		elif ((timeSinceLastEvent) > (mcDelTime)):
			self.ChangeMode(1)
	def Update(self, tDelta):
		self.LightMode(tDelta)
		self.UpdateMode(tDelta)	
		self.UptateTimer = self.UptateTimer + tDelta
		if (self.UptateTimer > 60.0):
			print "one min"
			self.UptateTimer = 0.0
	def PulseLight(self, tDelta):
		maxLight = self.curMaxPulse
		lightChange = int((tDelta * maxLight) * self.curPulseSpeed)
		newLight = self.lightVolValue
		if self.pulseDirecton == 1:
			newLight = self.lightVolValue + lightChange
			if newLight > maxLight:
				newLight = maxLight
				self.pulseDirecton = 0
		else:
			newLight = self.lightVolValue - lightChange
			if newLight < 0:
				newLight = 0
				self.pulseDirecton = 1
		self.lightVolValue = newLight
		self.SetLight(newLight)
	def SyncVolWithLight(self,tDelta=0):
		if (self.playBack.playing):
			self.lightVolValue=int((self.playBack.GetVol()/100.0)*240)+15
		else:
			self.lightVolValue=2
		self.SetLight(self.lightVolValue)
	def StartFlash(self):
		if(self.LightMode != self.FlashLight): #startFlash
			self.LastLightMode = self.LightMode
		self.flashCount = self.FLASHNUM
		self.pulseDirecton = 1
		self.lightVolValue = 0
		self.LightMode = self.FlashLight
	def FlashLight(self, tDelta=0):
		bDone = False
		newLight = self.lightVolValue
		lightChange = int((tDelta * 255) * 30)
		newLight = self.lightVolValue
		if self.pulseDirecton == 1:
			newLight = self.lightVolValue + lightChange
			if newLight > 255:
				newLight = 255
				self.pulseDirecton = 0
		else:
			newLight = self.lightVolValue - lightChange
			if newLight < 0:
				newLight = 0
				self.pulseDirecton = 1
				if self.flashCount <= 1:
					bDone=True
				else:
					self.flashCount = self.flashCount - 1
		self.lightVolValue = newLight
		self.SetLight(newLight)
		if bDone:
			self.LightMode = self.LastLightMode
	def SetLight(self, lightValue):
		lightValue = max(0, min(lightValue, 255))
		if (self.lastLightValue == lightValue):
			return
		else:
			self.lastLightValue = lightValue
			OutDat=struct.pack(self.FORMAT,0,0,0x4,0x01,lightValue)
			(tv_sec, tv_usec, type, code, value) = struct.unpack(self.FORMAT, OutDat)
			try:
				self.out_file.write(OutDat)
				self.out_file.flush()
			except:
				print "Cannot Write To Output"
	def EventChecker(self, q, eventListQueue): # for threadding
		thisThread = True
		while self.runThreads and thisThread:
			try:
				event = self.GetEvent()
				eventListQueue.append(event)
			except:
				print "Device Down (check permissions and plug), sleeping for 5 seconds"
				time.sleep(5)
				self.OpenInputOutPut()
				if self.badRuns < 1:
					thisThread = False
		print self.EventChecker.__name__ + " Thread quitting"
"""
force quitting:------------------------------------------------------------------------------------------------------------------------
"""
def signal_handler(signum, frame):
	print("W: custom interrupt handler called.")
"""
"""
pb = MPDPlayBack(MPD_TCP_IP,MPD_TCP_PORT)
kh = KnobHandler(POWERMATE, pb)
lt = LoopTimer()
eventList = []
"""
start threads
"""

t = threading.Thread(target=kh.EventChecker, args = (q,eventList))
t.daemon = True
t.start()
"""
"""
def signal_handler(signum, frame):
	print("Ctrl+Z")
	kh.runThreads=False
	sys.exit()
"""
loop
"""
loopTime = 10.0
signal.signal(signal.SIGTSTP, signal_handler)

bRun = True
print "Start up over, entering loop"
while bRun:
	try:
		kh.Update(loopTime)
		pb.Update(loopTime)
		while len(eventList) > 0:
			event = eventList.pop()
			kh.HandleEvent(event)
		loopTime = lt.DelayTillTime()
		if threading.active_count() == 1:
			print "All Polling Threads Dead"
			bRun = False
	except (KeyboardInterrupt, SystemExit):
		print("got Ctrl+C (SIGINT) or exit() is called")
		bRun = False
		kh.runThreads=False
print "exiting"
time.sleep(0.25)


