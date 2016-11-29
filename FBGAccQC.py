# -*- coding: utf-8 -*-
"""
Created on Fri Oct  2 10:08:32 2015

@author: flehr
"""
from pyqtgraph.Qt import QtGui
import sys

import MainWindow as mw


app = QtGui.QApplication(sys.argv)
spectra = mw.MainWindow()
spectra.show()
app.exec_()