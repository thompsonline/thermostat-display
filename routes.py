#!/usr/bin/env python


from flask import *
from flask.ext.basicauth import BasicAuth
from flaskext.mysql import MySQL
from flaskext.lesscss import lesscss
import subprocess
import rpi_backlight as bl

import logging
import logging.handlers

import ConfigParser

import os
import sys
import time

import datetime
import cPickle as pickle

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

config = ConfigParser.ConfigParser()
config.read(dname+"/config.txt")

LOG_LOGFILE = config.get('logging', 'logfile')
logLevelConfig = config.get('logging', 'loglevel')
if logLevelConfig == 'info':
    LOG_LOGLEVEL = logging.INFO
elif logLevelConfig == 'warn':
    LOG_LOGLEVEL = logging.WARNING
elif logLevelConfig ==  'debug':
    LOG_LOGLEVEL = logging.DEBUG

LOGROTATE = config.get('logging', 'logrotation')
LOGCOUNT = int(config.get('logging', 'logcount'))

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LOGLEVEL)
handler = logging.handlers.TimedRotatingFileHandler(LOG_LOGFILE, when=LOGROTATE, backupCount=LOGCOUNT)
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class MyLogger(object):
        def __init__(self, logger, level):
                self.logger = logger
                self.level = level

        def write(self, message):
                # Only log if there is a message (not just a new line)
                if message.rstrip() != "":
                        self.logger.log(self.level, message.rstrip())


app = Flask(__name__)
lesscss(app)

app.config['BASIC_AUTH_USERNAME'] = config.get('main','authUser')
app.config['BASIC_AUTH_PASSWORD'] = config.get('main','authPass')

app.config['MYSQL_DATABASE_USER'] = config.get('main','mysqlUser')
app.config['MYSQL_DATABASE_PASSWORD'] = config.get('main','mysqlPass')
app.config['MYSQL_DATABASE_DB'] = config.get('main','mysqlDatabase')
app.config['MYSQL_DATABASE_HOST'] = config.get('main','mysqlHost')
app.config['MYSQL_DATABASE_PORT'] = int(config.get('main','mysqlPort'))

PLOTLY_ID1 = os.path.split(config.get('main','plotlyPlot1'))[-1]
PLOTLY_ID2 = os.path.split(config.get('main','plotlyPlot2'))[-1]
PLOTLY_ID3 = os.path.split(config.get('main','plotlyPlot3'))[-1]
PLOTLY_ID4 = os.path.split(config.get('main','plotlyPlot4'))[-1]

WIFIDETECTADDRESS = os.path.split(config.get('main', 'WiFiDetectAddress'))[-1]

DEVELOPING = config.getboolean('main','developing')

if DEVELOPING:
    VIRTUALENV = config.get('main','devEnv')
else:
    VIRTUALENV = config.get('main','deployEnv')


mysql = MySQL()
mysql.init_app(app)
basic_auth = BasicAuth(app)

app.secret_key = config.get('main','secretKey')

def getModeList():
    cursor = mysql.connect().cursor()

    cursor.execute("SELECT mode FROM OperationModes order by displayorder")
    modes=cursor.fetchall()

    cursor.close()

    return [str(mode[0]) for mode in modes]

def getProg():
    cursor = mysql.connect().cursor()

    cursor.execute("SELECT * FROM ProgramTypes")
    prog=cursor.fetchall()

    for pair in prog:
        if pair[1]==1:
            actProg = pair[0]

    cursor.close()

    return actProg

# def getProgTimes(progStr):
#     cursor = mysql.connect().cursor()
#     dayDict = {'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3, 'FRI': 4, 'SAT': 5, 'SUN': 6}
#
#     if progStr == 'Seven Day':
#         cursor.execute("SELECT weekDay,time FROM ManualProgram")
#         progTimes = cursor.fetchall()
#     elif progStr == 'Smart':
#         cursor.execute("SELECT weekDay,time FROM SmartProgram")
#     else:
#         return []
#
#
#     progTimes = [list(pair) for pair in progTimes]
#     progDT = []
#     for pair in progTimes:
#         pair[1] = (datetime.datetime.min + pair[1]).time()
#         pair[0] = next_weekday(dayDict[pair[0]],pair[1])
#
#         progDT.append(datetime.datetime.combine(pair[0],pair[1]))
#
#     # print(progDT)
#     cursor.close()
#
#     return progDT
#
# def next_weekday(weekday,tod):
#     d = datetime.datetime.now()
#     days_ahead = weekday - d.date().weekday()
#
#     if days_ahead < 0: # Target day already happened this week
#         days_ahead += 7
#     if days_ahead == 0:
#         if d.time()>tod:
#             days_ahead += 7
#
#     return d + datetime.timedelta(days_ahead)


def getRoomList():
    cursor = mysql.connect().cursor()

    #cursor.execute("SELECT ModuleID, strDescription FROM ModuleInfo ORDER BY moduleID")
    cursor.execute("SELECT distinct ModuleInfo.ModuleID, ModuleInfo.strDescription, sd.moduleID FROM ModuleInfo  LEFT JOIN (SELECT moduleID, timeStamp FROM SensorData WHERE timestamp > date_sub(now(), interval 15 minute))  sd ON ModuleInfo.moduleID = sd.moduleID ORDER BY ModuleInfo.moduleID")
    rooms = cursor.fetchall()
    
    roomlist = [[room[1],room[0],room[2], "", ""] for room in rooms]
    
    for room in roomlist:
      cursor.execute("SELECT timeStamp, temperature from SensorData where moduleID = %s order by readingID DESC limit 1,1" % room[1]);
      timetemps = cursor.fetchall()
      
      stamp = timetemps[0][0]
      
      room[3] = "%d/%02d/%4d %02d:%02d:%02d" % (int(stamp.month), int(stamp.day), int(stamp.year), int(stamp.hour), int(stamp.minute), int(stamp.second))
      room[4] = int(round(timetemps[0][1]))
      
    cursor.close()
    
    return [[room[1],room[0],room[2], room[3], room[4]] for room in roomlist]

def getProgList():
    cursor = mysql.connect().cursor()

    cursor.execute("SELECT * FROM ProgramTypes")
    programs = cursor.fetchall()

    cursor.close()

    return ([str(prog[0]) for prog in programs if prog[1]==1][0],[str(prog[0]) for prog in programs])


def getThermSet():
    cursor = mysql.connect().cursor()

    cursor.execute("SELECT moduleID, targetTemp, targetMode, expiryTime FROM ThermostatSet")
    thermSet=cursor.fetchall()

    return [thermSet[0][0],thermSet[0][1],thermSet[0][2],thermSet[0][3]]

def getCurrentTemp(curModule):
    cursor = mysql.connect().cursor()
    cursor.execute("SELECT * FROM SensorData WHERE moduleID=%s ORDER BY readingID DESC LIMIT 1" % str(curModule))

    senseData = cursor.fetchall()

    curTemp = senseData[0][4]

    return curTemp

def getCurrentHumid(curModule):
    cursor = mysql.connect().cursor()
    cursor.execute("SELECT * FROM SensorData WHERE moduleID=%s ORDER BY readingID DESC LIMIT 1" % str(curModule))

    senseData = cursor.fetchall()

    curHumid = senseData[0][5]

    return curHumid

def getCurrentState(targTemp,targMode,curRoom,curProg,expTime):
    cursor = mysql.connect().cursor()
    cursor.execute("SELECT * FROM ThermostatLog ORDER BY timeStamp DESC LIMIT 1")

    thermState = cursor.fetchall()

    stateVars = thermState[0][-4:]

    lastReading = thermState[0][0]

    if (datetime.datetime.now()-lastReading).total_seconds() > 600:
        retStr1 = '<span class="message_alert_error">Malfunction</span>'

    else:
        if stateVars == (0, 0, 0, 0):
            retStr1 = 'Idle. Functioning properly.'
        elif stateVars == (0, 0, 1, 0):
            retStr1 = 'Running the fan only. Functioning properly.'
        elif stateVars == (1, 0, 1, 0):
            retStr1 = 'Cooling. Functioning properly.'
        elif stateVars == (0, 1,  1, 0):
            retStr1 = 'Heating. Functioning properly.'
        elif stateVars == (0, 1,  1, 1):
            retStr1 = 'Using aux heat. Functioning properly.'
        else:
            retStr1 = '<span class="message_alert_warning">Unknown state</span>'

    retStr2 = targMode

    if curProg == 'Manual':
        retStr3 = 'Target temperature is being set manually'
    else:
        expireDelta = (expTime-datetime.datetime.now()).total_seconds()
        if (expireDelta < 60):
            retStr3 = 'Temperature will expire in %d seconds according to the %s program.' % (int(expireDelta), curProg)
        elif (expireDelta < 3600):
            retStr3 = 'Temperature will expire in %d minutes according to the %s program.' % (int(expireDelta / 60), curProg)
        elif (expireDelta > 0):
            retStr3 = 'Temperature will expire in %0.1f hours according to the %s program.'%(expireDelta / 3600, curProg)
        else:
            retStr3 = 'Automatic pre-set program %s us running.'%(curProg)

    return (retStr1,retStr2,retStr3)

def getManualProgram():
    cursor = mysql.connect().cursor()
    cursor.execute("SELECT * FROM ManualProgram")
    table = cursor.fetchall()

    roomList = getRoomList()

    newTable=[]
    for ind, val in enumerate(table):
        newTable.append([])
        for ind1,key in enumerate(val):
            newTable[-1].append(key)
            if ind1 == 3:
                newTable[-1][-1]=roomList[int(key)-1]

    return newTable

def getPlotInfo():

    try:
        fobj = open('plotData.pck','rb')
        plotData = pickle.load(fobj)
        fobj.close()
        if (datetime.datetime.now()-plotData[-1]).seconds < 900:
            return plotData[0:5]
        else:
            return (plotData[0],'Error','Daemon', 'Error','Daemon')

    except IOError:
        plotLinks = [{'url': PLOTLY_ID1, 'name': '24Hr All'},
                     {'url': PLOTLY_ID2, 'name': 'Month All'},
                     {'url': PLOTLY_ID3, 'name': '24Hr Control'},
                     {'url': PLOTLY_ID4, 'name': 'Month Control'}]

        return (plotLinks,'Error','Daemon', 'Error','Daemon')

def getWiFiConnected():
    returnValue = False
    import httplib
    conn = httplib.HTTPConnection(WIFIDETECTADDRESS, timeout=2)
    try:
      conn.request("HEAD", "/")
      returnValue = True
    except:
      returnValue = False
    finally:
      if (conn != None):
        conn.close()
    return returnValue
    
    
def getSensorStatus():
  returnValue = None
  cursor = mysql.connect().cursor()

  cursor.execute("select s1.latest, s2.moduleID, s2.location, s2.temperature, s2.humidity from (select readingID, moduleID, max(timeStamp) as latest from SensorData group by moduleID) s1 join SensorData as s2 on s1.readingID = s2.readingID ORDER BY s2.moduleID") 
  sensors = cursor.fetchall()

  sensorList = []
  for sensor in sensors:
    cursor.execute("select count(readingID) from SensorData where moduleID = %d and timeStamp > date_sub(now(), interval 1 hour)" % sensor[1])
    counts = cursor.fetchall()
    sensorList.append([sensor[0], sensor[1], sensor[2], counts[0][0], "Weather" if sensor[1] == 0 else "Local" if sensor[1] == 1 else "Remote"])

  cursor.close()

  return [[sensor[1], sensor[2], sensor[0], sensor[3], sensor[4]] for sensor in sensorList]
    
def getSensorReadingCounts():
  cursor = mysql.connect().cursor()
  cursor.execute("""
		select concat(dh.d, ' ', if(dh.hours < 10, concat('0',dh.hours), dh.hours)) d, if(r.c is null, 0, r.c) c from 
		(
		select d, hours from 
		(
		select dates.all_dates d from 
		(select adddate(curdate(),-1*(t1.i*10 + t0.i)) all_dates from
		 (select 0 i union select 1 union select 2 union select 3 union select 4 union select 5 union select 6 union select 7 union select 8 union select 9) t0,
		 (select 0 i union select 1 union select 2 union select 3 union select 4 union select 5 union select 6 union select 7 union select 8 union select 9) t1) dates
		where dates.all_dates between date_sub(curdate(), interval 1 week) and curdate()) dd
		cross join
		(select hours from
		(select tens.a*10 + ones.a hours from
			(select 0 as a union all select 1 union all select 2 ) tens
		cross join 
			(select 0 as a union all select 1 union all select 2 union all select 3 union all select 4 union all select 5 union all select 6 union all select 7 union all select 8 union all select 9) ones
		order by hours) all_hours
		where hours < 24) hh

		) dh
		left join
		(
				select count(readingID) c, date(timeStamp) d, hour(timeStamp) hours from SensorData WHERE moduleID=2 group by concat(date(timeStamp),' ',hour(timeStamp)) 
		) r
		ON dh.d = r.d and dh.hours = r.hours
    where str_to_date(concat(dh.d, ' ', dh.hours, ':00'), '%Y-%m-%d %H:%i') <= now()
		order by d  
			""")
  sensorReadingCounts = cursor.fetchall()
  
  return [[count[0], count[1]] for count in sensorReadingCounts]

def getControllerCounts():
  cursor = mysql.connect().cursor()
  cursor.execute("""
		select concat(dh.d, ' ', if(dh.hours < 10, concat('0',dh.hours), dh.hours)) d, if(r.c is null, 0, r.c) c from 
		(
		select d, hours from 
		(
		select dates.all_dates d from 
		(select adddate(curdate(),-1*(t1.i*10 + t0.i)) all_dates from
		 (select 0 i union select 1 union select 2 union select 3 union select 4 union select 5 union select 6 union select 7 union select 8 union select 9) t0,
		 (select 0 i union select 1 union select 2 union select 3 union select 4 union select 5 union select 6 union select 7 union select 8 union select 9) t1) dates
		where dates.all_dates between date_sub(curdate(), interval 1 week) and curdate()) dd
		cross join
		(select hours from
		(select tens.a*10 + ones.a hours from
			(select 0 as a union all select 1 union all select 2 ) tens
		cross join 
			(select 0 as a union all select 1 union all select 2 union all select 3 union all select 4 union all select 5 union all select 6 union all select 7 union all select 8 union all select 9) ones
		order by hours) all_hours
		where hours < 24) hh
		) dh
		left join
		(
				select count(id) c, date(lastStatus) d, hour(lastStatus) hours from ControllerStatus group by concat(date(lastStatus),' ',hour(lastStatus)) 
		) r
		ON dh.d = r.d and dh.hours = r.hours
    where str_to_date(concat(dh.d, ' ', dh.hours, ':00'), '%Y-%m-%d %H:%i') <= now()
		order by d  
			""")
  controllerCounts = cursor.fetchall()
  
  return [[count[0], count[1]] for count in controllerCounts]
    
@app.route('/_controllerCount', methods= ['GET'])
def updateControllerCount():
  controllerCounts = getControllerCounts()
  
  return jsonify(controllerCounts)

@app.route('/_sensorReadings', methods= ['GET'])
def updateSensorReadings():
  sensorReadings = getSensorReadingCounts()
  
  return jsonify(sensorReadings)
    
@app.route('/config')
def config_page():
  # Get current sensor status
  sensorStatusList = getSensorStatus()

  sensorReadingCounts = getSensorReadingCounts()
  controllerCounts = getControllerCounts()

  return render_template('config.html', **locals())
  
  
@app.route('/')
#@basic_auth.required
def main_page():
    now = datetime.datetime.now()
    month = now.month
    if (month < 4 or month > 11):
      backgroundImage = "Madison.winter.800.480.jpg"
    else:
      backgroundImage = "Madison.spring.800.480.jpg"
      
    modeList = getModeList()
    roomList = getRoomList()
    curProg,progList = getProgList()

    curModule,targTemp,targMode,expTime = getThermSet()
    
    curRoom = -1
    # find the current room in the thermostat set list. Room list is a list of all rooms. When index 0 = index 3, the room sensor is active
    for testRoom in roomList:
      if (testRoom[0] == curModule and testRoom[2] == curModule):
        curRoom = testRoom 
        break
        
    # if the current room isn't in the room list (inactive/fault), default to the first one that is active
    if (curRoom == -1):
    	for testRoom in roomList:
    		if (testRoom[0] != 0 and testRoom[2] == testRoom[2]):
    		  curRoom = testRoom
    		  break
    
    stateString, modeString, expString = getCurrentState(targTemp,targMode,curRoom,curProg,expTime)

    curTemp = getCurrentTemp(curModule)
    curHumid = getCurrentHumid(curModule)
    if (curHumid == None): curHumid = 0
    curTemp = ('%d&deg;' % (round(curTemp,0)))
    curHumid = ('%d%%' % (round(curHumid,0)))

    outsideTemp = getCurrentTemp(0)
    outsideHumid = getCurrentHumid(0)
    if (outsideHumid == None): outsideHumid = 0
    outsideTemp = ('%d' % (round(outsideTemp,0)))
    outsideHumid = ('%d' % (round(outsideHumid,0)))  
    
    plotLinks, monthHours, dayHours, monthAux, dayAux = getPlotInfo()

    if 'Heat' in targMode:
        heatBool = True
    else:
        heatBool = False
        
    if getWiFiConnected():
      wiFiConnected = 'avail'
    else:
      wiFiConnected = 'unavail';

    currentTime = time.strftime('%-I:%M');
    if time.strftime('%p') == 'PM':
      currentTime = currentTime + 'p'
    else :
      currentTime = currentTime + 'a'
    currentDate = time.strftime(' %a %b %-d, %Y');
    currentTimeDate = currentTime + currentDate;
    return render_template('index.html', **locals())

@app.route('/schedule.html')
#@basic_auth.required
def schedule_page():
    manTable = getManualProgram()
    roomList = getRoomList()
    modeList = getModeList()
    curProg,progList = getProgList()

    return render_template('schedule.html', **locals())

@app.route('/schedule.html', methods=['POST'])
#@basic_auth.required
def handleSchedulePost():
    #print 'Here comes the Schedule form!!!!!'
    #print(request.form)

    if 'changeRow' in request.form.keys():
        url = updateMan(request)
    elif 'program' in request.form.keys():
        url = updateProg(request)
    elif 'deleteRow' in request.form.keys():
        url = deleteProg(request)

    else:
        #print('You hit the round button!')
        #print(request)
        url = updateSet(request)

    return redirect(url)

@app.route('/', methods=['POST'])
#@basic_auth.required
def handlePost():
    logger.debug( 'Here comes the form!!!!!')
    logger.debug(request.form)

    logger.debug('You hit the round button!')
    logger.debug(request)
    url = updateSet(request)

    return redirect(url)


def updateMan(request):
    rowKey = int(request.form['changeRow'])
    day = request.form['weekDay']
    time = request.form['opTime']

    room = request.form['room']
    #Convert room string to moduleID

    newTemp = request.form['desTemp']
    mode = request.form['opMode']

    conn = mysql.connect()

    cursor = conn.cursor()

    cursor.execute("SELECT rowKey FROM ManualProgram")
    _rowsInTable = cursor.fetchall()
    _rowsInTable = [int(val[0]) for val in _rowsInTable]

    if rowKey in _rowsInTable:
        cursor.execute("UPDATE ManualProgram SET weekDay='%s', time='%s', moduleID=%s, desiredTemp=%s, desiredMode='%s' WHERE rowKey=%s"
                       %(str(day),str(time),str(int(room)),str(newTemp),str(mode),str(rowKey)))
    else:
        cursor.execute("INSERT ManualProgram SET weekDay='%s', time='%s', moduleID=%s, desiredTemp=%s, desiredMode='%s', rowKey=%s"
                       %(str(day),str(time),str(int(room)),str(newTemp),str(mode),str(rowKey)))

    conn.commit()
    cursor.close()
    conn.close()

    #print 'Rows in ManualProgram',_rowsInTable

    if request.form['direct'] != '':
      return request.form['direct']
    else:
      return url_for('main_page')+'#download'


def updateSet(request):
    action = request.form['action']
    newMode = request.form['desired-mode']


    expTime = datetime.datetime.now()+ datetime.timedelta(hours=int(request.form['run-time']))

    targetTemp = int(request.form['target'])
    targetRoom = request.form['target-room']

    conn = mysql.connect()

    cursor=conn.cursor()

    if action == 'mode':
      cursor.execute("UPDATE ThermostatSet SET targetMode='%s' WHERE entryNo=1" % (str(newMode)))
    else:
      cursor.execute("UPDATE ThermostatSet SET moduleID=%s, targetTemp=%s, targetMode='%s', expiryTime='%s' WHERE entryNo=1"
                       %(str(targetRoom),str(targetTemp),str(newMode),str(expTime)))

    conn.commit()
    cursor.close()
    conn.close()


    return url_for('main_page')

def updateProg(request):
    program = request.form['program']

    conn = mysql.connect()

    cursor=conn.cursor()

    cursor.execute("UPDATE ProgramTypes SET active=1 WHERE program='%s'"
                       %(str(program)))

    cursor.execute("UPDATE ProgramTypes SET active=0 WHERE program!='%s'"
                       %(str(program)))

    conn.commit()
    cursor.close()
    conn.close()

    return url_for('main_page')

def deleteProg(request):
    rowNum = request.form['deleteRow']

    conn = mysql.connect()

    cursor=conn.cursor()

    cursor.execute("DELETE FROM ManualProgram WHERE rowKey=%s"%(rowNum))

    conn.commit()
    cursor.close()
    conn.close()

    if request.form['direct'] != '':
      return request.form['direct']
    else:
      return url_for('main_page')

# Make the display brighter
@app.route('/_brighter', methods= ['GET'])
def screenBrigher():
  maxBrightness = bl.get_max_brightness()
  currentBrightness = bl.get_actual_brightness()
  currentBrightness = currentBrightness + int(round(maxBrightness / 10))
  if currentBrightness <= maxBrightness:
    bl.set_brightness(currentBrightness) 
  else:
    bl.set_brightness(maxBrightness)
    
  return ""
  
# Make the display dimmer  
@app.route('/_dimmer', methods= ['GET'])
def screenDimmer():
  maxBrightness = bl.get_max_brightness()
  currentBrightness = bl.get_actual_brightness()
  currentBrightness = currentBrightness - int(round(maxBrightness / 10))
  if currentBrightness >= 11:
    bl.set_brightness(currentBrightness)
  else:
    bl.set_brightness(11)

  return "" 

@app.route('/_liveTargetTemp', methods= ['GET'])
def updateTargetTemp():
    curModule,targTemp,targMode,expTime = getThermSet()
    return (str(targTemp))

@app.route('/_liveTemp', methods= ['GET'])
def updateTemp():
    curModule,targTemp,targMode,expTime = getThermSet()
    curTemp = getCurrentTemp(curModule)
    return (str(int(round(curTemp,0))))

@app.route('/_liveStatus1', methods= ['GET'])
def updateStatus1():
    roomList = getRoomList()
    curProg,progList = getProgList()

    curModule,targTemp,targMode,expTime = getThermSet()
    curRoom = roomList[curModule-1]

    retStrings = getCurrentState(targTemp,targMode,curRoom,curProg,expTime)
    return retStrings[0]

@app.route('/_liveStatus2', methods= ['GET'])
def updateStatus2():
    roomList = getRoomList()
    curProg,progList = getProgList()

    curModule,targTemp,targMode,expTime = getThermSet()
    curRoom = roomList[curModule-1]

    retStrings = getCurrentState(targTemp,targMode,curRoom,curProg,expTime)
    return retStrings[1]

@app.route('/_liveStatus3', methods= ['GET'])
def updateStatus3():
    roomList = getRoomList()
    curProg,progList = getProgList()

    curModule,targTemp,targMode,expTime = getThermSet()
    curRoom = roomList[curModule-1]

    retStrings = getCurrentState(targTemp,targMode,curRoom,curProg,expTime)
    return retStrings[2]

@app.route('/_wifistatus', methods= ['GET'])
def updateWiFiStatus():
    if getWiFiConnected():
      wiFiConnected = 'avail'
    else:
      wiFiConnected = 'unavail'
    return wiFiConnected

@app.route('/_failedsensors', methods= ['GET'])
def updateFailedSensors():
    roomList = getRoomList()
    failedList = []
    
    for roomID, roomStr, sensorID, lastreading, lasttemp in roomList:
      if roomID != 0 and roomID != sensorID:
        failedList.append([roomID, [roomStr, lastreading]])

    return jsonify(failedList)
    
# AJAX responder to determine if the controller has failed or not. It is marked as failed
# if a command has not successfully been sent to it for 5 mins (600 seconds)
@app.route('/_failedcontroller', methods= ['GET'])
def updateFailedController():
    failed = 'false'
    status = getControllerStatus()
    if int(status[1]) > 600:  # if it has been more than 600 seconds since the last successful controller connection, it has failed.
      failed = 'true'
      logger.error("failed controller")
    else :
      logger.debug("controller is good")
      
    return '{"state":"%s", "laststatus":"%s"}' % (failed, status[0])
    
# Read the latest relay controller status from the database. Get the last time the controller
# was successfully sent instructions and the number of seconds since then
def getControllerStatus():
    cursor = mysql.connect().cursor()

    cursor.execute("SELECT lastStatus, NOW()-lastStatus FROM ControllerStatus ORDER BY lastStatus DESC LIMIT 1")
    status = cursor.fetchall()

    cursor.close()
    
    if status != None:
      stamp = status[0][0]
      stamp = "%d/%02d/%4d %02d:%02d:%02d" % (int(stamp.month), int(stamp.day), int(stamp.year), int(stamp.hour), int(stamp.minute), int(stamp.second))

    return ([stamp, status[0][1]] if status != None and status[0] != None else [None,None])
    

@app.route('/_sparkTest/<moduleID>/<location>/<temperature>', methods= ['GET', 'POST'])
#@basic_auth.required
def sparkData(moduleID,location,temperature):
    temperature = '%0.1f'%float(temperature)
    if float(temperature) < -100.0:
        return 'yes'

    location = str(location).replace('+', ' ')
    #print(location)
    conn = mysql.connect()

    cursor = conn.cursor()

    cursor.execute("INSERT SensorData SET moduleID=%s, location='%s', temperature=%s"%(str(moduleID),str(location),str(temperature)))

    conn.commit()
    cursor.close()
    conn.close()
    return 'yes'

logger.info("Starting")

if __name__ == '__main__':
    app.run("192.168.1.10",port=70, debug=True) # Listen on all interfaces
