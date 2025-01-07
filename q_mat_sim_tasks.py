# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QMatSim
                                 A QGIS plugin
 QGIS to MatSim
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-10-07
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Dmitry D.
        email                : dmitrdobr@mail.ru
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import pyqtSignal, QTime

from qgis.core import (
      QgsVectorLayer, 
      QgsGeometry,
      QgsFeature, 
      QgsFeatureIterator, 
      QgsPointXY, 
      QgsTask,
      QgsField,
      QgsFields,
      QgsWkbTypes,
      QgsFeatureRequest,
      QgsRectangle, 
      QgsVector,
      QgsExpression
)

from qgis.PyQt import QtXml

import numpy as np
import heapq, random

from datetime import datetime, time, timedelta

POINT_NODE_XML_TASK_DESCRIPTION = "POINT_NODE_XML_TASK"
LINE_LINK_XML_TASK_DESCRIPTION = "LINE_LINK_XML_TASK"
LINE_LINK_NMP_TASK_DESCRIPTION = "LINE_LINK_ARRAY_TASK"
AGENT_XML_TASK_DESCRIPTION = "AGENT_XML_TASK"

class XmlBase(): # Base to create XML elements indide parent with given names
      def __init__(self, doc, ParentNodeName = "nodes", ChildNodeName = "node"):
            self.__doc = doc # QDomDocument()
            self.resultDom = doc.createElement(ParentNodeName) # QDomElement
            self.__childDomName = ChildNodeName

      def addChildNode(self, params: dict):
            childNode = self.__doc.createElement(self.__childDomName)

            for key, value in params.items():
                  childNode.setAttribute(key, str(value))

            self.resultDom.appendChild(childNode)

class FeatureTaskBase(QgsTask): # Task base with feature iteration
      printLog = pyqtSignal(str)

      def __init__(self, description, layer, IdValOnLayer = True, IdAttr = 'id'):
            super().__init__(description, QgsTask.CanCancel)
            self.flagAutoId = IdValOnLayer # identify id with attribute or .id() / $id
            self.IdAttributeName = IdAttr 

            self.features = layer.getFeatures() # list of features to process
            self.FCount = layer.featureCount() # count of features

            self.currentId = 0 # current processing feature ID
            self.IdAttrName = IdAttr
            '''
            {
                  'AllLine2Sides': False, - linetask
                  'Attribute': 'oneway', - linetask
                  'OneWayVal': '1',  - linetask
                  'TwoSidedVal': '0',  - linetask
                  'DefaultOneWay': 1,  - linetask

                  'IdValOnLayer': False, - basetask

                  'PointAttr': 'id', - pointtask
                  'LineAttr': 'id' - linetask
            }
            '''
      
      def run(self):
            self.printLog.emit(f'[INFO]:[{self.description()}] => Task run.')

            counter = 0
            for feature in self.features:
                  self.currentId = int(feature.id()) if self.flagAutoId else int(feature.attribute(self.IdAttrName))
                  self.sendFeatureLog('Processing.',0)

                  self.processFeature(feature)

                  if self.isCanceled():
                        return False
                  
                  self.setProgress(counter/self.FCount)
                  counter += 1

            self.setProgress(100)
            return True
      
      def processFeature(self, feature): # need to override
            pass

      def sendFeatureLog(self, string, LogType):
            str_t = '[INFO]:['
            if (LogType == 1):
                  str_t = '[WARN]:['
            if (LogType == 2):
                  str_t = '[ERROR]:['
            new_str = f'{str_t}{self.description()}] => feature({str(self.currentId)}). {string}.'
            self.printLog.emit(new_str)

      def finished(self, result):
            self.printLog.emit(f'[INFO]:[{self.description()}] => Task finished.')
            self.result = result
    
      def cancel(self):
            self.printLog.emit(f'[INFO]:[{self.description()}] => Task cancel.')
            super().cancel()

class NodeXmlTask(XmlBase, FeatureTaskBase): # task to create XML nodes from points
      def __init__(self, document, pointVectorLayer, taskSettings):
            XmlBase.__init__(self, doc=document, ParentNodeName="nodes", ChildNodeName="node")
            FeatureTaskBase.__init__(self, description=POINT_NODE_XML_TASK_DESCRIPTION, layer=pointVectorLayer, 
                              IdValOnLayer=taskSettings['IdValOnLayer'],IdAttr=taskSettings['PointAttr'])
            
      def processFeature(self, feature): # overrided
            point = feature.geometry().asPoint()
            params = dict({
                  'id': int(self.currentId),
                  'x': round(point.x(), 3),
                  'y': round(point.y(), 3)
            })

            self.addChildNode(params)

class LineTaskBase(FeatureTaskBase): # task base for network instruments 
      def __init__(self, TaskDescription, lineVectorLayer, pointVectorLayer, taskSettings):
            FeatureTaskBase.__init__(self, description=TaskDescription, layer=lineVectorLayer, 
                              IdValOnLayer=taskSettings['IdValOnLayer'], IdAttr=taskSettings['LineAttr'])
           
            self.MaxLineId = -1 # id for reversed lines

            if (self.flagAutoId): # use feature number in layer
                  self.MaxLineId = lineVectorLayer.featureCount() + 1
            else: # use field
                  idx = lineVectorLayer.fields().lookupField(taskSettings['LineAttr'])
                  self.MaxLineId = lineVectorLayer.maximumValue(idx) + 1

            self.TaskParams = taskSettings # network settings
            self.DefaultTwoWay = taskSettings['DefaultTwoWay']

            self.points = pointVectorLayer
            self.ToleranceVector = QgsVector(0.05,0.05) # vector for QgsRectangle extent search for points
      
      def defineNearNodeID(self, point): # define nearest node id from point layer to given point
            foundId = None

            request = QgsFeatureRequest(QgsRectangle(point - self.ToleranceVector, point + self.ToleranceVector))
            request.setFlags(QgsFeatureRequest.ExactIntersect)

            for PFeature in self.points.getFeatures(request): # QgsFeatureIterator
                  foundId = PFeature.id() if self.flagAutoId else PFeature.attribute('id')
                  if (PFeature.geometry().asPoint() == point):
                        break
            
            if (foundId is None):
                  self.sendFeatureLog(f'not found node at point: POINT({round(point.x(),3)},{round(point.y(),3)})', 2)
                  self.cancel()
                  return -1
            else:
                  return int(foundId)
      
      def processFeature(self, feature): # overrided
            linePoints = None
            # check geometry
            if (feature.geometry().wkbType() == QgsWkbTypes.LineString):
                  linePoints = feature.geometry().asPolyline()
            else:
                  linePoints = feature.geometry().asMultiPolyline()[0]

            if len(linePoints) != 2:
                  self.sendFeatureLog('2+ point lines not supported', 2)
                  self.cancel()
                  return

            # define nearest nodes ids from point layers
            idFrom = self.defineNearNodeID(linePoints[0])
            idTo = self.defineNearNodeID(linePoints[1])

            flagTwoSides = True

            if (not self.TaskParams['AllLine2Sides']): # if not every line is two sided
                  onewayval = feature.attribute(self.TaskParams['Attribute']) # get value of oneway attribute from feature

                  if (str(onewayval) == self.TaskParams['OneWayVal']):
                        flagTwoSides = False
                  elif (str(onewayval) == self.TaskParams['TwoSidedVal']):
                        flagTwoSides = True
                  else:
                        flagTwoSides = self.DefaultTwoWay
            
            self.processLine(feature, idFrom, idTo, flagTwoSides)
      
      def processLine(self, feature, idFrom, idTo, TwoSides): # override
            pass

class NetworkArrayTask(LineTaskBase): # task to create numpy array of network from lines and points
      def __init__(self, lineVectorLayer, pointVectorLayer, taskSettings):
            LineTaskBase.__init__(self, LINE_LINK_NMP_TASK_DESCRIPTION, lineVectorLayer, pointVectorLayer, taskSettings)

            self.matrix = np.full((self.points.featureCount(),self.points.featureCount()), -1)
            # matrix representation of network
            # nodes $id as rows/columns
            # links original with settings numbers as [row, col] values if there is a way from to node
            self.lineUseAutoId = self.flagAutoId
            self.flagAutoId = True # rewrite base class definition to use only $id for points
      
      def processLine(self, feature, idFrom, idTo, TwoSides): # override
            
            lineId = self.currentId
            if (not self.lineUseAutoId):
                  lineId = feature.attribute(self.IdAttrName)

            self.matrix[idFrom - 1,idTo  - 1] = lineId

            if (TwoSides):
                  self.matrix[idTo - 1, idFrom - 1] = int(self.MaxLineId)
                  self.MaxLineId += 1
            
class LinkXmlTaskV2(XmlBase, LineTaskBase): # task to create XML links from lines and points
      def __init__(self, document, lineVectorLayer, pointVectorLayer, taskSettings):
            XmlBase.__init__(self, doc=document, ParentNodeName="links", ChildNodeName="link")
            LineTaskBase.__init__(self, LINE_LINK_XML_TASK_DESCRIPTION, lineVectorLayer, pointVectorLayer, taskSettings)
      
      def processLine(self, feature, idFrom, idTo, TwoSides): # override
            # get line attributes
            freespeed = feature.attribute('freespeed')
            if (freespeed == None or freespeed <= 0.0):
                  self.sendFeatureLog('Not set freespeed. Default=20.0', 1)
                  freespeed = 20.0
            
            capacity = feature.attribute('capacity')
            if (capacity == None or capacity <= 0):
                  self.sendFeatureLog('Not set capacity. Default=3600', 1)
                  capacity = 3600

            permlanes = feature.attribute('permlanes')
            if (permlanes == None or permlanes <= 0):
                  self.sendFeatureLog('Not set permlanes. Default=1', 1)
                  permlanes = 1

            # XML link params
            params = dict({
                  'id': int(self.currentId),
                  'from': idFrom,
                  'to': idTo,
                  'freespeed': freespeed,
                  'length': round((feature.geometry().length()),3),
                  'capacity': int(capacity),
                  'permlanes': int(permlanes)
            })

            self.addChildNode(params)
            # two sided link
            if (TwoSides):
                  params['id'] = int(self.MaxLineId)
                  params['from'] = idTo
                  params['to'] = idFrom

                  self.addChildNode(params)

                  self.MaxLineId += 1

# class XmlBaseV2(): # Base to quickly create XML elements
#       def __init__(self, doc, startDomName):
#             self.__doc = doc # QDomDocument()
#             self.DomElementStack = list()

#             self.rootDom = self.__doc.elementsByTagName(startDomName).item(0) # QDomElement
      
#       def applyToRootDom(self): # set element at the end of stack as child for root element
#             self.rootDom.appendChild(self.DomElementStack[-1])
      
#       def createDomAtStack(self, domName: str): # create new element at the end of stack
#             elem = self.__doc.createElement(domName)
#             self.DomElementStack.append(elem)
      
#       def addAttributesAtLastDomAtStack(self, params: dict): # add attributes to element at the end of stack
#             for key, value in params.items():
#                   self.DomElementStack[-1].setAttribute(key, str(value))

#       def addTextNodeToLastDomAtStack(self, text: str): # insert text to element at the end of stack
#             tx = self.__doc.createTextNode(text)
#             self.DomElementStack[-1].appendChild(tx)

#       def appendLastDomAtStack(self): # set element at the end of stack as child for element before and delete it from stack
#             self.DomElementStack[-2].appendChild(self.DomElementStack[-1])
#             self.DomElementStack.pop()

# class AgentXmlTask(XmlBaseV2, QgsTask):
#       printLog = pyqtSignal(str)
      
#       def __init__(self, document, nodesLayer, actsLayer, matrix, taskSettings):
#             XmlBaseV2.__init__(self, doc=document, startDomName="plans") # append final <person> element to <plans> root element
#             QgsTask.__init__(self, AGENT_XML_TASK_DESCRIPTION, QgsTask.CanCancel)

#             self.agCount = taskSettings['AgentsCount']
#             self.settings = taskSettings

#             self.actsLayer = actsLayer
#             self.nodesLayer = nodesLayer

#       def run(self):
#             for i in range(1, self.agCount+1):
#                   if self.isCanceled():
#                         return False
                  
#                   actCount = random.randint(self.settings['ActCountMin'], self.settings['ActCountMax'])
#                   print('agent no ' , i , ' act count: ' , actCount)

#                   self.createActs(actCount)

#                   self.setProgress(int(i/(self.agCount+1)))
            
#             self.setProgress(100)
#             return True

#       def createActs(self, actCount):
#             acts = list()

#             for i in range(1, actCount):
#                   print('act no:', i)
#                   print('act feature: ')
#                   print(self.randActPointFeature().id())

#       def randActPointFeature(self, filterType=None): # get random act point from acts layer if filterType is set, get with current act type
#             FeatureId = -1

#             if (filterType):
#                   string = f'"acttype"=\'{filterType}\'' # request string
#                   #print(string)
#                   request = QgsFeatureRequest(QgsExpression(string))
#                   ids = list()
#                   for f in self.actsLayer.getFeatures(request): # request features and get theirs $id
#                         ids.append(f.id())
#                   #print(ids)
#                   FeatureId = random.choice(ids) # random from ids
#             else:
#                   FeatureId = random.randint(1,self.actsLayer.featureCount())

#             return self.actsLayer.getFeature(FeatureId)


#       def randTimeFromSecLimit(self, minT, maxT):
#             val = random.randint(minT, maxT)
#             t = QTime(s=val)
#             return t

#       def finished(self, result):
#             self.printLog.emit(f'[INFO]:[{self.description()}] => Task finished.')
#             self.result = result
    
#       def cancel(self):
#             self.printLog.emit(f'[INFO]:[{self.description()}] => Task cancel.')
#             super().cancel()

class LinkXmlTask(XmlBase, FeatureTaskBase): # deprecated
      def __init__(self, document, lineVectorLayer, pointVectorLayer, taskSettings):
            XmlBase.__init__(self, doc=document, ParentNodeName="links", ChildNodeName="link")
            FeatureTaskBase.__init__(self, description=LINE_LINK_XML_TASK_DESCRIPTION, layer=lineVectorLayer, 
                              IdValOnLayer=taskSettings['IdValOnLayer'], IdAttr=taskSettings['LineAttr'])
            
            self.MaxLineId = -1 # id for reversed lines

            if (self.flagAutoId): # use feature number in layer
                  self.MaxLineId = lineVectorLayer.featureCount() + 1
            else: # use field
                  idx = lineVectorLayer.fields().lookupField(taskSettings['LineAttr'])
                  self.MaxLineId = lineVectorLayer.maximumValue(idx) + 1

            self.TaskParams = taskSettings
            self.DefaultTwoWay = taskSettings['DefaultTwoWay']

            self.points = pointVectorLayer
            self.ToleranceVector = QgsVector(0.05,0.05) # vector for QgsRectangle extent search for points
            # topology Tolerance
            '''
                  0---+
                  |\  |
                  | o |
                  |  \|
                  +---0
            '''

      def defineNearNodeID(self, point):
            foundId = None

            request = QgsFeatureRequest(QgsRectangle(point - self.ToleranceVector, point + self.ToleranceVector))
            request.setFlags(QgsFeatureRequest.ExactIntersect)

            for PFeature in self.points.getFeatures(request): # QgsFeatureIterator
                  foundId = PFeature.id() if self.flagAutoId else PFeature.attribute('id')
                  if (PFeature.geometry().asPoint() == point):
                        break
            
            if (foundId is None):
                  self.sendFeatureLog(f'not found node at point: POINT({round(point.x(),3)},{round(point.y(),3)})', 2)
                  self.cancel()
                  return -1
            else:
                  return int(foundId)
      
      def processFeature(self, feature): # override
            points = None

            if (feature.geometry().wkbType() == QgsWkbTypes.LineString):
                  points = feature.geometry().asPolyline()
            else:
                  points = feature.geometry().asMultiPolyline()[0]

            if len(points) != 2:
                  self.sendFeatureLog('2+ point lines not supported', 2)
                  self.cancel()
                  return

            idFrom = self.defineNearNodeID(points[0])
            idTo = self.defineNearNodeID(points[1])

            freespeed = feature.attribute('freespeed')
            if (freespeed == None or freespeed <= 0.0):
                  self.sendFeatureLog('Not set freespeed. Default=20.0', 1)
                  freespeed = 20.0
            
            capacity = feature.attribute('capacity')
            if (capacity == None or capacity <= 0):
                  self.sendFeatureLog('Not set capacity. Default=3600', 1)
                  capacity = 3600

            permlanes = feature.attribute('permlanes')
            if (permlanes == None or permlanes <= 0):
                  self.sendFeatureLog('Not set permlanes. Default=1', 1)
                  permlanes = 1

            params = dict({
                  'id': int(self.currentId),
                  'from': idFrom,
                  'to': idTo,
                  'freespeed': freespeed,
                  'length': round(points[0].distance(points[1]),3),
                  'capacity': int(capacity),
                  'permlanes': int(permlanes)
            })

            self.addChildNode(params)

            flagTwoSides = True

            if (not self.TaskParams['AllLine2Sides']): # if not every line is two sided
                  onewayval = feature.attribute(self.TaskParams['Attribute']) # get value of oneway attribute from feature

                  if (str(onewayval) == self.TaskParams['OneWayVal']):
                        flagTwoSides = False
                  elif (str(onewayval) == self.TaskParams['TwoSidedVal']):
                        flagTwoSides = True
                  else:
                        flagTwoSides = self.DefaultTwoWay

            if (flagTwoSides):
                  params['id'] = int(self.MaxLineId)
                  params['from'] = idTo
                  params['to'] = idFrom

                  self.addChildNode(params)

                  self.MaxLineId += 1