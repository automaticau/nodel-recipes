'''
_(recipe Mk 2 rev. 8, requires Nodel v2.2 or higher)_

To get started from scratch, use the **Create Frontend from sample** Action.

This **Frontend** / **Dashboard** makes use of the following files:

   * `content/index.xml` (*): a landing page (see <a href="index-sample.xml?_source" target="_blank">here</a> for viewing/copying)
   * `content/css/custom.css`: custom CSS (see <a href="css/custom-sample.css?_source" target="_blank">here</a> for viewing/copying)
   * `content/js/custom.js`: custom Javascript (see <a href="js/custom-sample.js?_source" target="_blank">here</a> for viewing/copying)
   * `content/img/background.jpg`
   * `content/img/logo.png`
   
(*) required, more than one allowed

You can **drag & drop** content into the editor for convenience, including certain binary files (e.g. graphics, etc.).

To switch to your Frontend / Dashboard, use the **Nav** / **UI** menu or use `/index.xml` URL suffix for node.

_changelog_

 * rev. 8: EXPERIMENTAL: inline discrete arguments action and event combining, e.g. `<button join='PowerA:On, PowerB:Off, PowerC:On'>`
 * rev. 6: support for signal combining using AND boolean logic
 * rev. 6: EXPERIMENTAL: negation using "NOT" as prefix
 * rev. 5: improved support for multiple actions, e.g. `<button action='Action1, Action2, Action3'>` instead of the inline-JSON method `<button action='["Action1","Action2","Action3"]'>` (avoid!)
'''

import xml.etree.ElementTree as ET # XML parsing
import os                          # working directory
from java.io import File           # reading files
from org.nodel.io import Stream    # reading files
from org.nodel import SimpleName   # for Node names
from org.nodel.core import Nodel   # for host path

param_suggestedNode = Parameter({'title': 'Suggested Node', 
                                 'desc': 'A suggestion can be made when remote bindings are created. The then need to be confirm and saved',
                                 'schema': {'type': 'string', 'format': 'node'}})

param_localOnlySignals = Parameter({'title': 'Local only signals',
                                    'desc': 'No remote bindings are configured for these. Comma-separated list of signals',
                                    'schema': {'type': 'string'}})

param_localOnlyActions = Parameter({'title': 'Local only actions',
                                    'desc': 'No remote bindings are configured for these. Comma-separated list of signals',
                                    'schema': {'type': 'string'}})

local_event_Clock = LocalEvent({"title": "Clock", "group": "General", "schema": {"type": "string" }})
timer_clock = Timer(lambda: local_event_Clock.emit(date_now()), 1)

localOnlySignals = set()
localOnlyActions = set()

# the node's working directory
workingDir = os.getcwd()

schemaMap = {} # taken from 'schema.json'
               # For example:
               #
               # { 'status_signal': {'type': 'object', 'properties': ... },
               #   'meter': {'type': 'number'},
               #   ...
               # }

def main():
  # split the local only actions and signals
  [localOnlySignals.add(SimpleName(name)) for name in (param_localOnlySignals or '').split(',')]
  [localOnlyActions.add(SimpleName(name)) for name in (param_localOnlyActions or '').split(',')]
  
  # parse the index
  indexFile = os.path.join(workingDir, 'content', 'index.xml')
  if not os.path.exists(indexFile):
    return console.warn('No "content/index.xml" file exists; please use "Create from sample" Action')
  
  schemasFile = os.path.join(workingDir, 'content', 'schemas.json')
  if os.path.exists(schemasFile):
    loadSchemas(Stream.readFully(File(schemasFile)))
  
  loadIndexFile(indexFile)
  
def loadSchemas(json):
  schemas = json_decode(json)
  
  keys = list()
  for key in schemas:
    schemaMap[key] = schemas[key]
    keys.append(key)
    
  if len(keys) > 0:
    console.info('Loaded schemas: %s' % ', '.join(keys))

  else:
    console.warn('(no schema mapping info was present)')

def loadIndexFile(xmlFile):
  xml = ET.parse(xmlFile)
  
  def explore(group, e):
    eType = e.tag
    join = e.get('join')             # shorthand for <... action=... event=...">
    eActionNormal = e.get('action') or join
    eActionOn = e.get('action-on')   # these are for
    eActionOff = e.get('action-off') # momentary buttons
    eEvent = e.get('event') or join
    title = e.get('title')
    
    # compose a group name (if possible)
    if title == None and eType == 'title':
      title = e.text
      
    if title in ['row', 'column']:
      title = None
    
    if title == None:
      thisGroup = group
    
    elif group == '':
      thisGroup = title
      
    else:
      thisGroup = '%s - %s' % (group, title)
      
    # the default schema to use if '_action' or '_signal' is not used
    defaultSchema = schemaMap.get(eType)

    def tryAction(aName):
      if is_blank(aName):
        return

      plainName = aName

      # aName might be 'Display1 Power' or 'Display1 Power:On'
      argProvided = None
      indexOfColon = aName.find(':')
      if indexOfColon > 0:
        argProvided = aName[indexOfColon+1:]
        plainName = aName[:indexOfColon] # for plain name, strip out the arg part

      existing = lookup_local_action(aName)
      if existing:
        return existing
      
      # a new action is specified
        
      # is it local only?
      if SimpleName(aName) in localOnlyActions:
        handler = lambda arg: None
        
      else:
        remoteAction = lookup_remote_action(plainName)
        if not remoteAction:
            remoteAction = create_remote_action(plainName, suggestedNode=param_suggestedNode)
        handler = lambda arg: remoteAction.call(argProvided if argProvided != None else arg)
      
      action = Action(aName, handler, 
                      { 'title': aName, 'group': thisGroup, 'order': next_seq(), 'schema': schemaMap.get('%s_action' % eType, defaultSchema)})
      
      return action

    
    def tryMultiAction(aNames):
      if is_blank(aNames):
        return False

      if lookup_local_action(aNames):
        # already exists, no need to create
        return True

      aParts = [ s.strip() for s in aNames.split(',') if not is_blank(s) ]

      if len(aParts) <= 1:
        return False

      # has multiple actions

      actionsList = []
      for aPart in aParts:
        # create discrete ones
        actionsList.append(tryAction(aPart))

      # create the handler to fire them all
      
      def handler(arg):
        for a in actionsList:
          a.call(arg) # all use the same arg

      Action(aNames, handler, 
        { 'title': aNames, 'group': thisGroup, 'order': next_seq(), 'schema': schemaMap.get('%s_action' % eType, defaultSchema) })

      return True

    # for "normal" actions check if multiple actions specified by comma separation
    if tryMultiAction(eActionNormal):
      pass # had a result meaning a multi action was dealt with
      
    else:
      # represents a single action
      tryAction(eActionNormal)
    
    # momentary actions
    tryAction(eActionOn)
    tryAction(eActionOff)

    # event / signals

    def tryEvent(eName):
      if is_blank(eName):
        return False

      plainName = eName

      # eName might be 'Display1 Power' or 'Display1 Power:On'
      argProvided = None
      indexOfColon = eName.find(':')
      if indexOfColon > 0:
        argProvided = eName[indexOfColon+1:]
        plainName = eName[:indexOfColon] # for plain name, strip out the arg part
        
      # EXPERIMENTAL
      negate = eName.startswith('NOT')
      if negate:
        eName = eName[3:] # drop the NOT

      existing = lookup_local_event(eName)
      if existing:
        return existing

      # an event is specified

      event = Event(eName, 
                    {'group': thisGroup, 'order': next_seq(), 'schema': schemaMap.get('%s_signal' % eType, defaultSchema)})
      
      # is it local only?
      if not SimpleName(eName) in localOnlySignals:

        def remoteEventHandler(rawArg=None):
          if argProvided != None:
            result = rawArg == argProvided
          else:
            result = rawArg

          event.emit(not result if negate else result)
      
        remoteEvent = lookup_remote_event(plainName)
        if not remoteEvent:
          remoteEvent = create_remote_event(plainName, remoteEventHandler, suggestedNode=param_suggestedNode)
      
      return event

    def tryMultiEvent(eNames):
      if is_blank(eNames):
        return

      # EXPERIMENTAL
      negate = eNames.startswith('NOT')
      if negate:
        eNames = eNames[3:] # drop the NOT

      if lookup_local_event(eNames):
        # already exists, no need to create
        return True

      eParts = [ s.strip() for s in eNames.split(',') if not is_blank(s) ]

      if len(eParts) <= 1:
        return False

      # has multiple actions

      eventsList = []

      multiEvent = Event(eNames, {'title': eNames, 'group': thisGroup, 'order': next_seq(), 'schema': { 'type': 'boolean' }})

      def multi_handler(arg):
        result = all([ e.getArg() for e in eventsList ])  # combine them using AND i.e. 'all' Python function, 
        multiEvent.emit(not result if negate else result) # negating if necessary
      
      for ePart in eParts:
        # create discrete ones
        e = tryEvent(ePart)
        e.addEmitHandler(multi_handler)
        eventsList.append(e)

    if tryMultiEvent(eEvent):
      pass

    else:
      tryEvent(eEvent)
    
    for i in e:
      explore(thisGroup, i)
  
  explore('', xml.getroot())


@local_action({'title': 'Create Frontend from sample and restart (will not overwrite existing)' })
def CreateFromSample():
  # this is "embedded" (and updated) with each version of Nodel
  sampleFile = File(os.path.join(Nodel.getHostPath(), '.nodel', 'webui_cache', 'index-sample.xml')) 
  contentDir = File(_node.getRoot(), 'content')
  dstFile = File(contentDir, 'index.xml')
  
  if dstFile.exists():
    return console.warn('index.xml file already exists!')
  
  if not contentDir.exists() and not contentDir.mkdirs():
    return console.error('Could not create directory %s' % contentDir)
  
  Stream.writeFully(dstFile, Stream.readFully(sampleFile))
  
  console.info('"content/index.xml" created successfully from sample. Please edit to suit your needs. Restarting node...')
  _node.restart()
