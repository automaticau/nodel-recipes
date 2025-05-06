'''
**Atlona AT-GAIN-60** amplifier (and other compatible models)

 * default credentials `admin` `Atlona`
 * possible MAC prefix `b8:98:b0`
 * latest firmware at time of writing **1.1.20**

`REV 1`
'''

param_IPAddress = Parameter({ "schema": { "type": "string", "desc": "Overrides bindings" }})

TCP_PORT = 23
param_Port = Parameter({ "schema": { "type": "string", "desc": "(if not %s)" % TCP_PORT }})

local_event_IPAddress = LocalEvent({ "schema": { "type": "string" }})

def remote_event_IPAddress(arg):
  if is_blank(param_IPAddress):
    prev = local_event_IPAddress.getArg()
    if prev != arg:
      console.info("IP address updated to %s, was %s" % (arg, prev))
      local_event_IPAddress.emit(arg)
      dest = "%s:%s" % (arg, param_Port or TCP_PORT)
      _tcp.setDest(dest)

def main():
  ipAddr = param_IPAddress
  
  if is_blank(ipAddr):
    ipAddr = local_event_IPAddress.getArg()
  else:
    console.info("Using IP address from config - %s" % ipAddr)
    local_event_IPAddress.emit(ipAddr)
  
  if is_blank(ipAddr):
    return console.info("No IP address configured; otherwise will wait to be notified")
  
  dest = "%s:%s" % (ipAddr, param_Port or TCP_PORT)
  console.info("Will connect to %s" % dest)
  _tcp.setDest(dest)

_pollers = list()
  
local_event_Version = LocalEvent({ "schema": { "type": "string" }})

def doPollVersion():
  _tcp.send("Version")
  
_pollers.append(Timer(doPollVersion, 2 * 60, 10)) # every 2 minutes, first after 10 seconds

local_event_Power = LocalEvent({ "schema": { "type": "string", "enum": [ "On", "Off" ] }})

@local_action({ "schema": { "type": "string", "enum": [ "On", "Off" ] }})
def Power(arg):
  console.info("Power(%s)" % arg)
  lcArg = str(arg).lower()
  if lcArg in [ "on", "1", "true" ]: state = True
  elif lcArg in [ "off", "0", "false" ]: state = False
  else: return console.warn("Power: unknown arg - %s" % arg)

  if state:
    doPowerOn()
  else:
    doPowerOff()
    
def parseLine(line):
  if line == "PWON":
    local_event_Power.emit("On")
    
  elif line == "PWOFF":
    local_event_Power.emit("Off")
    
  elif line.count(".") >= 2:
    global _lastReceive
    _lastReceive = system_clock()
    local_event_Version.emit(line)

def doPowerOn():
  _tcp.send("PWON")
  
def doPowerOff():
  _tcp.send("PWOFF")

def tcp_received(line):
  console.info("tcp_recv: %s" % line)
  parseLine(line)

def tcp_connected():
  console.info("TCP connected")
  _tcp.clearQueue()
  [ p.start() for p in _pollers ]
  
def tcp_disconnected():
  console.warn("TCP disconnected")
  [ p.stop() for p in _pollers ]
  
def tcp_sent(line):
  log(1, "tcp_sent [%s]" % line)

_tcp = TCP(connected=tcp_connected, received=tcp_received, sent=tcp_sent, disconnected=tcp_disconnected, sendDelimiters='\n', receiveDelimiters='\r\n')
  
# <!-- logging

local_event_LogLevel = LocalEvent({'group': 'Debug', 'order': 10000+next_seq(), 'desc': 'Use this to ramp up the logging (with indentation)',  
                                   'schema': {'type': 'integer'}})

def warn(level, msg):
  if (local_event_LogLevel.getArg() or 0) >= level:
    console.warn(('  ' * level) + msg)

def log(level, msg):
  if (local_event_LogLevel.getArg() or 0) >= level:
    console.log(('  ' * level) + msg)
    
# --!>
  
# <!-- status

# for comms drop-out
_lastReceive = system_clock()

# roughly, the last contact  
local_event_LastContactDetect = LocalEvent({'group': 'Status', 'order': 99999+next_seq(), 'title': 'Last contact detect', 'schema': {'type': 'string'}})

# node status
local_event_Status = LocalEvent({ "group": "Status", 'order': 99999+next_seq(), 'schema': { 'type': 'object', 'properties': {
        'level': { 'type': 'integer', 'order': 1 },
        'message': { 'type': 'string', 'order': 2 }}}})
  
def statusCheck():
  diff = (system_clock() - _lastReceive)/1000.0 # (in secs)
  now = date_now()
  
  if diff > (status_check_interval*2):
    previousContactValue = local_event_LastContactDetect.getArg()
    
    if previousContactValue == None:
      message = 'Always been missing'
      
    else:
      previousContact = date_parse(previousContactValue)
      message = 'Missing %s' % formatPeriod(previousContact)
      
    local_event_Status.emit({'level': 2, 'message': message})
    
  else:
    # update contact info
    local_event_LastContactDetect.emit(str(now))
    local_event_Status.emit({'level': 0, 'message': 'OK'})
    
status_check_interval = 75
status_timer = Timer(statusCheck, status_check_interval)

def formatPeriod(dateObj):
  if dateObj == None:       return 'for unknown period'
  
  now = date_now()
  diff = (now.getMillis() - dateObj.getMillis()) / 1000 / 60 # in mins
  
  if diff == 0:             return 'for <1 min'
  elif diff < 60:           return 'for <%s mins' % diff
  elif diff < 60*24:        return 'since %s' % dateObj.toString('h:mm a')
  else:                     return 'since %s' % dateObj.toString('E d-MMM h:mm a')

# --->
