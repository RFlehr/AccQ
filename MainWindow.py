# -*- coding: utf-8 -*-
"""
Created on Fri Oct  2 10:16:23 2015

@author: flehr

ToDo:
"""
__title__ =  'FBGAccQC'
__about__ = """Hyperion si255 Interrogation Software
            for fbg-acceleration sensors quality control
            """
__version__ = '0.1.1'
__date__ = '22.02.2016'
__author__ = 'Roman Flehr'
__cp__ = u'\u00a9 2016 Loptek GmbH & Co. KG'

import sys
sys.path.append('../')

from pyqtgraph.Qt import QtGui, QtCore
import plot as pl
import hyperion, time, os
import numpy as np
from scipy.ndimage.interpolation import shift

from tc08usb import TC08USB, USBTC08_TC_TYPE, USBTC08_ERROR#, USBTC08_UNITS
from lmfit.models import GaussianModel
import productionLog as proL




class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self, parent)
        
        self.isConnected = False
        self.tempConnected = False
        self.measurementActive = False
        self.si255 = None
        self.tc08usb = None
        self.HyperionIP = '10.0.0.55'
        self.__numChannel = 1
        self.__wavelength = np.zeros(20000)
        self.__scaledWavelength = None
        self.__scalePos = np.arange(20000, dtype=np.int16)
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.timeout.connect(self.getData)
        self.updateTempTimer = QtCore.QTimer()
        self.updateTempTimer.timeout.connect(self.getTemp)
        self.startTime = None
        
        
        self.__maxBuffer = 5000
        self.peaks = np.zeros(self.__maxBuffer)
        self.peaksTime = np.zeros(self.__maxBuffer)
        
        self.specFolder = str('../../Spektren')
        self.qcFolder = str('../../QC')
        self.gLabel = ['0g','-1g', '+1g']
        self.sensorIndex = 0
                       
        self.setWindowTitle(__title__ + ' ' + __version__)
        self.resize(900, 600)
        
        self.plotW = pl.Plot()
        
        mainSplit = QtGui.QSplitter()
        mainSplit.addWidget(self.plotW)
        mainSplit.addWidget(self.createInfoWidget())
        
        mainSplit.setFocus()
        self.setCentralWidget(mainSplit)
        
        self.createMenu()
        self.initArrays()
        #self.initDevice()
    
        self.plotW.returnSlope.connect(self.setSlope)
        
        
        self.setActionState()
        
                
#==============================================================================
#         self.setActionState()
#         self.showOptions()
#         self.showFitTable()
#==============================================================================
                
    def initArrays(self):
        self.gPeaks = [0.,0.,0.]
        self.gFWHM = [0.,0.,0.]
        self.gAsym = [0.,0.,0.]
        self.gCOG = [0.,0.,0.]
        self.gSpec = ['','','']
        self.gSens = [0.,0.]
        self.zeroButton.setChecked(True)
        self.zeroButton.setEnabled(True)
        self.minusButton.setEnabled(True)
        self.plusButton.setEnabled(True)    
        
        self.log = proL.ProductionLog()
        
    def new(self):
        self.initArrays()
        ids = self.log.getSensorIDs()
        newDia = NewSensorDialog(ids)
        index = 0
        if newDia.exec_():
            index = newDia.setSensor()
        #print(index)
        self.setIDbyIndex(index)
        self.sensorIndex = index
        if self.proID.text():
            self.measButton.setEnabled(True)
        self.saveButton.setEnabled(False)
        
    def setIDbyIndex(self, index =-1):
        pro, fbg, sens = self.log.getIDbyIndex(index)
        self.proID.setText(pro)
        self.fbgID.setText(fbg)
        self.sensorID.setText(sens)
        
        
    def initDevice(self):
        try:
            si255Comm = hyperion.HCommTCPSocket(self.HyperionIP, timeout = 5000)
        except hyperion.HyperionError as e:
            print e , ' \thaha'   
        #except:
            #print('err: ',err)
            #pass
        if si255Comm.connected:
            self.si255 = hyperion.Hyperion(comm = si255Comm)
            self.isConnected=True
            self.__wavelength =np.array(self.si255.wavelengths)
            _min = self.minWlSpin.value()
            _max = self.maxWlSpin.value()
            #print(_min, _max)
            self.__scalePos = np.where((self.__wavelength>=_min) & (self.__wavelength<_max))[0]
            #print(self.__scalePos)
            self.__scaledWavelength = self.__wavelength[self.__scalePos]
        else:
            self.isConnected=False
            QtGui.QMessageBox.critical(self,'Connection Error',
                                       'Could not connect to Spectrometer. Please try again')
        self.setActionState()       
         
    def about(self):
        QtGui.QMessageBox.about(self,'About '+__title__,
            self.tr("""<font size=8 color=red>
                        <b><center>{0}</center></b></font>
                   <br><font size=5 color=blue>
                        <b>{1}</b></font>
                    <br><br>Author: {2}<br>
                    Version: {3}<br>
                    Date: {4}<br><br>""".format(__title__, __about__, __author__, __version__, __date__)+__cp__))
                    
    def addActions(self, target, actions):
        for action in actions:
            if action is None:
                target.addSeparator()
            else:
                target.addAction(action)

    def closeEvent(self, event):
        reply = QtGui.QMessageBox.question(self, 'Message',
            "Are you sure to quit?", QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            try:
                if self.si255.comm.connected:
                    self.si255.comm.close()
                if self.tempConnected:
                    self.tc08usb.close_unit()
            except:
                pass
            event.accept()
        else:
            event.ignore()
             
    def connectTemp(self):
        dll_path = os.path.join(os.getenv('ProgramFiles'),'Pico Technology', 'SDK', 'lib')
        try:
            self.tc08usb = TC08USB(dll_path = dll_path)
            if self.tc08usb.open_unit():
                self.tc08usb.set_mains(50)
                self.tc08usb.set_channel(1, USBTC08_TC_TYPE.K)
                self.getTemp()
                self.tempConnected = True
                self.updateTempTimer.start(1000)
            else:
                self.tempConnected = False
                self.connectTempAction.setChecked(False)
                QtGui.QMessageBox.critical(self,'Connection Error',
                                       'Could not connect to TC08-USB. Please try again')
                
        except USBTC08_ERROR as e:
            print(e)
        
        
    def createAction(self, text, slot=None, shortcut=None,
                     icon=None,tip=None,checkable=False,
                     signal='triggered()'):
        action = QtGui.QAction(text, self)
        if icon is not None:
            action.setIcon(QtGui.QIcon('../icons/%s.png' % icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        if tip is not None:
            action.setToolTip(tip)
            action.setStatusTip(tip)
        if slot is not None and not checkable:
            action.triggered.connect(slot)
        elif slot is not None and checkable:
            action.toggled.connect(slot)
        if checkable:
            action.setCheckable(True)
       
        return action
    
    def createGBox(self):
        self.zeroButton = QtGui.QRadioButton(text='0g')
        self.zeroButton.setChecked(True)
        self.zeroButton.setEnabled(False)
        self.minusButton = QtGui.QRadioButton(text='-1g')
        self.minusButton.setEnabled(False)
        self.plusButton = QtGui.QRadioButton(text='+1g')
        self.plusButton.setEnabled(False)
        
        gGroup = QtGui.QButtonGroup()
        gGroup.addButton(self.zeroButton)
        gGroup.addButton(self.minusButton)
        gGroup.addButton(self.plusButton)
        
        wg = QtGui.QWidget()
        lay = QtGui.QHBoxLayout()
        lay.addWidget(self.zeroButton)
        lay.addWidget(self.minusButton)
        lay.addWidget(self.plusButton)
        wg.setLayout(lay)
        
        return wg
        
        
    def createIdFrame(self):
        f = QtGui.QGroupBox(self, title='IDs:')
        l = QtGui.QGridLayout(f)
        font = QtGui.QFont()
        font.setBold(False)
        font.setPointSize(16)
        prodIdLabel = QtGui.QLabel(text='Produktion:', font=font) 
        self.proID = QtGui.QLineEdit(font=font)
        self.proID.setAlignment(QtCore.Qt.AlignRight)
        fbgIdLabel = QtGui.QLabel(text='FBG:', font=font) 
        self.fbgID = QtGui.QLineEdit(font=font)
        self.fbgID.setAlignment(QtCore.Qt.AlignRight)
        sensorIdLabel = QtGui.QLabel(text='Sensor:', font=font)
        self.sensorID = QtGui.QLineEdit(font=font)
        self.sensorID.setAlignment(QtCore.Qt.AlignRight)
        
        l.addWidget(prodIdLabel,0,0)
        l.addWidget(self.proID,0,1)
        l.addWidget(fbgIdLabel,1,0)
        l.addWidget(self.fbgID,1,1)
        l.addWidget(sensorIdLabel,2,0)
        l.addWidget(self.sensorID,2,1)
        
        return f
       
    def createInfoWidget(self):
        i = QtGui.QFrame()
        #i.setMaximumWidth(400)
        il = QtGui.QVBoxLayout()
        
        logo = QtGui.QLabel()
        logo.setPixmap(QtGui.QPixmap('../pics/Logo loptek.jpg'))
        logoLay = QtGui.QHBoxLayout()
        logoLay.addStretch()
        logoLay.addWidget(logo)
        
        il.addLayout(logoLay)
        il.addWidget(self.createIdFrame())
        
        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(20)
        isLabel = QtGui.QLabel(text='Ist')
        isLabel.setAlignment(QtCore.Qt.AlignCenter)
        isLabel.setFont(font)
        self.chan1IsLabel = QtGui.QLabel()
        self.chan1IsLabel.setText('0000.000')
        self.chan1IsLabel.setFont(font)
        tempLabel = QtGui.QLabel(text='Temperatur:')
        tempLabel.setFont(font)
        font.setBold(False)
        font.setPointSize(16)
        spinLabel = QtGui.QLabel(text='Points for Regression: ')
        #spinLabel.setFont(font)
        self.numPointsSpin = QtGui.QSpinBox()
        self.numPointsSpin.setRange(10,self.__maxBuffer)
        self.numPointsSpin.setValue(50)
        self.numPointsSpin.valueChanged.connect(self.plotW.setRegPoints)
        slopeLabel = QtGui.QLabel(text='Slope [pm/s]:')
        slopeLabel.setFont(font)
        dSlopeLabel = QtGui.QLabel(text= u'\u0394Slope [pm/s]:')
        dSlopeLabel.setFont(font)
        self.slopeCh1Label = QtGui.QLabel(text='---')
        self.slopeCh1Label.setFont(font)
        self.dSlopeCh1Label = QtGui.QLabel(text='---')
        self.dSlopeCh1Label.setFont(font)
        self.tempDisplay = QtGui.QLabel(text=u'-.- \u00b0C')
        font.setBold(True)
        font.setPointSize(16)
        self.tempDisplay.setAlignment(QtCore.Qt.AlignRight)
        self.tempDisplay.setFont(font)
        
        self.newButton = QtGui.QPushButton(text='Neu')
        self.saveButton = QtGui.QPushButton(text='Speichern')
        self.saveButton.setEnabled(False)
        self.measButton = QtGui.QPushButton(text='Messen')
        self.measButton.setFont(font)
        self.measButton.setEnabled(False)
        
        valLayout = QtGui.QGridLayout()
        valLayout.addWidget(isLabel,0,0)
        valLayout.addWidget(self.chan1IsLabel,1,0)
        valLayout.addWidget(slopeLabel,2,0)
        valLayout.addWidget(dSlopeLabel,2,1)
        valLayout.addWidget(self.slopeCh1Label,3,0)
        valLayout.addWidget(self.dSlopeCh1Label,3,1)
        valLayout.addWidget(spinLabel,4,0)
        valLayout.addWidget(self.numPointsSpin,4,1)
        valLayout.addWidget(tempLabel,0,1)
        valLayout.addWidget(self.tempDisplay,1,1)
        valLayout.addWidget(self.measButton,7,0,1,2)
        valLayout.addWidget(self.createGBox(),6,1)
        valLayout.addWidget(self.newButton,5,0)
        valLayout.addWidget(self.saveButton,5,1)
        
        self.newButton.clicked.connect(self.new)
        self.measButton.clicked.connect(self.measSensorParams)
        self.saveButton.clicked.connect(self.saveSensorParams)
        
        
        il.addLayout(valLayout)
        il.addStretch()
        i.setLayout(il)
        
        return i
        
        
    def createMenu(self):
        
        self.fileMenu = self.menuBar().addMenu('&File')
        self.maesMenu = self.menuBar().addMenu('&Measurement')
        self.helpMenu = self.menuBar().addMenu('&Help')
        waL = QtGui.QWidgetAction(self)
        dispSpinLabel = QtGui.QLabel(text='Points displayed: ')
        waL.setDefaultWidget(dispSpinLabel)
        
        #self.menuBar().addAction(wa)
        self.quitAction = self.createAction('Q&uit',slot=self.close,shortcut='Ctrl+Q',
                                            icon='Button Close',tip='Close App')
        self.connectAction = self.createAction('&Connect', slot=self.initDevice,
                                              tip='Connect Spectrometer', checkable = True,
                                              icon='Button Add')        
        self.connectTempAction = self.createAction('Thermo', slot=self.tempActionToggled, tip='Connect Thermometer',
                                                   checkable=True)
        
        self.startAction = self.createAction('St&art', slot=self.startMeasurement, shortcut='Ctrl+M',
                                             tip='Start Measurement', icon='Button Play')
#         #self.pauseAction = self.createAction('Pa&use', #slot=self.pauseMeasurement, shortcut='Ctrl+U', 
#          #                                    tip='Pause Measurement', icon='Button Pause')
#         
        self.stopAction = self.createAction('St&op', slot=self.stopMeasurement, shortcut='Ctrl+T',
                                        tip='Stop Measurment', icon='Button Stop')
        #self.dBmAction = self.createAction('dBm', tip='Plot logarithmic Data', checkable=True)
        #self.dBmAction.setChecked(True)
        
        self.showTraceAction = self.createAction('Trace', tip='Show Peakwavelength vs. Time', checkable=True)
        self.showTraceAction.setChecked(True)
        self.ptdAction = self.createPointsOfTraceAction()
        self.scalePlotAction = self.createScalePlotAction()
        self.scalePlotAction.setChecked(True)
        
        self.showSpecAction = self.createAction('Spec', slot=self.showPlot, tip='Show Spectrum', checkable=True)
        self.showSpecAction.setChecked(True)
        self.showTraceAction.toggled.connect(self.showPlot)
        
        self.showDBmData = self.createAction('dBm', tip='Plot Spectum as dBm Data', checkable=True)
        self.showDBmData.setChecked(True)
        
        
        
# 
        #self.addActions(self.fileMenu,(self.importFileAction, self.importLogAction, self.exportData))
        self.fileMenu.addAction(self.quitAction)
#        self.addActions(self.maesMenu, (self.startAction, self.stopAction))
        aboutAction = self.createAction('About', slot=self.about)
                                     
        self.helpMenu.addAction(aboutAction)
        
        self.toolbar = self.addToolBar('Measurement')
        
        #self.toolbar.addAction(self.connectAction)
        self.addActions(self.toolbar, (self.connectAction, self.connectTempAction, None, self.startAction, self.stopAction,
                                      None,  self.showTraceAction, self.ptdAction, None, 
                                      self.showSpecAction, self.scalePlotAction, self.showDBmData))#, self.importFileAction, self.importLogAction, self.exportData, None,self.showOptAction,None,self.fitAction, self.showFitAction))
        
    def createPointsOfTraceAction(self):
        wa = QtGui.QWidgetAction(self)
        s = QtGui.QSpinBox()
        s.setRange(100,self.__maxBuffer)
        s.setValue(500)
        sl = QtGui.QLabel(text='Points: ')
        self.plotW.setTracePoints(s.value())
        s.valueChanged.connect(self.plotW.setTracePoints)
        
        l = QtGui.QHBoxLayout()
        l.addWidget(sl)
        l.addWidget(s)
        
        w = QtGui.QWidget()
        w.setLayout(l)
        wa.setDefaultWidget(w)
        
        return wa
        
    def createScalePlotAction(self):
        wa = QtGui.QWidgetAction(self)
        
        self.minWlSpin = QtGui.QDoubleSpinBox()
        self.minWlSpin.setDecimals(3)
        self.minWlSpin.setSuffix(' nm')
        self.minWlSpin.setRange(1460.0,1619.0)
        self.minWlSpin.setValue(1540.0)
        self.minWlSpin.valueChanged.connect(self.scaleInputSpectrum)#self.plotW.setMinWavelength)
        
        self.maxWlSpin = QtGui.QDoubleSpinBox()
        self.maxWlSpin.setDecimals(3)
        self.maxWlSpin.setSuffix(' nm')
        self.maxWlSpin.setRange(1469.0, 1620.0)
        self.maxWlSpin.setValue(1570.0)
        self.maxWlSpin.valueChanged.connect(self.scaleInputSpectrum)#self.plotW.setMaxWavlength)
        
#==============================================================================
#         auto = QtGui.QCheckBox()
#         auto.setChecked(True)
#         auto.stateChanged.connect(self.setAutoScale)
#         
#==============================================================================
        
        l = QtGui.QHBoxLayout()
        l.addWidget(self.minWlSpin)
        l.addWidget(QtGui.QLabel(text=' - '))
        l.addWidget(self.maxWlSpin)
        #l.addWidget(auto)
        
        w = QtGui.QWidget()
        w.setLayout(l)
        wa.setDefaultWidget(w)
        
        return wa
    
    def disconnectTemp(self):
        if self.updateTempTimer.isActive():
            self.updateTempTimer.stop()
        if self.tempConnected:
                    self.tc08usb.close_unit()
        self.tempConnected = False
   
    def getData(self):
        #get spectra
        y = self.getdBmSpec()
        dbmData = y[self.__scalePos]
        wl = self.__scaledWavelength
        if self.showSpecAction.isChecked():
            if not self.showDBmData.isChecked():
                dbmData = np.power(10,dbmData/10)
            self.plotW.plotS(wl,dbmData)
        #get peak data

        numVal = self.getPeakData(wl, dbmData)
        if self.showTraceAction.isChecked():
            if numVal:
                self.plotW.plotT(self.peaksTime[:numVal-1], self.peaks[:numVal-1])
        
            
                   
        now = time.time()
        dt = now - self.lastTime
        if self.fps is None:
             self.fps = 1.0/dt
        else:
             s = np.clip(dt*3., 0, 1)
             self.fps = self.fps * (1-s) + (1.0/dt) * s
        self.statusBar().showMessage('%0.2f Hz' % (self.fps))
        self.lastTime = now
        
    def getdBmSpec(self):
        try:
            dbmData = np.array(self.si255.get_spectrum([1,]), dtype=float)
            
        except hyperion.HyperionError as e:
            print(e)
        
        return dbmData
        
    def getIDs(self):
        pro = self.proID.text()
        fbg = self.fbgID.text()
        sensor = self.sensorID.text()
        er = self.prodInfo.setIDs(pro, fbg, sensor)        
        return er
        
    def getPeakData(self, wl, dbmData):
        peak = self.centerOfGravity(wl, dbmData)
        timestamp = time.clock() - self.startTime
        numVal = np.count_nonzero(self.peaks)
        self.chan1IsLabel.setText(str("{0:.3f}".format(peak)))
                
        if numVal < self.__maxBuffer:
            self.peaks[numVal] = peak
            self.peaksTime[numVal] = timestamp
        else:
            self.peaks = shift(self.peaks, -1, cval = peak)
            self.peaksTime = shift(self.peaksTime, -1, cval = timestamp)
            
        return numVal
        
    def getTemp(self):
        self.tc08usb.get_single()
        temp = self.tc08usb[1]
        tempStr = str("{0:.1f}".format(temp)) + u' \u00b0C'
        self.tempDisplay.setText(tempStr)
        
                
    def saveSensorParams(self):
        self.calcSensorParams()
        self.qcFolder
        fname = self.sensorID.text() + '_'+time.strftime('%Y%m%d_%H%M%S') + '.spc'
        _file = os.path.join(str(self.qcFolder) , str(fname))  
        cen = np.around(self.gPeaks, decimals=3)
        fwhm = np.around(self.gFWHM,decimals=3)
        cog = np.around(self.gCOG, decimals=3)
        asym = np.around(self.gAsym, decimals=3)
        sens = np.around(self.gSens, decimals=3)
        File = open(_file,'w')
        File.write('Datum: '+ time.strftime('%d-%m-%Y %H:%M:%S')+'\n')
        File.write('Sensor: ' + self.sensorID.text() +'\n')
        File.write('FBG: ' + self.fbgID.text() +'\n')
        File.write('Produktions ID: ' + self.proID.text() +'\n')
        File.write('Temperatur: ' + self.tempDisplay.text() + '\n\n')
        File.write('g-Wert\t Peak-Wl [nm]\t FWHM [nm]\t CoG [nm] \t Asymmetrie [nm]\n')
            
        for i in range(3):
            File.write(str(self.gLabel[i]) + '\t'+ str(cen[i])+ '\t'+ str(fwhm[i])+'\t'+ str(cog[i])+'\t'+ str(asym[i])+'\n')
        
        File.write('\nEmpfindlichkeit: ' + str(sens[0]) + '(-1g); ' + str(sens[1]) + '(+1g)\n')
        File.close()
        
        temp = self.tempDisplay .text().split(' ')[0]
        self.log.setSensorParams(self.sensorIndex, cen, fwhm, cog, asym, sens, temp)
    
    def saveSpectrum(self, x, y,gLabel):
        if len(x) == 0:
            y = self.getdBmSpec()
            x = self.__wavelength
        fname = time.strftime('%Y%m%d_%H%M%S') + self.sensorID.text() +'_'+ str(gLabel) + '.spc'
        #print(self.specFolder, fname)
        _file = os.path.join(str(self.specFolder) , str(fname))  
        
        File = open(_file,'w')
        for i in range(len(x)):
            File.write(str("{0:.3f}".format(x[i])) + '\t' + str(y[i]) + '\n')
        File.close()
        return fname
            
    def scaleInputSpectrum(self):
        _min = float(self.minWlSpin.value())
        _max = float(self.maxWlSpin.value())
        if _min > _max:
            _min = _max-1
        if _max < _min:
            _max = _min+1
        self.__scalePos = np.where((self.__wavelength>=_min)&(self.__wavelength<=_max))[0]
        self.__scaledWavelength = self.__wavelength[self.__scalePos]
        
        
    def setActionState(self):
        if self.isConnected:
            self.connectAction.setEnabled(False)
            if self.measurementActive:
                self.startAction.setEnabled(False)
                self.stopAction.setEnabled(True)
            else:
                self.startAction.setEnabled(True)
                self.stopAction.setEnabled(False)
        else:
            self.connectAction.setEnabled(True)
            self.startAction.setEnabled(False)
            self.stopAction.setEnabled(False)
            
    def setProdIDs(self, proID, sensorID):
        self.proID.setText(proID)
        self.fbgID.clear()
        self.sensorID.setText(sensorID)
            
    def setSlope(self, slope, Dslope):
        self.slopeCh1Label.setText(slope)
        self.dSlopeCh1Label.setText(Dslope)  
        
#==============================================================================
#     def setAutoScale(self, state):
#         if state:
#             self.minWlSpin.setEnabled(True)
#             self.maxWlSpin.setEnabled(True)
#             self.plotW.setAutoScaleWavelength(True)
#         else:
#             self.minWlSpin.setEnabled(False)
#             self.maxWlSpin.setEnabled(False)
#             self.plotW.setAutoScaleWavelength(False)
#         
#==============================================================================
    def showPlot(self):
        plotT = self.showTraceAction.isChecked()
        plotS = self.showSpecAction.isChecked()
        self.ptdAction.setEnabled(plotT)
        self.showDBmData.setEnabled(plotS)
        self.plotW.setShowPlot(plotT, plotS)
        
    def startMeasurement(self):
        self.startTime = time.clock()
        self.lastTime= self.startTime
        self.fps=None
        self.peaks = np.zeros(self.__maxBuffer)
        self.updateTimer.start(100)
        self.measurementActive = True
        self.setActionState()
        
    def stopMeasurement(self):
        self.updateTimer.stop()
        self.measurementActive = False
        self.setActionState()
    

    def testChannelForPeaks(self, Channel = 1):
        i = Channel
        numFBGs = 0
        try:
            peaks = self.si255.get_peaks()
            peakData  = peaks.get_channel(i)
            numFBGs = len(peakData)
            print('Channel ',i,' ',numFBGs,' Gitter')
        except:
            pass
        return numFBGs
                
    def tempActionToggled(self, state):
        if state:
            self.connectTemp()
        else:
            self.disconnectTemp()
            
      
#### calculations
    
    def measSensorParams(self):
        index = 0
        y = self.getdBmSpec()
        x = self.__wavelength
        if self.zeroButton.isChecked() & self.zeroButton.isEnabled():
            index = 0
            self.zeroButton.setEnabled(False)
            self.minusButton.setChecked(True)
        elif self.minusButton.isChecked() & self.minusButton.isEnabled():
            index = 1
            self.minusButton.setEnabled(False)
            self.plusButton.setChecked(True)
        elif self.plusButton.isChecked() & self.plusButton.isEnabled():
            index = 2            
            self.plusButton.setEnabled(False)
            self.zeroButton.setChecked(True)
            self.measButton.setEnabled(False)
            self.saveButton.setEnabled(True)
        self.saveSpectrum(x,y,self.gLabel[index])
        center, fwhm = self.peakFit(x,y)
        self.gPeaks[index] = center
        self.gFWHM[index] = fwhm
        cog = self.centerOfGravity(x,y)
        self.gCOG[index] = cog
        self.gAsym[index] = self.calculateAsym(center,cog)
        
    def calcSensorParams(self):
        self.gSens[0] = np.abs(self.gPeaks[0] - self.gPeaks[1])
        self.gSens[1] = np.abs(self.gPeaks[2] - self.gPeaks[0])
            
        
   
    def peakFit(self, x, y):
        if len(x) == 0:
            y = self.getdBmSpec()
            y = y[self.__scalePos]
            x = self.__scaledWavelength
        y = np.power(10,y/10)
        mod = GaussianModel()
        pars = mod.guess(y, x=x)
        out  = mod.fit(y, pars, x=x)
        
        print(out.fit_report(min_correl=0.25))
        center = out.best_values['center']
        fwhm = out.best_values['sigma']*2.3548
        
        return center, fwhm#, amp
   
    def centerOfGravity(self, x, y):
        if len(x) == 0:
            y = self.getdBmSpec()
            y = y[self.__scalePos]
            x = self.__scaledWavelength
        y = np.power(10,y/10)
        pos = np.where(y>(np.max(y)*.3))[0]
        x = x[pos]
        y = y[pos]
           
        cog = (x*y).sum()/y.sum()
        return cog
   
    def calculateAsym(self, pFit, pCOG):
        if pFit:
            return np.abs(pFit-pCOG)
        else:
            return 0
        

class NewSensorDialog(QtGui.QDialog):
    def __init__(self, ids=None, *args):
        QtGui.QDialog.__init__(self, *args) 
        
        self.index = 0
        self.setWindowTitle('Sensorauswahl')
        self.setMinimumWidth(200)
        self.idCombo = QtGui.QComboBox()
        self.idCombo.addItems(ids)    
        lay = QtGui.QVBoxLayout()
        ok = QtGui.QPushButton(text='OK')
        ok.clicked.connect(self.accept)
        lay.addWidget(self.idCombo)
        lay.addWidget(ok)
        self.setLayout(lay)
        
        self.idCombo.currentIndexChanged.connect(self.setIndex)
        
    def setIndex(self, index):
        self.index = index
        #print(self.index)
            
    def setSensor(self):
        return self.index
        
        
        