# -*- coding: utf-8 -*-
"""
Created on Wed Feb 10 06:38:58 2016

ToDo:
Doku
- test for last entry
- write data in table

Anweisung:
- zu messende bzw berechnende Größen übergeben bzw anfordern
- IDs
@author: Roman
"""

from PyQt4 import QtCore
from openpyxl import load_workbook

class ProductionLog(QtCore.QObject):
    #emitProdIds = QtCore.pyqtSignal('list', 'list)
    
    #emitGetIDs = QtCore.pyqtSignal()
    #emitTestFbg = QtCore.pyqtSignal(int) # int - channel number
    def __init__(self, *args):
        QtCore.QObject.__init__(self, *args)
        
        self.excel = '..\..\FBGAcc_ProdutionsLog.xlsx'
        
        self.__logStartRow = 5        
        self.__logRow = self.__logStartRow      
        self.__prodID = []
        self.__fbgID = []
        self.__sensID = []
        self.__idRow = []
        
        
        self.loadProductionLog()
        
               
    def loadProductionLog(self, _file = None):
        print('Load productiontable')
        self.wb = load_workbook(filename=self.excel)
        
        self.__log = self.wb['acc_Produktion']
        
        content = True
        while content:
            cell = self.__log['A'+str(self.__logRow)].value
            #print('Zeile ', str(self.__logRow),': ', cell)
            if cell:
                content = True
                if not self.__log['O'+str(self.__logRow)].value:
                    self.__prodID.append(self.testCell(cell))
                    cell = self.__log['B'+str(self.__logRow)].value
                    self.__fbgID.append(self.testCell(cell))
                    cell = self.__log['C'+str(self.__logRow)].value
                    self.__sensID.append(self.testCell(cell))
                    self.__idRow.append(self.__logRow)
                self.__logRow +=1
                
            else:
                content = False
            
           
    def testCell(self,cell): 
        if cell:
             cell = unicode(cell)
        else:
             cell = unicode('')
        return cell    
        
        
    def getIDbyIndex(self, index = -1):
        return self.__prodID[index], self.__fbgID[index], self.__sensID[index]
        
    def getSensorIDs(self):
        return self.__sensID
        
    def setSensorParams(self, index, center, fwhm, cog, asym, sens, temp):
        row = str(self.__idRow[index])
        self.__log['O'+row].value = center[0]
        self.__log['Q'+row].value = str(temp)
        self.__log['R'+row].value = asym[0]
        self.__log['S'+row].value = fwhm[0]
        self.__log['T'+row].value = center[2]
        self.__log['U'+row].value = sens[1]
        self.__log['V'+row].value = asym[2]
        self.__log['W'+row].value = fwhm[2]
        self.__log['X'+row].value = center[1]
        self.__log['Y'+row].value = sens[0]
        self.__log['Z'+row].value = asym[1]
        self.__log['AA'+row].value = fwhm[1]
        
        self.wb.save(self.excel)