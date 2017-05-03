#!/usr/bin/env python


from flask import *
from flask.ext.basicauth import BasicAuth
from flaskext.mysql import MySQL
from flaskext.lesscss import lesscss
import subprocess

import ConfigParser

import os
import sys

import datetime
import cPickle as pickle

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

config = ConfigParser.ConfigParser()
config.read(dname+"/config.txt")

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

    cursor.execute("SELECT * FROM OperationModes")
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

    cursor.execute("SELECT * FROM ModuleInfo")
    rooms = cursor.fetchall()

    cursor.close()

    return [str(room[1]) for room in rooms]

def getProgList():
    cursor = mysql.connect().cursor()

    cursor.execute("SELECT * FROM ProgramTypes")
    programs = cursor.fetchall()

    cursor.close()

    return ([str(prog[0]) for prog in programs if prog[1]==1][0],[str(prog[0]) for prog in programs])


def getThermSet():
    cursor = mysql.connect().cursor()

    cursor.execute("SELECT * FROM ThermostatSet")
    thermSet=cursor.fetchall()

    return thermSet[0][1:-1]

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

    if targMode == 'Off':
        retStr2 = 'Off'
    elif targMode == 'Fan':
        retStr2 = 'Currently in %s mode'%(targMode)
    else:
        retStr2 = '''Running in %s mode. Trying to reach
                      %s&deg; on the %s sensor.'''%(targMode, targTemp, curRoom)

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

@app.route('/')
#@basic_auth.required
def main_page():
    now = datetime.datetime.now()
    month = now.month
    if (month < 4 or month > 11):
      backgroundImage = "Madison.winter.320.480.jpg"
    else:
      backgroundImage = "Madison.spring.320.480.jpg"
      
    modeList = getModeList()
    roomList = getRoomList()
    curProg,progList = getProgList()

    curModule,targTemp,targMode,expTime = getThermSet()
    curRoom = roomList[curModule-1]

    stateString, modeString, expString = getCurrentState(targTemp,targMode,curRoom,curProg,expTime)

    curTemp = getCurrentTemp(curModule)
    curHumid = getCurrentHumid(curModule)
    if curHumid > 0:
        curTemp = '%2.1f&deg;/%d%%' % (curTemp, int(curHumid))
    else:
        curTemp = str(curTemp)+'&deg'

    plotLinks, monthHours, dayHours, monthAux, dayAux = getPlotInfo()

    if 'Heat' in targMode:
        heatBool = True
    else:
        heatBool = False

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
    #print 'Here comes the form!!!!!'
    #print(request.form)

    #print('You hit the round button!')
    #print(request)
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
    newMode = request.form['desired-mode']

    expTime = datetime.datetime.now()+ datetime.timedelta(hours=int(request.form['run-time']))

    targetTemp = int(request.form['target'])
    targetRoom = request.form['target-room']

    conn = mysql.connect()

    cursor=conn.cursor()

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

@app.route('/_liveTargetTemp', methods= ['GET'])
def updateTargetTemp():
    curModule,targTemp,targMode,expTime = getThermSet()
    return (str(targTemp)+'&deg')

@app.route('/_liveTemp', methods= ['GET'])
def updateTemp():
    curModule,targTemp,targMode,expTime = getThermSet()
    curTemp = getCurrentTemp(curModule)
    curHumid = getCurrentHumid(curModule)
    if curHumid > 0:
        return ('%2.1f&deg;/%d%%' % (curTemp, int(curHumid)))
    else:
        return (str(curTemp)+'&deg')

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

if __name__ == '__main__':
    app.run("192.168.1.10",port=70, debug=True) # Listen on all interfaces
