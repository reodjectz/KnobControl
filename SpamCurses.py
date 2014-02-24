#!/usr/bin/env python2
import curses
import time
import Queue
import threading

class LoopTimer: #given a LoopLenth will sleep the ammount to have the time between calls be that loop lenght
#does nothing if the time from last call is longer than LoopLenght
	def __init__(self,DesiredLoopSpeed=1.0/30.0):
		self.fLoopLenght=DesiredLoopSpeed
		self.fLoopStartTime=time.time()	
		self.fThisLoopTime=0.0
		self.rTime=0.0
	def DelayTillTime(self):
		nTime = time.time()
		lTime = nTime  - self.fLoopStartTime
		self.rTime = self.fLoopLenght - lTime
		if self.rTime > 0.0:
			time.sleep(self.rTime)
		self.fLoopStartTime = time.time()
		return nTime


def PopulateColorPairs():
	iC=1
	curses.init_pair(iC, curses.COLOR_BLACK, -1);iC=iC+1
	curses.init_pair(iC, curses.COLOR_BLUE, -1);iC=iC+1
	curses.init_pair(iC, curses.COLOR_CYAN, -1);iC=iC+1
	curses.init_pair(iC, curses.COLOR_GREEN, -1);iC=iC+1
	curses.init_pair(iC, curses.COLOR_MAGENTA, -1);iC=iC+1
	curses.init_pair(iC, curses.COLOR_RED, -1);iC=iC+1
	curses.init_pair(iC, curses.COLOR_WHITE, -1);iC=iC+1
	curses.init_pair(iC, curses.COLOR_YELLOW, -1);iC=iC+1
	curses.init_pair(iC, curses.COLOR_BLACK, curses.COLOR_BLUE);iC=iC+1
	curses.init_pair(iC, curses.COLOR_BLACK, curses.COLOR_CYAN);iC=iC+1
	curses.init_pair(iC, curses.COLOR_BLACK, curses.COLOR_GREEN);iC=iC+1
	curses.init_pair(iC, curses.COLOR_BLACK, curses.COLOR_MAGENTA);iC=iC+1
	curses.init_pair(iC, curses.COLOR_BLACK, curses.COLOR_RED);iC=iC+1
	curses.init_pair(iC, curses.COLOR_BLACK, curses.COLOR_WHITE);iC=iC+1
	curses.init_pair(iC, curses.COLOR_BLACK, curses.COLOR_YELLOW);iC=iC+1
	curses.init_pair(iC, curses.COLOR_RED, curses.COLOR_MAGENTA);iC=iC+1
	
	return iC
def PrepWin(pwin, wcol=0):
	pwin.clear()
	pwin.attron(curses.color_pair(wcol))
	pwin.box()
	pwin.attroff(curses.color_pair(wcol))
	pwin.refresh()

def FrontCutTo(sTring, iLenght):
	sDif=len(sTring) - iLenght
	if (sDif > 0):
		sTring = sTring.lstrip(sTring[:sDif])
	return sTring

def StringProgBar(iWidth, fValue,endbars=True):
	BarSeg=iWidth-2.0
	FillSegs=int(BarSeg*(fValue / 100.0))
	BarSeg = int(BarSeg)
	if endbars:
		retBar="["
	else:
		retBar=""
	for x in range (0,BarSeg):
		if x < FillSegs:
			retBar = retBar + '|'
		else:
			retBar = retBar + '-'
	if endbars:
		retBar = retBar + ']'
	return retBar

def ProgBar(iLineStart,iColStart,iWidth,fValue, CursesWindow):#you must call refresh
	BarStr=StringProgBar(iWidth,fValue,False)
	CursesWindow.addstr(iLineStart,iColStart,"[", curses.color_pair(7))
	CursesWindow.addstr(iLineStart,iColStart+1,BarStr, curses.color_pair(6))
	CursesWindow.addstr(iLineStart,iColStart+iWidth-1,"]", curses.color_pair(7))

def main(stdscr,Atrib):
	stdscr.nodelay(1)
	stdscr.refresh()
	AddString=" "
	bGo=True
	ix=0
	curses.use_default_colors()
	curses.curs_set(0)
	(winyl,winxl) = stdscr.getmaxyx()
	curses.start_color()
	dPair = PopulateColorPairs()
	sTime = time.time()
	llTime = time.time()
	(winy,winx) = stdscr.getmaxyx()
	win1=curses.newwin(winy/2,winx,0,0)
	win2=curses.newwin(winy/2,winx,winy/2,0)

	bReSize=False
	PrepWin(win1,3)
	PrepWin(win2,10)
	lt=LoopTimer(1.0/30.0)
	bStr="."
	bScrollText="Whether in Russia for Olympic athletes or New England for winter vacationers, snowmakers work hard to produce the solid base and dusty powder that can supplement, or in some cases supplant, nature and make for quality skiing. If there is an art to getting good snow from a machine, it is based on a thorough understanding of the science, especially the role of temperature and humidity in the process."
	strDot=unichr(387)
	iScrolTextInt=0
	ScrollPerSec=020.50
	bScr=" "
	fScrollTimer=0.0
	fRunTime=0
	win1Cnt=0
	while bGo:
		ch=stdscr.getch()
		while ch != -1:
			if (ch == ord('q')):
				bGo=False
			elif (ch == ord('j')):
				ScrollPerSec = ScrollPerSec + 0.1
				if ScrollPerSec > 100.0:
					ScrollPerSec = 100.0
			elif (ch == ord('m')):
				ScrollPerSec = ScrollPerSec - 0.1
				if ScrollPerSec < 0.001:
					ScrollPerSec = 0.001
			elif ((ch < 255) and not (ch == ord('\n'))):
				bStr=bStr+unichr(ch)
				bStr = FrontCutTo(bStr, 10)
				win1.addstr(2,2,bStr)
				win1.refresh()
			if (ch == curses.KEY_RESIZE):
				bReSize=True
			ch=stdscr.getch()	
		if bReSize:
			(winy,winx) = stdscr.getmaxyx()
			win1.resize(winy/2,winx)
			win2.resize(winy/2,winx)
			win2.mvwin(winy/2,0)
			PrepWin(win1,3)
			PrepWin(win2,10)
			bReSize=False
		win2.addstr(2,2,"tm: " + str(lt.rTime))
		fRunTime = fRunTime + lt.rTime
		win2.addstr(2,30,"run time: " + str(fRunTime)[:6],curses.color_pair(5) )
		nScroll=False
		while (fScrollTimer > 1.0/ScrollPerSec):
			fScrollTimer  = fScrollTimer - 1.0/ScrollPerSec
			if iScrolTextInt >= len(bScrollText):
				iScrolTextInt = 0
			bScr = bScr + bScrollText[iScrolTextInt];iScrolTextInt=iScrolTextInt+1
			bScr = FrontCutTo(bScr, 30)
			nScroll=True
		if nScroll:
			win1.addstr(3,10,bScr, curses.color_pair(6))
			win1.addstr(4,10,str(win1Cnt), curses.color_pair(7))
			win1Cnt=win1Cnt+1
			win1.refresh()	
		win2.addstr(4,2,"Scroll Per Sec: "+ str(ScrollPerSec) , curses.color_pair(4))
		ProgBar(5,2,21,ScrollPerSec,win2)
		win2.refresh()
		
		fScrollTimer = fScrollTimer + lt.rTime
		lt.DelayTillTime()
curses.wrapper(main,0)
