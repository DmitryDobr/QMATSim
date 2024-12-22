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

from qgis.PyQt.QtCore import pyqtSignal

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
      QgsVector
)

from qgis.PyQt import QtXml
import math
#import numpy as np

POINT_NODE_XML_TASK_DESCRIPTION = "POINT_NODE_XML_TASK"
LINE_LINK_XML_TASK_DESCRIPTION = "LINE_LINK_XML_TASK"

class XmlBase():
      def __init__(self, doc, ParentNodeName = "nodes", ChildNodeName = "node"):
            self.__doc = doc # QDomDocument()
            self.resultDom = doc.createElement(ParentNodeName) # QDomElement
            self.__childDomName = ChildNodeName

      def addChildNode(self, params: dict):
            childNode = self.__doc.createElement(self.__childDomName)

            for key, value in params.items():
                  childNode.setAttribute(key, str(value))

            self.resultDom.appendChild(childNode)

class TaskBase(QgsTask):
      printLog = pyqtSignal(str)

      def __init__(self, description, layer, IdValOnLayer = True, IdAttr = 'id'):
            super().__init__(description, QgsTask.CanCancel)
            self.flagAutoId = IdValOnLayer # identify id with attribute or .id()
            self.IdAttributeName = IdAttr 

            self.features = layer.getFeatures() # list of features to process
            self.FCount = layer.featureCount() # count of features

            self.currentId = 0 # current processing feature ID
      
      def run(self):
            self.printLog.emit(f'[INFO]:[{self.description()}] => Task run.')

            counter = 0
            for feature in self.features:
                  self.currentId = int(feature.id()) if self.flagAutoId else int(feature.attribute('id'))
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

class NodeXmlTask(XmlBase, TaskBase):
      def __init__(self, document, pointVectorLayer, taskSettings):
            XmlBase.__init__(self, doc=document, ParentNodeName="nodes", ChildNodeName="node")
            TaskBase.__init__(self, description=POINT_NODE_XML_TASK_DESCRIPTION, layer=pointVectorLayer, 
                              IdValOnLayer=taskSettings['IdValOnLayer'],IdAttr=taskSettings['PointAttr'])
            
      def processFeature(self, feature): # override
            point = feature.geometry().asPoint()
            params = dict({
                  'id': int(self.currentId),
                  'x': round(point.x(), 3),
                  'y': round(point.y(), 3)
            })

            self.addChildNode(params)

class LinkXmlTask(XmlBase, TaskBase):
      def __init__(self, document, lineVectorLayer, pointVectorLayer, taskSettings):
            XmlBase.__init__(self, doc=document, ParentNodeName="links", ChildNodeName="link")
            TaskBase.__init__(self, description=LINE_LINK_XML_TASK_DESCRIPTION, layer=lineVectorLayer, 
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
            if (freespeed == None or freespeed < 0):
                  self.sendFeatureLog('Not set freespeed. Default=20.0', 1)
                  freespeed = 20.0
            
            capacity = feature.attribute('capacity')
            if (capacity == None or capacity < 0):
                  self.sendFeatureLog('Not set capacity. Default=10', 1)
                  capacity = 10

            permlanes = feature.attribute('permlanes')
            if (permlanes == None or permlanes < 0):
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