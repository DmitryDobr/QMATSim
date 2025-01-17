# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QMatSimDialog
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

import os
import sys
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.core import (
    QgsRasterLayer,
    QgsMapLayerProxyModel,
    QgsApplication
)

# from qgis.PyQt import QtXml
from qgis.PyQt.QtGui import QTextCursor, QSyntaxHighlighter, QFont, QTextCharFormat, QColor, QIcon
from qgis.PyQt.QtCore import Qt, QRegularExpression, QRegularExpressionMatchIterator, QObject, QRegExp, QTime

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
# FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'q_mat_sim_dialog_base_network.ui'))

# import xml.etree.ElementTree as ET
# from xml.dom import minidom
# import xml.etree as etr

class HighlightingRule():
    def __init__(self, expression, format):
        self.pattern = expression
        self.format = format

class Highlighter(QSyntaxHighlighter): # highlighter for xml document
    def __init__(self, parent):
        super().__init__(parent)
        self.HighlightRules: list[HighlightingRule] = [] # HighlightingRule

        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#4452ff"))
        rule = HighlightingRule(expression=QRegularExpression(r".*"), format=classFormat)
        self.HighlightRules.append(rule)

        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#505050"))
        rule = HighlightingRule(expression=QRegularExpression(r"\d"), format=classFormat)
        self.HighlightRules.append(rule)

        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#ff3038"))
        rule = HighlightingRule(expression=QRegularExpression(r"\S+(?=\=)"), format=classFormat)
        self.HighlightRules.append(rule)

        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#8800ff"))
        rule = HighlightingRule(expression=QRegularExpression(r'=\"([^"]*)\"'), format=classFormat)
        self.HighlightRules.append(rule)

        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#505050"))
        rule = HighlightingRule(expression=QRegularExpression(r'='), format=classFormat)
        self.HighlightRules.append(rule)

        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#ff3038"))
        classFormat.setBackground(QColor("#ffff00"))
        rule = HighlightingRule(expression=QRegularExpression(r"\<\?|\?>"), format=classFormat)
        self.HighlightRules.append(rule)
    
    def highlightBlock(self, text):
        for rule in self.HighlightRules:
            mIterator = rule.pattern.globalMatch(text)
            while (mIterator.hasNext()):
                match = mIterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), rule.format)
        self.setCurrentBlockState(0)

class QMatSimDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, mode='network'):
        """Constructor."""
        #super(QMatSimDialog, self).__init__(parent)

        QtWidgets.QDialog.__init__(self, parent)
        if (mode == 'network'): # run Netowrk ui
            uic.loadUi(os.path.join(os.path.dirname(__file__), 'q_mat_sim_dialog_base_network.ui'), self) # run Network ui
        else: 
            uic.loadUi(os.path.join(os.path.dirname(__file__), 'q_mat_sim_dialog_base_agents.ui'), self) # run Agent ui

            # settings agent buttons connect
            self.pushButton_agents.clicked.connect(self.changeWidgetAgents)
            self.pushButton_agentsCancel.clicked.connect(self.changeWidgetAgents)
            self.pushButton_agentsOk.clicked.connect(self.saveAgentSettings)
            
            # filters for layers pickers
            self.mMapLayerComboBox_acts.setFilters(QgsMapLayerProxyModel.PointLayer)

            self.pushButton_actTimeReset.clicked.connect(self.resetActTable)
            self.initActTableColumns()
            self.resetActTable()

            self.agentSettings = dict() # settings for XML tasks
            self.reloadAgentSettings()

        #self.setupUi(self)
        self.tabWidget_base.setCurrentIndex(0)
        self.stackedWidget.setCurrentWidget(self.stackedWidgetPage1)

        document = self.textEdit_help.document()
        cursor = QTextCursor(document)
        cursor.insertImage(os.path.dirname(__file__) + '/icons/icon_small.png')

        # filters for layers pickers
        self.mMapLayerComboBox_links.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.mMapLayerComboBox_nodes.setFilters(QgsMapLayerProxyModel.PointLayer)

        self.hl = Highlighter(self.textEdit_xmlOutput.document()) # set highlighter for xml output

        # network settings button connect
        self.pushButton_settings.clicked.connect(self.changeWidgetSettings)
        self.pushButton_settingsCancel.clicked.connect(self.changeWidgetSettings)
        self.pushButton_settingsOk.clicked.connect(self.saveSettings)

        self.radioButton_2sided_2.toggled.connect(self.setOneWaySettingsEnabled)

        self.taskSettings = dict() # settings for XML tasks
        self.reloadSettings() # default reload
    
    def initActTableColumns(self):
        self.tableWidget_actTime.horizontalHeader().setResizeMode(0,QtWidgets.QHeaderView.Fixed)
        self.tableWidget_actTime.horizontalHeader().setResizeMode(1,QtWidgets.QHeaderView.Stretch)
        self.tableWidget_actTime.horizontalHeader().setResizeMode(2,QtWidgets.QHeaderView.Stretch)
        self.tableWidget_actTime.horizontalHeader().setResizeMode(3,QtWidgets.QHeaderView.Fixed)
        self.tableWidget_actTime.horizontalHeader().setResizeMode(4,QtWidgets.QHeaderView.Fixed)

    def addActRow(self, actType='', afterRow=0, minTime='00:00:00', maxTime='01:00:00'): # insert row to Act settings table
        self.tableWidget_actTime.insertRow(afterRow)

        cell = QtWidgets.QTableWidgetItem()
        cell.setText(actType)

        self.tableWidget_actTime.setItem(afterRow,0,cell)

        # add\remove rows buttons
        add_row = QtWidgets.QPushButton()
        add_row.setIcon(QIcon(QgsApplication.iconPath('symbologyAdd.svg')))
        add_row.setText('')

        remove_row = QtWidgets.QPushButton()
        remove_row.setIcon(QIcon(QgsApplication.iconPath('symbologyRemove.svg')))
        remove_row.setText('')

        self.tableWidget_actTime.setCellWidget(afterRow,3,add_row)
        self.tableWidget_actTime.setCellWidget(afterRow,4,remove_row)
        add_row.clicked.connect(self.add_row)
        remove_row.clicked.connect(self.remove_row)

        # min\max act timeEdit
        minTimeEdit = QtWidgets.QTimeEdit()
        minTimeEdit.setTime(QTime.fromString(minTime))

        maxTimeEdit = QtWidgets.QTimeEdit()
        maxTimeEdit.setTime(QTime.fromString(maxTime))

        self.tableWidget_actTime.setCellWidget(afterRow,1,minTimeEdit)
        self.tableWidget_actTime.setCellWidget(afterRow,2,maxTimeEdit)

    def remove_row(self): # remove row on clicked button
        row = self.tableWidget_actTime.indexAt(self.sender().pos()).row()
        self.tableWidget_actTime.removeRow(row)
    
    def add_row(self): # add new row under clicked button
        row = self.tableWidget_actTime.indexAt(self.sender().pos()).row()
        self.addActRow(afterRow=row+1)
 
    def resetActTable(self): # set act table to default
        self.tableWidget_actTime.setRowCount(0)
        self.addActRow('h', minTime='01:00:00', maxTime='12:00:00')
        self.addActRow('w', minTime='05:00:00', maxTime='09:00:00')
        
    def addLogMessage(self, string): # insert log message to log textedit
        self.textEdit_log.append(string)

    def changeWidgetSettings(self): # go to network settings
        if self.stackedWidget.currentWidget() == self.stackedWidgetPage2:
            self.stackedWidget.setCurrentWidget(self.stackedWidgetPage1)
        else:
            self.stackedWidget.setCurrentWidget(self.stackedWidgetPage2)
    
    def changeWidgetAgents(self): # go to agents settings
        if self.stackedWidget.currentWidget() == self.stackedWidgetPage3:
            self.stackedWidget.setCurrentWidget(self.stackedWidgetPage1)
        else:
            self.stackedWidget.setCurrentWidget(self.stackedWidgetPage3)

    def saveSettings(self): # save Network Settings
        self.stackedWidget.setCurrentWidget(self.stackedWidgetPage1)
        self.reloadSettings()

    def saveAgentSettings(self): # save Agents Settings
        
        if (self.reloadAgentSettings()):
            self.stackedWidget.setCurrentWidget(self.stackedWidgetPage1)
        else:
            QtWidgets.QMessageBox.warning(None, 'Warning', 'Agents activity time table has no value act type row')
        
    def reloadSettings(self): # reload network Settings
        self.taskSettings['AllLine2Sides'] = self.radioButton_2sided.isChecked()
        self.taskSettings['Attribute'] = self.mFieldComboBox_Oneway.currentField()
        self.taskSettings['OneWayVal'] = self.lineEdit_oneway.text()
        self.taskSettings['TwoSidedVal'] = self.lineEdit_twoSide.text()
        self.taskSettings['DefaultTwoWay'] = self.comboBox_direction.currentIndex()

        self.taskSettings['IdValOnLayer'] = self.radioButton_idVal1.isChecked()
        self.taskSettings['PointAttr'] = self.mFieldComboBox_PointAttrId.currentField()
        self.taskSettings['LineAttr'] = self.mFieldComboBox_LineAttrId.currentField()
    
    def reloadAgentSettings(self): # reload agent generator settings
        flag = True
        actParams = dict()
        # (key 'h' value: list[minTime, maxTime])
        for i in range(0, self.tableWidget_actTime.rowCount()):
            timeList = list()
            actName = self.tableWidget_actTime.item(i,0).text()
            
            if (actName == ""):
                flag = False
                break

            timeList.append(QTime(0,0).secsTo(self.tableWidget_actTime.cellWidget(i,1).time())) # min time of act
            timeList.append(QTime(0,0).secsTo(self.tableWidget_actTime.cellWidget(i,2).time())) # max time of act

            actParams[str(actName)] = timeList

        if (flag):
            self.agentSettings['AgentsCount']   = self.spinBox_agentNum.value()       # number of agents in population
            self.agentSettings['ActCountMin']   = self.spinBox_actCountMin.value()    # minimum count of acts per plan
            self.agentSettings['ActCountMax']   = self.spinBox_actCountMax.value()    # maximum count of acts per plan
            self.agentSettings['LastFirstAct']  = self.checkBox_lastAct.isChecked()   # first act equals last
            self.agentSettings['FirstActHome']  = self.checkBox_firstActH.isChecked() # first act is 'h'
            self.agentSettings['FirstActMinMax'] = list([QTime(0,0).secsTo(self.timeEdit_firstActDurMin.time()),
                                                         QTime(0,0).secsTo(self.timeEdit_firstActDurMax.time())])
            self.agentSettings['ActMinMaxTime'] = actParams                           # time limits for acts type
        
        return flag

    def getAgentSettings(self): # return current saved agent settings
        return self.agentSettings
    
    def getSettings(self): # return current saved network settings
        return self.taskSettings

    def setOneWaySettingsEnabled(self, flag): # enable settings for directions of lines
        self.mFieldComboBox_Oneway.setEnabled(flag)
        self.lineEdit_oneway.setEnabled(flag)
        self.lineEdit_twoSide.setEnabled(flag)
        self.comboBox_direction.setEnabled(flag)

    def resetGUI(self): # clear all interface
        self.stackedWidget.setCurrentWidget(self.stackedWidgetPage1)
        self.textEdit_xmlOutput.clear()
        self.textEdit_log.clear()
        self.tabWidget_xml.setCurrentWidget(self.tab_output)
        self.progressBar.setValue(0)
        self.pushButton_saveFile.setEnabled(False)
    
