from __future__ import division
import numpy as np
import scipy.stats as stats
from PyQt4 import QtCore, QtGui

import logging
import os
from matplotlib.backends.backend_qt4agg import FigureCanvas #ensure matplotlib is updated
from matplotlib.figure import Figure
from matplotlib.pyplot import Line2D
from matplotlib import patches
from matplotlib import cm
from random import randint
from copy import deepcopy
import pickle
from listquote import LineParser
#import cv2

from matplotlib import rcParams

if rcParams['backend.qt4']!='PyQt4':
    raise ValueError('matplotlib.rcParams[\'backend.qt4\'] should be = PyQt4. Edit matplotlibrc file')  

import spot

'''
try:
    from numba import jit  # used for detrending maths. Not required.
except ImportError:
    logging.warning('Numba is not installed. Please install numba package for optimal performance!')

    def jit(a):
        return a
'''
__author__ = 'chris+edmund'

LIST_ITEM_ENABLE_FLAG = QtCore.Qt.ItemFlag(QtCore.Qt.ItemIsSelectable + QtCore.Qt.ItemIsEnabled +
                                           QtCore.Qt.ItemIsDragEnabled + QtCore.Qt.ItemIsUserCheckable)  # 57



class CalibrationViewer(QtGui.QMainWindow):

    def __init__(self):
        self.filters = list()
        super(CalibrationViewer, self).__init__()
        self.autolabel=1 #automatically generate pattern labels
        self.setWindowTitle('Pattern stim')
        self.statusBar()
        self.trial_selected_list = []
        self.session_id=0
        self.sess_list=[]
        self.spots={}
        self.stim_types=['target','nontarget','probe']
        self.file_list=[]
        self.fn=''
        self.gridmax=[]
        self.DMD_dim=[]
        self.update_mode=True


        self.random_spacing=1.5 #when generating new spot, the minimum spot spacing from others in self.spots['list']

        mainwidget = QtGui.QWidget(self)
        self.setCentralWidget(mainwidget)
        layout = QtGui.QVBoxLayout(mainwidget)
        mainwidget.setLayout(layout)

        self.statusbar = QtGui.QStatusBar()
        self.setStatusBar(self.statusbar)

        #===menu items====
        menu = self.menuBar()
        filemenu = menu.addMenu("&File")
        toolsmenu = menu.addMenu("&Tools")
        openAction = QtGui.QAction("&Open datafile...", self)
        openAction.triggered.connect(self._openAction_triggered)
        openAction.setStatusTip("Open a processed results file.")
        openAction.setShortcut("Ctrl+O")
        filemenu.addAction(openAction)

        #==save to current file==
        saveAllAction = QtGui.QAction('&Save to current file...', self)
        saveAllAction.triggered.connect(self._saveAllAction_triggered)
        saveAllAction.setShortcut('Ctrl+S')
        saveAllAction.setStatusTip("Saves patterns,spots and options to pickle.")
        filemenu.addAction(saveAllAction)

        #==save as==
        saveAsAction = QtGui.QAction('Save to new file...', self)
        saveAsAction.triggered.connect(self._saveAsAction_triggered)
        filemenu.addAction(saveAsAction)
        
        
        #==full screen==
        screenAction = QtGui.QAction("Toggle screen size...", self)
        screenAction.triggered.connect(self._screenAction_triggered)
        screenAction.setStatusTip("Toggle screen.")
        screenAction.setShortcut("Ctrl+E")
        filemenu.addAction(screenAction)



        #===quit===        
        exitAction = QtGui.QAction("&Quit", self)
        exitAction.setShortcut("Ctrl+Q")
        exitAction.setStatusTip("Quit program.")
        exitAction.triggered.connect(QtGui.qApp.quit)
        filemenu.addAction(exitAction)

        #===toggle auto-label===
        autolabelAction = QtGui.QAction("&Autolabel", self)
        autolabelAction.setStatusTip('Apply auto-labelling to new sessions.')
        autolabelAction.triggered.connect(self._make_autolabel_all)
        toolsmenu.addAction(autolabelAction)


        #===fix spots===
        displayParamsAction = QtGui.QAction("&Finalize spots", self)
        displayParamsAction.setStatusTip('Finalize spot definitions.')
        displayParamsAction.triggered.connect(self._finalize_spots)
        toolsmenu.addAction(displayParamsAction)

        #===fix spots===
        QAction = QtGui.QAction("Set 1st session number", self)
        QAction.triggered.connect(self._set_first_sess)
        toolsmenu.addAction(QAction)


        row1_layout = QtGui.QHBoxLayout()
        row2_layout = QtGui.QHBoxLayout()
        layout.addLayout(row1_layout)
        layout.addLayout(row2_layout)

        #===session list====
        sess_select_box = QtGui.QGroupBox()
        sess_select_layout = QtGui.QVBoxLayout()
        sess_select_box.setLayout(sess_select_layout)
        sess_select_box.setTitle('Sessions')
        sess_select_box.setFixedWidth(100)
        self.sess_select = SessListWidget()
        sess_select_layout.addWidget(self.sess_select)
        self.sess_select.itemSelectionChanged.connect(self._sess_select_changed)
        row1_layout.addWidget(sess_select_box)
        self.sess_select.showh5Sig.connect(self.showh5)
        self.sess_select.deleteSessionSig.connect(self.delete_session)

        #define push button to generate new session
        self.new_session_btn = QtGui.QPushButton('Add')
        self.new_session_btn.clicked.connect(self._new_session)
        sess_select_layout.addWidget(self.new_session_btn)

        #===session info===
        sess_info_box = QtGui.QWidget()
        sess_info_layout = QtGui.QVBoxLayout()
        row1_layout.addWidget(sess_info_box)
        sess_info_box.setLayout(sess_info_layout)
        sess_info_box.setFixedWidth(150)

        self.sess_info = SessInfoWidget()
        self.sess_comments = SessCommentsWidget()
        self.sess_option_select = SessOptionSelectWidget()
        self.sess_option_select.currentIndexChanged.connect(self._sess_option_select_changed)

        self.sess_option_value = SessOptionValueWidget()


        sess_info_layout.addWidget(self.sess_info)
        sess_info_layout.addWidget(self.sess_comments)
        sess_info_layout.addWidget(self.sess_option_select)
        sess_info_layout.addWidget(self.sess_option_value)


        #===session plot===
        plots_box = QtGui.QGroupBox()
        plots_box.setTitle('Session Plot')
        plots_layout = QtGui.QHBoxLayout()

        self.figure = Figure((9, 5))
        self.figure.patch.set_facecolor('white')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(plots_box)
        self.canvas.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        plots_layout.addWidget(self.canvas)
        plots_box.setLayout(plots_layout)
        row1_layout.addWidget(plots_box)
        self.ax_sess = self.figure.add_subplot(1, 1, 1)
        self.ax_sess.set_title('Left bias')
        self.ax_sess.set_ylabel('%')
        self.ax_sess.set_xlabel('Trial')
        #self.ax_mean_plots.autoscale(enable=True, axis=u'both', tight=False)
        self.figure.tight_layout()

        #===defined spot list===
        spot_select_box = QtGui.QGroupBox()
        spot_select_layout = QtGui.QVBoxLayout()
        spot_select_layout.setSpacing(0)
        spot_select_box.setLayout(spot_select_layout)
        spot_select_box.setTitle('Defined spots')
        spot_select_box.setFixedWidth(100)
        self.spot_select = SpotListWidget()
        self.spot_select.itemSelectionChanged.connect(self._spot_select_changed)
        spot_select_layout.addWidget(self.spot_select)
        self.spot_select.renameSpotSig.connect(self.rename_spot)
        self.spot_select.deleteSpotSig.connect(self.delete_spot)
        self.spot_select.RNGSpotSig.connect(self.RNG_spot)
        self.spot_select.emptySpotSig.connect(self.empty_spot)

        #===spot x, y coordinate entry boxes==
        spot_xy_box = QtGui.QGroupBox()
        spot_xy_box.setFlat(True)

        spot_xy_layout = QtGui.QHBoxLayout()
        spot_xy_box.setLayout(spot_xy_layout)
        spot_select_layout.addWidget(spot_xy_box)

        self.spot_x=QtGui.QLineEdit()
        self.spot_y=QtGui.QLineEdit()
        spot_xy_layout.addWidget(self.spot_x)
        spot_xy_layout.addWidget(self.spot_y)
        spot_xy_layout.setSpacing(0)


        #==button to add new spot==
        self.new_spot_btn = QtGui.QPushButton('New')
        self.new_spot_btn.clicked.connect(self._new_spot)
        spot_select_layout.addWidget(self.new_spot_btn)

        self.redo_spot_btn = QtGui.QPushButton('Redo')
        self.redo_spot_btn.clicked.connect(self._redo_spot)
        spot_select_layout.addWidget(self.redo_spot_btn)




        row2_layout.addWidget(spot_select_box)


        #===spot(s) display===
        spot_disp_box = QtGui.QGroupBox()
        spot_disp_layout = QtGui.QHBoxLayout()
        #spot_disp_box.setFixedWidth(200)

        self.spot_disp_figure = Figure()
        self.spot_disp_figure.patch.set_facecolor('white')
        self.spot_disp_canvas = FigureCanvas(self.spot_disp_figure)
        self.spot_disp_canvas.setParent(spot_disp_box)
        #self.spot_disp_canvas.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        #self.spot_disp_canvas.setFixedHeight(200)
        spot_disp_layout.addWidget(self.spot_disp_canvas)
        spot_disp_box.setLayout(spot_disp_layout)
        row2_layout.addWidget(spot_disp_box)
        self.ax_spot_disp = self.spot_disp_figure.add_subplot(1, 1, 1)

        #===pattern sequence list===
        pattern_select_box = QtGui.QGroupBox()
        pattern_select_layout = QtGui.QVBoxLayout()
        pattern_select_layout.setSpacing(0)
        pattern_select_box.setLayout(pattern_select_layout)
        pattern_select_box.setTitle('Session-defined patterns')
        pattern_select_box.setFixedWidth(280)
        self.pattern_select = PatternSelectWidget()
        self.pattern_select.currentIndexChanged.connect(self._pattern_select_changed)
        self.pattern_select.deletePatternSig.connect(self.delete_pattern)

        pattern_select_layout.addWidget(self.pattern_select)
        row2_layout.addWidget(pattern_select_box)

        #==pattern spot list==
        self.patternspot_select = PatternspotListWidget()
        self.patternspot_select.itemSelectionChanged.connect(self._patternspot_select_changed)
        pattern_select_layout.addWidget(self.patternspot_select)


        #==pattern spot onset and duration==
        spot_timing_layout = QtGui.QHBoxLayout()
        spot_timing_box = QtGui.QGroupBox()
        spot_timing_box.setLayout(spot_timing_layout)
        spot_timing_box.setFlat(True)
        pattern_select_layout.addWidget(spot_timing_box)

        self.spot_onset=QtGui.QLineEdit()
        self.spot_onset.setStatusTip("To specify random, input 'lower, upper' e.g. 10,80")
        self.spot_dur=QtGui.QLineEdit()
        self.spot_dur.setStatusTip("To specify random, input 'lower, upper' e.g. 10,80")
        self.spot_intensity=QtGui.QLineEdit()
        self.spot_intensity.setStatusTip("0-255. For random, input 'lower, upper'. e.g. 0,255")

        spot_onset_box= QtGui.QGroupBox()
        spot_onset_layout=QtGui.QVBoxLayout()
        spot_onset_box.setLayout(spot_onset_layout)
        spot_onset_layout.addWidget(self.spot_onset)
        spot_onset_box.setTitle('Onset')

        spot_dur_box= QtGui.QGroupBox()
        spot_dur_layout=QtGui.QVBoxLayout()
        spot_dur_box.setLayout(spot_dur_layout)
        spot_dur_layout.addWidget(self.spot_dur)
        spot_dur_box.setTitle('Dur')

        spot_intensity_box= QtGui.QGroupBox()
        spot_intensity_layout=QtGui.QVBoxLayout()
        spot_intensity_box.setLayout(spot_intensity_layout)
        spot_intensity_layout.addWidget(self.spot_intensity)
        spot_intensity_box.setTitle('Pwr')


        spot_timing_layout.addWidget(spot_onset_box)
        spot_timing_layout.addWidget(spot_dur_box)
        spot_timing_layout.addWidget(spot_intensity_box)        
        spot_timing_layout.setSpacing(0)

        #==pattern grouping==
        spot_grouping_layout = QtGui.QHBoxLayout()
        spot_grouping_box = QtGui.QGroupBox()
        spot_grouping_box.setLayout(spot_grouping_layout)
        spot_grouping_box.setFlat(True)
        pattern_select_layout.addWidget(spot_grouping_box)

        self.spot_grouptime=QtGui.QLineEdit()
        self.spot_grouptime.setStatusTip("group number, offset. e.g. 1, 20 means 20 ms after group 1")
        generic_box= QtGui.QGroupBox()
        generic_layout=QtGui.QVBoxLayout()
        generic_box.setLayout(generic_layout)
        generic_layout.addWidget(self.spot_grouptime)
        generic_box.setTitle('group time')
        spot_grouping_layout.addWidget(generic_box)


        self.sequence_omit=QtGui.QLineEdit()
        self.sequence_omit.setStatusTip("Randomly choose n spots to omit from pattern on each trial")
        generic_box= QtGui.QGroupBox()
        generic_layout=QtGui.QVBoxLayout()
        generic_box.setLayout(generic_layout)
        generic_layout.addWidget(self.sequence_omit)
        generic_box.setTitle('Omit')        
        spot_grouping_layout.addWidget(generic_box)
        
        self.sequence_replace=QtGui.QLineEdit()
        self.sequence_replace.setStatusTip("Randomly choose n spots to replace with random pool spot ")
        generic_box= QtGui.QGroupBox()
        generic_layout=QtGui.QVBoxLayout()
        generic_box.setLayout(generic_layout)
        generic_layout.addWidget(self.sequence_replace)
        generic_box.setTitle('Sub')
        spot_grouping_layout.addWidget(generic_box)        

        
        self.sequence_scramble=QtGui.QLineEdit()
        self.sequence_scramble.setStatusTip("Scramble order while preserving timing.")
        generic_box= QtGui.QGroupBox()
        generic_layout=QtGui.QVBoxLayout()
        generic_box.setLayout(generic_layout)
        generic_layout.addWidget(self.sequence_scramble)
        generic_box.setTitle('scramble')
        spot_grouping_layout.addWidget(generic_box)

        self.sequence_randt=QtGui.QLineEdit()
        self.sequence_randt.setStatusTip("Randomize timing.")
        generic_box= QtGui.QGroupBox()
        generic_layout=QtGui.QVBoxLayout()
        generic_box.setLayout(generic_layout)
        generic_layout.addWidget(self.sequence_randt)
        generic_box.setTitle('randt')
        spot_grouping_layout.addWidget(generic_box)

        spot_grouping_layout.setSpacing(0)


        #==button to add/remove spot from pattern==
        self.patternspot_transfer_btn = QtGui.QPushButton('Add Spot')
        self.patternspot_transfer_btn.clicked.connect(self._patternspot_transfer)
        pattern_select_layout.addWidget(self.patternspot_transfer_btn)

        #==buttons to add new pattern==
        self.pattern_add_btn = QtGui.QPushButton('Add Pattern')
        self.pattern_add_btn.clicked.connect(self._add_pattern)
        pattern_select_layout.addWidget(self.pattern_add_btn)


        #====box that displays timing image===
        timing_disp_box = QtGui.QGroupBox()
        timing_disp_layout = QtGui.QHBoxLayout()

        self.timing_disp_figure = Figure()
        self.timing_disp_figure.patch.set_facecolor('white')
        self.timing_disp_canvas = FigureCanvas(self.timing_disp_figure)
        self.timing_disp_canvas.setParent(timing_disp_box)
        self.timing_disp_canvas.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        self.timing_disp_canvas.setFixedHeight(200)
        timing_disp_layout.addWidget(self.timing_disp_canvas)
        timing_disp_box.setLayout(timing_disp_layout)
        row2_layout.addWidget(timing_disp_box)
        self.ax_timing_disp = self.timing_disp_figure.add_subplot(1, 1, 1)
        self.ax_timing_disp.set_frame_on(False)
        self.ax_timing_disp.get_xaxis().tick_bottom()
        self.ax_timing_disp.axes.get_yaxis().set_visible(False)

        #===create lists for stim definitions===
        self.stim_widgets={}

        stim_select_width=200
        for s in self.stim_types:
            self.stim_widgets[s]={}
            self.stim_widgets[s]['select_box']=QtGui.QGroupBox()
            select_layout = QtGui.QVBoxLayout()
            self.stim_widgets[s]['select_box'].setLayout(select_layout)
            self.stim_widgets[s]['select_box'].setTitle(s)
            self.stim_widgets[s]['select_box'].setFixedWidth(stim_select_width)
            self.stim_widgets[s]['select'] = StimListWidget(s)
            select_layout.addWidget(self.stim_widgets[s]['select'])




            #==button to add/remove pattern from Stim list==
            self.stim_widgets[s]['transfer_btn'] = QtGui.QPushButton('Add')
            select_layout.addWidget(self.stim_widgets[s]['transfer_btn'])
            
            #==button to add/remove odors==
            self.stim_widgets[s]['add_odor'] = QtGui.QPushButton('Add odor')
            self.stim_widgets[s]['add_odor'].setObjectName(s)                                                                 
            select_layout.addWidget(self.stim_widgets[s]['add_odor'])
            self.stim_widgets[s]['add_odor'].clicked.connect(self._add_odor)
            x = QtGui.QPushButton('x') 

        #==unresolved: in passing arguments to lambda functions, so I can't just pass s in a loop==
        self.stim_widgets[self.stim_types[0]]['transfer_btn'].clicked.connect(lambda: self._stim_transfer(self.stim_types[0]))
        self.stim_widgets[self.stim_types[1]]['transfer_btn'].clicked.connect(lambda: self._stim_transfer(self.stim_types[1]))
        self.stim_widgets[self.stim_types[2]]['transfer_btn'].clicked.connect(lambda: self._stim_transfer(self.stim_types[2]))


        self.stim_widgets[self.stim_types[0]]['select'].itemSelectionChanged.connect(lambda: self._stim_select_changed(self.stim_types[0]))
        self.stim_widgets[self.stim_types[1]]['select'].itemSelectionChanged.connect(lambda: self._stim_select_changed(self.stim_types[1]))
        self.stim_widgets[self.stim_types[2]]['select'].itemSelectionChanged.connect(lambda: self._stim_select_changed(self.stim_types[2]))




        row1_layout.addWidget(self.stim_widgets[self.stim_types[0]]['select_box'])
        row1_layout.addWidget(self.stim_widgets[self.stim_types[1]]['select_box'])
        row2_layout.addWidget(self.stim_widgets[self.stim_types[2]]['select_box'])


    def _format_option_dtype(self,optionval,option):
        """returns dtype (pre-defined) of voyeur option. maybe implement as class??"""
        floats=['reinforcementpercentage','ratio_training','ratio_probe','ratio_training_probe']
        ints=['debias','gridsize','graylevel','initialtrials',
              'laserdur','fvdur','lickgraceperiod','order','probeMode']
        strings=['initialport','mouse_protocol','protocol_type','rig']

        if option in floats:
            try:
                return float(optionval)
            except ValueError:
                type_required='float'
        elif option in ints:
            try:
                return int(optionval)
            except ValueError:
                type_required='int'
        else:
            try:
                return str(optionval)
            except ValueError:
                type_required='str'

        message = 'Cannot parse input. Type '+type_required+ ' required.'
        msgBox = QtGui.QMessageBox()
        msgBox.setText(message)
        msgBox.exec_()

    @QtCore.pyqtSlot()
    def _openAction_triggered(self):
        filedialog = QtGui.QFileDialog(self)
        startpath = 'C:/voyeur_rig_config/'
        self.fn = filedialog.getOpenFileName(self, "Select a data file.", startpath, "pickle (*.pickle)", "", QtGui.QFileDialog.DontUseNativeDialog)
        #self.fn='template.pickle'
        self.setWindowTitle(self.fn)

        if self.fn:
            with open(self.fn) as f:
                [sess_list,spots]=pickle.load(f)

            if 'emulation' not in spots: #maintain backward compatibility
                spots['emulation']=False
                
            #===populate defined spots==
            self.spots= spots
            self.spot_select.clear()

            spotNames = self.spots['list'].keys()
            spotNames.sort()
            for i, tstr in enumerate(spotNames):
                it = QtGui.QListWidgetItem(tstr, self.spot_select)

            if self.spots['finalized']:
                self.spot_x.setReadOnly(True)
                self.spot_y.setReadOnly(True)
            else:
                self.spot_x.setReadOnly(False)
                self.spot_y.setReadOnly(False)

                self.spot_x.returnPressed.connect(self._xy_changed)
                self.spot_y.returnPressed.connect(self._xy_changed)

            #===populate session info===
            self.sess_list = sess_list
            self.sess_select.clear()

            sessions = [sess['post']['id'] for sess in sess_list]
            completed = [sess['completed'] for sess in sess_list]
            
            for tstr,complete in zip(sessions,completed):
                it = QtGui.QListWidgetItem(tstr, self.sess_select)
                
                if complete:
                    it.setTextColor(QtGui.QColor(127,127,127))
                else:
                    it.setTextColor(QtGui.QColor(0,0,0))
                    
            self.sess_select.setCurrentRow(0)


            for i in range(self.spot_select.count()):
                self.spot_select.item(i).setSelected(True)



        else:
            print('No file selected.')
        return

    def _screenAction_triggered(self):
        if self.windowState() == QtCore.Qt.WindowMaximized:
            self.showNormal()
        else:
            self.showMaximized()


    def _rand_xy(self,(x_max,y_max),spacing, ref_spots=np.array([-99,-99])):
        if self.rig == 'ALP2':
            return self._rand_xy_offset(spacing,ref_spots)

        #pick random x,y coordinate to define non-overlapping spots
        #spacing: minimum euclidean distance between spots, measured by number of spots
        #e.g. 1 means spots cannot be above, below, left, or right, but can be diagonal [distance = sqrt(2)]
        #can also supply ref_spots (n-by-2 array) that new spots must not overlap with
        #spacing < 0 means spots can overlap

        if ref_spots.shape==(2L,):
            ref_spots=ref_spots.reshape(1L,2L) #if only one spot, need to reshape for concatenation later

        new_spot=[]#container holding all spot values, initialized to -99 (to avoid affecting distance calc)

        max_loop=10000

        for j in range(max_loop):
            x=randint(0,x_max)
            y=randint(0,y_max)
            euclid_dist=np.sqrt(np.sum((ref_spots-[x,y])**2,1))
            if euclid_dist.min() > spacing:
                new_spot=[x,y]
                break
            elif j==max_loop-1:
                raise ValueError('max iterations reached, no possible spot found')

        return new_spot

    def _rand_xy_offset(self,spacing, ref_spots=np.array([-99,-99])):
        #for ALP2. grid does not start from (0,0)

        if self.rig !='ALP2':
            raise ValueError('Inappropriate randomization for rig'+str(self.rig))

        if ref_spots.shape==(2L,):
            ref_spots=ref_spots.reshape(1L,2L) #if only one spot, need to reshape for concatenation later

        new_spot=[]#container holding all spot values, initialized to -99 (to avoid affecting distance calc)

        max_loop=10000

        for j in range(max_loop):
            x=randint(self.grid[0][0],self.grid[0][1])
            y=randint(self.grid[1][0],self.grid[1][1])
            euclid_dist=np.sqrt(np.sum((ref_spots-[x,y])**2,1))
            if euclid_dist.min() > spacing:
                new_spot=[x,y]
                break
            elif j==max_loop-1:
                raise ValueError('max iterations reached, no possible spot found')

        return new_spot

    def _saveAllAction_triggered(self):
        if not self._check_last_session():
            return

        #==save comments==

        self.sess_list[self.session_id]['post']['comments']=str(self.sess_comments.toPlainText())
        
        #===update pickle file===
        with open(self.fn, 'wb') as f:
            pickle.dump([self.sess_list, self.spots], f)
            
        
    def _saveAsAction_triggered(self):
        if not self._check_last_session():
            return
        
        
        self.saveDialog = QtGui.QFileDialog()
        saveloc = self.saveDialog.getSaveFileName(self, 'Save As', '', 'pickle (*.pickle)')
        saveloc = str(saveloc)
        print saveloc
        self.fn = saveloc
        #===new pickle file===
        with open(self.fn, 'wb') as f:
            pickle.dump([self.sess_list, self.spots], f)
            
        self.setWindowTitle(self.fn)
    
    def _check_last_session(self):
        #do basic parameter checks on the last session (new session)
        sess=self.sess_list[-1]
        
        message=''
        
        if sess['completed']==1:
            message=message+'Last session should be new, uncompleted session.\n'
        
        stim_ratio_sum=sess['pre']['ratio_probe']+sess['pre']['ratio_training']+sess['pre']['ratio_training_probe']
        if stim_ratio_sum != 1:
            message=message+'Stim ratios should sum to 1. Currently '+str(stim_ratio_sum)
        
        if (sess['pre']['probeMode']==0) and (sess['pre']['ratio_training']!=1):
            message=message+'Probe mode = '+str(sess['pre']['probeMode'])+' but ratio_training='+str(sess['pre']['ratio_probe'])
             
        if (sess['pre']['probeMode']==1) and (sess['pre']['ratio_training']==1):
            message=message+'Probe mode = '+str(sess['pre']['probeMode'])+' but ratio_training='+str(sess['pre']['ratio_training'])
        
        #==add parameters for backward compatibility==
        #graylevel: for both ALP and Polygon, can be in [1,8]
        if 'graylevel' not in sess['pre']:
            self.sess_list[-1]['pre']['graylevel']=1
        
        
        if message != '':
            showMessage(message)
            return False
        else:
            return True


    def _make_autolabel_all(self):
        pass

    def _make_autolabel(self):
        pattern=str(self.pattern_select.currentText())
        spots= self.sess_list[self.session_id]['patterns'][pattern]['defn']

        #==sort spot/onset pairs==
        spotstrings=[]
        for s in spots:
            onset=spots[s]['onset']
            if s.startswith('R'): #in label, drop index of random spot 'R'
                s='R'
            spotstrings.append(str(onset).zfill(4) + '_' + s)
        spotstrings.sort()
        newLabel=''
        for s in spotstrings:
            [onset, spot] = s.split('_')
            if ',' in onset: #list
                onset='#'
            else:
                onset=str(int(onset))
            newLabel=newLabel+spot+onset+'_'

        newLabel =  newLabel[:-1]
        oldLabel = pattern

        #apply label
        self.pattern_select.setItemText(self.pattern_select.currentIndex(),newLabel)
        self._pattern_renamed()


    def _finalize_spots(self):
        msgBox = QtGui.QMessageBox()

        if self.spots['finalized']:
            message='Spots already finalized!'
            msgBox.setText(message)
            msgBox.exec_()
            return

        msgBox.setStandardButtons(QtGui.QMessageBox.Cancel|QtGui.QMessageBox.Ok)
        #unfortunately default button order is unintuitive, and cannot be swapped

        msgBox.setDefaultButton(QtGui.QMessageBox.Cancel)
        message='Finalize spot definitions'
        msgBox.setText(message)
        ret = msgBox.exec_()
        if ret == QtGui.QMessageBox.Cancel:
            return
        elif ret == QtGui.QMessageBox.Ok:
            self.spots['finalized']=1
            self.spot_x.setReadOnly(True)
            self.spot_y.setReadOnly(True)

            msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
            message='Spots finalized. Save file to preserve change.'
            msgBox.setText(message)
            msgBox.exec_()

    def _set_first_sess(self):
        sess_num, ok = QtGui.QInputDialog.getText(self, 'Input', 'Set first session number:')
        self.sess_list[0]['post']['id']=str(sess_num)
        self.sess_select.item(0).setText(sess_num)

    @QtCore.pyqtSlot()
    def _sess_select_changed(self):
        #==get session index + other info==
        idx = self.sess_select.currentRow()
        self.session_id=idx

        try:
            sess=self.sess_list[self.session_id]
        except:
            print 'session list index error, probably innocuous: could be during deletion of session'
            return

        self.rig=sess['pre']['rig']

        for p in sess['patterns']:
            if 'defn' not in sess['patterns'][p]:
                sess['patterns'][p]={'defn':sess['patterns'][p].copy()}
                print self.sess_list[self.session_id]['patterns']
        
       
        #==populate session info==
        self.sess_info.clear()
        params=['date','total_trials','target_left_acc','target_right_acc']
        descriptors={'date':'date: ',
                     'total_trials': 'nTrials: ',
                     'target_left_acc': 'Target Left: ',
                     'target_right_acc': 'Target Right: ',
                     }
        for p in params:
            textstring = descriptors[p]+str(sess['post'][p])
            self.sess_info.append(textstring)

        #==get order==
        if sess['pre']['order']==0:
            side = {'target': ' (left)', 'nontarget': ' (right)'}
        elif sess['pre']['order']==1:
            side = {'target': ' (right)', 'nontarget': ' (left)'}

        for stim in side:
            self.stim_widgets[stim]['select_box'].setTitle(stim+side[stim])


        #==populate session comments==
        self.sess_comments.clear()
        textstring = sess['post']['comments']
        self.sess_comments.insertPlainText(textstring)


        #==re-populate sess option dropdown menu==
        options=sess['pre'].keys()
        options.sort()
        self.sess_option_select.clear()
        for o in options:
            self.sess_option_select.addItem(o)


        self.update_sess_plot()
        self._sess_option_select_changed() #update option value too

        #==calculate grid x_max and y_max==
        s=spot.Spot(sess['pre']['rig'])

        if sess['pre']['rig']=='ALP2':
            self.grid = self.spots['grid']

        self.gridmax=s.get_grid_max(sess['pre']['gridsize'])
        self.DMD_dim = s.Im_dim


        #===set editability of patterns===
        input_params = {}
        input_params['setReadOnly'] = [self.sess_option_value,
                                       self.spot_onset,
                                       self.spot_dur,
                                       self.spot_intensity,
                                       self.spot_grouptime,
                                       self.sequence_omit,
                                       self.sequence_replace,
                                       self.sequence_scramble,
                                       self.sequence_randt]

        input_params['setEditable'] = [self.pattern_select]

        input_params['setEnabled'] = [self.patternspot_transfer_btn,
                                      self.pattern_add_btn]
        
        for s in self.stim_types:
            input_params['setEnabled'].append(self.stim_widgets[s]['transfer_btn'])

        
        if sess['completed']==1:
            #==forbid changing options if session was completed===
            for param in input_params['setReadOnly']:
                param.setReadOnly(True)
                
            for param in input_params['setEditable']:
                param.setEditable(False)       
                
            for param in input_params['setEnabled']:
                param.setEnabled(False)       
            
        else:
            for param in input_params['setReadOnly']:
                param.setReadOnly(False)
                
            for param in input_params['setEditable']:
                param.setEditable(True)       
                
            for param in input_params['setEnabled']:
                param.setEnabled(True)

            #===allow saving of edited values by pressing return (without updating pickle yet)
            self.sess_option_value.returnPressed.connect(self._option_value_changed)
            self.pattern_select.lineEdit().returnPressed.connect(self._pattern_renamed)
            
            self.spot_onset.returnPressed.connect(self._timing_changed)
            self.spot_dur.returnPressed.connect(self._timing_changed)
            self.spot_intensity.returnPressed.connect(self._timing_changed)
            self.spot_grouptime.returnPressed.connect(self._timing_changed)            
            
            self.sequence_omit.returnPressed.connect(self._sequence_global_changed)
            self.sequence_replace.returnPressed.connect(self._sequence_global_changed)
            self.sequence_scramble.returnPressed.connect(self._sequence_global_changed)
            self.sequence_randt.returnPressed.connect(self._sequence_global_changed)

            

        if self.autolabel==1: #override pattern naming settings if autolabel mode is on
            self.pattern_select.setEditable(False)
        
        #==define 'odors' dict if not already defined, for backward compatibility
        if 'odors' not in self.sess_list[self.session_id]: 
            self.sess_list[self.session_id]['odors']={'target':[],'nontarget':[],'probe':[],'probeTraining':[]}
        
        #==populate patterns==
        patterns=sess['patterns'].keys()
        patterns.sort()
        self.pattern_select.clear()
        for p in patterns:
            self.pattern_select.addItem(p)

        #==populate stim lists==
        for s in self.stim_types:
            self.populate_stim_select(s)

        return

    def _new_session(self):
        #create new session, copying the currently selected session
        if not self.sess_list: #==first session==
            sess_num, ok = QtGui.QInputDialog.getText(self, 'Input', 'Set first session number:')
            sess_num = str(sess_num)
            sess_dict={'completed':0,'pre':{},'post':{},'patterns':{}, 'stim':{},'odors':{} }
            sess_dict['completed']=0
            sess_dict['post']['id']=sess_num

            sess_dict['pre']['debias']=0 
            sess_dict['pre']['initialtrials']=0
            sess_dict['pre']['initialport']='Left'
            sess_dict['pre']['laserdur']=500
            sess_dict['pre']['lickgraceperiod']=600
            sess_dict['pre']['order']=0
            
            sess_dict['pre']['mouse_protocol']='patternstim_2AFC'
            sess_dict['pre']['protocol_type']='test'
            sess_dict['pre']['probeMode']=0
            sess_dict['pre']['reinforcementpercentage']=1
            sess_dict['pre']['gridsize']=20
            sess_dict['pre']['graylevel']=1
            
            sess_dict['pre']['ratio_training']=1.0
            sess_dict['pre']['ratio_probe']=0.0
            sess_dict['pre']['ratio_training_probe']=0.0
            sess_dict['pre']['rig']='ALP'
            
            sess_dict['patterns']={}
            
            sess_dict['stim']['target']=[]
            sess_dict['stim']['nontarget']=[]
            sess_dict['stim']['probe']=[]
            sess_dict['stim']['probeTraining']=[]
            
            sess_dict['odors']['target']=[]
            sess_dict['odors']['nontarget']=[]
            sess_dict['odors']['probe']=[]
            sess_dict['odors']['probeTraining']=[]            
            
            new_sess = deepcopy(sess_dict)
            
            #initialize spots
            self.spots['finalized'] = 0
            self.spots['list'] = {}
            


            
        else:
            new_sess = deepcopy(self.sess_list[self.session_id])
            new_sess['completed']=0
            new_sess['post']['id']='New'


        post_vars=['date','target_left_acc','target_right_acc','total_trials','h5file',
              'left_plot','right_plot','quit-o-meter','comments']
        for v in post_vars:
            new_sess['post'][v]=''

        self.sess_list.append(new_sess)
        self.sess_select.addItem(new_sess['post']['id']) #update listwidget

        last_index=self.sess_select.count()-1
        self.sess_select.setCurrentRow(last_index) #set selection to new item

    def _new_spot(self):
        print self.spots
        if self.spots['finalized']:
            self.spots_finalized()
            return
        
        #==randomly generate new name for spot==
        spot_name='New'
        while spot_name in self.spots['list']:
            spot_name='New' + str(randint(0,100))
        self.spot_select.addItem(spot_name)
        
        print self.spots
        if self.spots['emulation']:
            #emulation mode
            filedialog = QtGui.QFileDialog(self)
            startpath = 'C:/voyeur_rig_config/'
            im_path = filedialog.getOpenFileName(self, "Select an image file.", startpath, "png (*.png)", "", QtGui.QFileDialog.DontUseNativeDialog)    
            spot=cv2.imread(str(im_path),0)
            self.spots['list'][spot_name]=spot
            
            
            if self.DMD_dim != list(spot.shape):
                err = 'Loaded pattern has shape of ' + str(list(spot.shape)) 
                err = err + ' but DMD has shape of ' + str(self.DMD_dim)
                raise ValueError(err)
        else:
            #random pattern mode: generate new spot randomly with spacing restrictions
            try:
                print self.gridmax
                if self.spots['list'].values():
                    x,y = self._rand_xy((self.gridmax[0],self.gridmax[1]),self.random_spacing,
                                  np.array(self.spots['list'].values()))
                else:
                    x,y = self._rand_xy((self.gridmax[0],self.gridmax[1]),self.random_spacing)
    
            except ValueError:
                msgBox = QtGui.QMessageBox()
                message='Max iterations reached before finding a new random spot. Try decreasing spacing (Menu Tools)'
    
                msgBox.setText(message)
                msgBox.exec_()
                return

            self.spots['list'][spot_name]=[x,y]

    def _redo_spot(self):
        if self.spots['finalized']:
            self.spots_finalized()
            return
        
        if self.spots['emulation']:
            spot_name=str(self.spot_select.currentItem().text())

            #emulation mode
            filedialog = QtGui.QFileDialog(self)
            startpath = 'C:/voyeur_rig_config/'
            im_path = filedialog.getOpenFileName(self, "Select an image file.", startpath, "png (*.png)", "", QtGui.QFileDialog.DontUseNativeDialog)    
            spot=cv2.imread(str(im_path),0)
            self.spots['list'][spot_name]=spot
            
            if self.DMD_dim != list(spot.shape):
                err = 'Loaded pattern has shape of ' + str(list(spot.shape)) 
                err = err + ' but DMD has shape of ' + str(self.DMD_dim)
                raise ValueError(err)
            
            
        else:
            msgBox = QtGui.QMessageBox()
            selected_idxes = self.spot_select.selectedIndexes()
    
            if len(selected_idxes) > 1:
                message='Error: Multiple spots selected!'
                msgBox.setText(message)
                msgBox.exec_()
                return
    
            spot_name=str(self.spot_select.currentItem().text())
    
            try:
                if self.spots['list'].values():
                    x,y = self._rand_xy((self.gridmax[0],self.gridmax[1]),self.random_spacing,
                                  np.array(self.spots['list'].values()))
                else:
                    x,y = self._rand_xy((self.gridmax[0],self.gridmax[1]),self.random_spacing)
            except ValueError:
                message='Max iterations reached before finding a new random spot. Try decreasing spacing (Menu Tools)'
                msgBox.setText(message)
                msgBox.exec_()
                return
    
            self.spots['list'][spot_name]=[x,y]
            self._spot_select_changed()


    def _patternspot_transfer(self):
        pattern=str(self.pattern_select.currentText())

        if self.patternspot_transfer_btn.text()=='Remove Spot': #remove spots
            spotNames=[]

            while self.patternspot_select.selectedIndexes(): #delete entries in QtList
                i = self.patternspot_select.selectedIndexes()[0]
                ii = i.row()
                spotNames.append(str(self.patternspot_select.item(ii).text()))
                self.patternspot_select.takeItem(ii)

            for s in spotNames:
                del self.sess_list[self.session_id]['patterns'][pattern]['defn'][s]

            self._plot_timing()
        elif self.patternspot_transfer_btn.text()=='Add Spot': #Add spots
            sel_spots=self.spot_select.selectedItems()
            new_spot={'dur':80,'onset':0}

            for s in sel_spots:
                spotName=str(s.text())

                if spotName == 'R': #deal with multiple instantiations of random spot
                    spotlist=self.sess_list[self.session_id]['patterns'][pattern]['defn'].keys()
                    r_indices=[]
                    for s in spotlist:
                        if s.startswith('R'):
                            r_indices.append(int(s[1:]))

                    if r_indices:
                        new_index=max(r_indices)+1
                    else:
                        new_index=0
                    spotName='R'+str(new_index)
                
                print spotName
                print self.sess_list[self.session_id]['patterns']
                if not (spotName in self.sess_list[self.session_id]['patterns'][pattern]['defn']):
                    self.sess_list[self.session_id]['patterns'][pattern]['defn'][spotName]=deepcopy(new_spot)
            self._pattern_select_changed()

        if self.autolabel==1:
            self._make_autolabel()

    def _add_odor(self):
        trial_type = str(self.sender().objectName())
        Odor, ok = QtGui.QInputDialog.getText(self, 'Input', 'Enter odor e.g. carvone_0.1_100: ')
        Odor = str(Odor)
        print Odor, trial_type
        
        #===check odor string===
        #odor should be in format odorname_{1}_{2}, where 1 is liq dilution, 2 is nitrogen flow out of 1000
        #e.g. methyl benzoate_0.1_100
        odor_params = Odor.split('_')
        odor_error = 0
        if len(odor_params) != 3:
            odor_error = 1
            
        try:
            float(odor_params[1])
        except:
            odor_error = 1

        try:
            int(odor_params[2])
        except:
            odor_error = 1
            
        if odor_error == 1:
            err_mess = 'odor should be xxx_0.1_100, where the last two values are liq dilution and nitrogen flow (10/100)'
            msgBox = QtGui.QMessageBox()
            msgBox.setText(err_mess)
            msgBox.exec_()
            raise ValueError('odor name error.')
        
        if self.sender().text() == 'Add odor to ptn':
            old_item=str(self.stim_widgets[trial_type]['select'].currentItem().text())
            new_item = old_item+'!'+Odor
            print new_item, old_item, Odor[0]
            self.stim_widgets[trial_type]['select'].currentItem().setText(new_item)
            self.sess_list[self.session_id]['stim'][trial_type].append(new_item)
            self.sess_list[self.session_id]['stim'][trial_type].remove(old_item)
            
            if trial_type == 'target' or trial_type == 'nontarget':
                trial_type='probeTraining'
                self.sess_list[self.session_id]['stim'][trial_type].append(new_item)
                self.sess_list[self.session_id]['stim'][trial_type].remove(old_item)
                self.sess_list[self.session_id]['stim'][trial_type].sort()
                self.populate_stim_select('probe')                    
        else:
            if Odor in self.sess_list[self.session_id]['odors'][trial_type]: #odor already exists
                return
            
            self.sess_list[self.session_id]['odors'][trial_type].append(Odor)
            self.sess_list[self.session_id]['odors'][trial_type].sort()
    
            self.populate_stim_select(trial_type)
            
            if trial_type == 'target' or trial_type == 'nontarget':
                trial_type='probeTraining'
                self.sess_list[self.session_id]['odors'][trial_type].append(Odor)
                self.sess_list[self.session_id]['odors'][trial_type].sort()
                self.populate_stim_select('probe')        
    
            print self.sess_list[self.session_id]['odors']
            

    def _stim_transfer(self,s):
        """add or remove patterns from each Stim (A,B,probe)"""

        stim_btn =  self.stim_widgets[s]['transfer_btn']

        #====remove====
        if stim_btn.text()=='Remove':
            ptnNames=[]

            while self.stim_widgets[s]['select'].selectedIndexes(): #delete entries in QtLists
                i = self.stim_widgets[s]['select'].selectedIndexes()[0]
                ii = i.row()
                ptnNames.append(str(self.stim_widgets[s]['select'].item(ii).text()))

                self.stim_widgets[s]['select'].takeItem(ii)

            for p in ptnNames:
                for stimtype in ['stim','odors']:
                    if p in self.sess_list[self.session_id][stimtype][s]:
                        self.sess_list[self.session_id][stimtype][s].remove(p)

            s='probeTraining'
            for p in ptnNames:
                for stimtype in ['stim','odors']:
                    if p in self.sess_list[self.session_id][stimtype][s]:
                        self.sess_list[self.session_id][stimtype][s].remove(p)

            self.populate_stim_select('probe')

        #====add====
        elif stim_btn.text()=='Add':
            pattern=str(self.pattern_select.currentText())
            if not (pattern in self.sess_list[self.session_id]['stim'][s]):
                self.sess_list[self.session_id]['stim'][s].append(pattern)
                self.sess_list[self.session_id]['stim'][s].sort()

                if s=='target' or s=='nontarget':
                    self.sess_list[self.session_id]['stim']['probeTraining'].append(pattern)
                    self.sess_list[self.session_id]['stim']['probeTraining'].sort()

                #==repopulate Stim QList==
                self.populate_stim_select(s)

                if s != 'probe': #update probe training trials
                    self.populate_stim_select('probe')


    def populate_stim_select(self,trial_type):
        self.stim_widgets[trial_type]['select'].clear()
        #==for probe trials, deal with probe of training trials==
        if trial_type=='probe':
            stim_list = self.sess_list[self.session_id]['odors']['probeTraining']+self.sess_list[self.session_id]['stim']['probeTraining']
            for idx, p in enumerate(stim_list):
                self.stim_widgets[trial_type]['select'].addItem(p)
                self.stim_widgets[trial_type]['select'].item(idx).setTextColor(QtGui.QColor(127,127,127))
        
        stim_list = self.sess_list[self.session_id]['odors'][trial_type]+self.sess_list[self.session_id]['stim'][trial_type]
        nOdors = len(self.sess_list[self.session_id]['odors'][trial_type])
        for idx, p in enumerate(stim_list):
            self.stim_widgets[trial_type]['select'].addItem(p)
            
            if idx < nOdors and trial_type !='probe':
                self.stim_widgets[trial_type]['select'].item(idx).setTextColor(QtGui.QColor(255,0,0))
            
        
    def _add_pattern(self):
        newPattern, ok = QtGui.QInputDialog.getText(self, 'Input', 'Enter pattern (blank for random, \'empty\' for empty):')
        sess=self.sess_list[self.session_id]
        if ok:
            if newPattern=='':
                #==copy a currently selected pattern==

                oldPattern = str(self.pattern_select.currentText())
                if oldPattern=='':
                    #==no pattern exists, make arbitrary==
                    newPattern='New'
                    newPatternDict={self.spots['list'].keys()[0]:{'onset':0,'dur':0}}
                    self.sess_list[self.session_id]['patterns'][newPattern]={'defn': newPatternDict}
                else:
                    newPattern = oldPattern + 'copy'
                    self.sess_list[self.session_id]['patterns'][newPattern]={'defn':deepcopy(self.sess_list[self.session_id]['patterns'][oldPattern])}

                    someSpot=self.sess_list[self.session_id]['patterns'][newPattern]['defn'].keys()[0]

                    oldOnset=self.sess_list[self.session_id]['patterns'][newPattern]['defn'][someSpot]['onset']
                    self.sess_list[self.session_id]['patterns'][newPattern]['defn'][someSpot]['onset']=oldOnset + randint(1,100)

                self.pattern_select.addItem(newPattern)
                newest=self.pattern_select.count()-1
                self.pattern_select.setCurrentIndex(newest)
                self._make_autolabel()
            elif newPattern=='empty':
                newPattern=str(newPattern)
                self.pattern_select.addItem(newPattern)
                self.sess_list[self.session_id]['patterns'][newPattern]= {'defn':{'empty':{'onset':0, 'dur':0}}}
                newest=self.pattern_select.count()-1
                self.pattern_select.setCurrentIndex(newest)
            else:
                #===try to parse input string==
                newPattern=str(newPattern)
                spots=newPattern.split('_')
                self.sess_list[self.session_id]['patterns'][newPattern]={'defn':{}}
                for s in spots:
                    spotLetter=s[0]
                    spotOnset=s[1:]
                    
                    if spotOnset == '':
                        raise ValueError('Enter spot onset e.g. \'A40')
                    
                    
                    if spotOnset=='#':
                        spotOnset=0
                    else:
                        spotOnset=int(spotOnset)

                    self.sess_list[self.session_id]['patterns'][newPattern]['defn'][spotLetter]={}
                    self.sess_list[self.session_id]['patterns'][newPattern]['defn'][spotLetter]['onset']=spotOnset
                    self.sess_list[self.session_id]['patterns'][newPattern]['defn'][spotLetter]['dur']=80
                    self.sess_list[self.session_id]['patterns'][newPattern]['defn'][spotLetter]['intensity']=255

                self.pattern_select.addItem(newPattern)
                newest=self.pattern_select.count()-1
                self.pattern_select.setCurrentIndex(newest)
                self._make_autolabel()

        else:
            return #no input
        pass


    def _sess_option_select_changed(self):
        try:
            #===if menu has just being cleared (this function is automatically called), this raises an error===
            selected_option=str(self.sess_option_select.currentText())
            sess_idx = self.sess_select.currentRow()
            val = self.sess_list[sess_idx]['pre'][selected_option]
            self.sess_option_value.setText(str(val))
        except:
            pass
            #print "optionlist cleared"


    def _spot_select_changed(self):
        #==deal with multiple selections==
        selected_items = self.spot_select.selectedItems()
        if not selected_items:
            return
        spotNames=[]
        for i in selected_items:
            spotName= str(i.text())
            spotNames.append(spotName)

        spot=self.spots['list'][spotName]
        
        if self.spots['emulation']: #odor emulation mode, hand-drawn ROIs
            self._plot_spots(spotNames)
            
        else: #random pattern mode
            #==update x,y. if multiple spots selected, use most recently selected==
            if spotName == 'R':
                self.spot_x.setText('')
                self.spot_y.setText('')
            else:
                self.spot_x.setText(str(spot[0]))
                self.spot_y.setText(str(spot[1]))
    
            self._plot_grid(spotNames)

    def _pattern_select_changed(self):
        sess=self.sess_list[self.session_id]
        pattern=str(self.pattern_select.currentText())
        if pattern == '': #no pattern selected
            return

        spotNames=sess['patterns'][pattern]['defn'].keys()
        spotNames.sort()

        self.patternspot_select.clear()
        for s in spotNames:
            self.patternspot_select.addItem(s)


        self.patternspot_select.setCurrentRow(0)

        self._patternspot_select_changed()
        self._plot_timing()
        
        
        params = {'omit':0,'replace':0,'scramble':0,'randt':0}
        for p in params:
            if p in sess['patterns'][pattern]:
                params[p] = sess['patterns'][pattern][p]
        
        self.sequence_omit.setText(str(params['omit']))
        self.sequence_replace.setText(str(params['replace']))
        self.sequence_scramble.setText(str(params['scramble']))
        self.sequence_randt.setText(str(params['randt']))


    def _option_value_changed(self):
        option_selected=str(self.sess_option_select.currentText())
        option_val=str(self.sess_option_value.text())

        option_val=self._format_option_dtype(option_val,option_selected)
        self.sess_list[self.session_id]['pre'][option_selected]=option_val
        
        if option_selected == 'gridsize':
            self._sess_select_changed()
        
    def _stim_select_changed(self,s):
        selected_items = self.stim_widgets[s]['select'].selectedItems()
        focus_item=str(self.stim_widgets[s]['select'].currentItem().text())
        
        if selected_items:
            self.stim_widgets[s]['transfer_btn'].setText('Remove')
            message = s + ':' +focus_item


            #==deal with probe training types (differently colored)==
            if s=='probe' and not self.stim_widgets[s]['select'].currentItem().textColor().name() == '#000000':
                self.stim_widgets[s]['transfer_btn'].setEnabled(False)
                message = 'probe training:' +self.stim_widgets[s]['select'].currentItem().text()
            else:
                self.stim_widgets[s]['transfer_btn'].setEnabled(True)
                
            if (focus_item in self.sess_list[self.session_id]['patterns']) and ('!' not in focus_item):
                self.stim_widgets[s]['add_odor'].setEnabled(True)
                self.stim_widgets[s]['add_odor'].setText('Add odor to ptn')
            else:
                self.stim_widgets[s]['add_odor'].setEnabled(False)


        else:
            self.stim_widgets[s]['add_odor'].setEnabled(True)
            self.stim_widgets[s]['transfer_btn'].setEnabled(True)
            self.stim_widgets[s]['transfer_btn'].setText('Add')
            self.stim_widgets[s]['add_odor'].setText('Add odor')
            message=''

        self.statusbar.showMessage(message)



    def _xy_changed(self):
        msgBox = QtGui.QMessageBox()

        #===retrieve values from all xy input boxes===
        try:
            retrievedValues={'x': int(self.spot_x.text()),'y':int(self.spot_y.text())} #use correct key later
        except ValueError:
            message = 'Spot coordinates must be integer!'
            msgBox.setText(message)
            msgBox.exec_()
            return

        #===check if spots are within grid===
        if self.rig=='ALP2':
            xbounds = self.grid[0]
            ybounds = self.grid[1]
        else:
            xbounds=[0,self.gridmax[0]]
            ybounds=[0,self.gridmax[1]]
        x=retrievedValues['x']
        y=retrievedValues['y']

        if xbounds[0] <= x <= xbounds[1] and ybounds[0] <= y <= ybounds[1]:
            pass
        else:
            message = 'Spots are not within x:' + str(xbounds)+\
                      ' and y: ' + str(ybounds)
            msgBox.setText(message)
            msgBox.exec_()
            return

        sel_spots=self.spot_select.selectedItems()
        if len(sel_spots)>1:
            message='Sorry, you have more than one spot selected. Cannot edit.'
            msgBox.setText(message)
            msgBox.exec_()
            return
        else:
            spotName = str(sel_spots[0].text())


        self.spots['list'][spotName]=[retrievedValues['x'],retrievedValues['y']]

        self._spot_select_changed()
    
    
    def _sequence_global_changed(self):
        #parameters applying to entire sequence
        retrievedValues={'omit': int(self.sequence_omit.text()),
                         'replace': int(self.sequence_replace.text()),
                         'scramble': int(self.sequence_scramble.text()),
                         'randt': int(self.sequence_randt.text())}
        
        pattern=str(self.pattern_select.currentText())
        for param, newValue in retrievedValues.items():
            self.sess_list[self.session_id]['patterns'][pattern][param]=newValue
            print param,newValue

    def _timing_changed(self):
        def IntegerError():
            msgBox = QtGui.QMessageBox()
            message = 'Timing values must be integer (milliseconds)!'
            msgBox.setText(message)
            msgBox.exec_()
            
        def IntensityError():
            msgBox = QtGui.QMessageBox()
            message = 'Intensity must be an integer in [0,255]'
            msgBox.setText(message)
            msgBox.exec_()     
            

        msgBox = QtGui.QMessageBox()

        timing={}
        retrievedValues={'onset': str(self.spot_onset.text()),
                         'dur': str(self.spot_dur.text()),
                         'intensity': str(self.spot_intensity.text()),
                         'grouptime': str(self.spot_grouptime.text())}
        
        textBoxes={'onset':self.spot_onset,
                   'dur':self.spot_dur,
                   'intensity':self.spot_intensity,
                   'grouptime': self.spot_grouptime}
        
        #===format timing values===
        timingisRandom=0 #number of text values separately specified as list 
        for param in ['onset','dur']:
            text=retrievedValues[param]

            if ',' in text: #list was supplied, this becomes a random timing spot
                timingisRandom=timingisRandom+1
                reader=LineParser()
                try:
                    timing[param]=reader.feed(text)
                except ValueError:
                    IntegerError()
                    return
            else:
                try:
                    timing[param]=int(text)
                except ValueError:
                    IntegerError()
                    return
        
        if timingisRandom==1: #one timing parameter is a list but not the other: force non-list value into list
            for param in ['onset','dur']:
                text=retrievedValues[param]
                if not (',' in text):
                    timing[param]=[int(text),int(text)]
                    textBoxes[param].setText(str(timing[param]))
                    
        #===format intensity values===            
        param = 'intensity'
        text=retrievedValues[param]

        if ',' in text: #list was supplied, this becomes a random intensity spot
            reader=LineParser()
            try:
                timing[param]=reader.feed(text)
            except ValueError:
                IntegerError()
                return
            
            for intensity in timing[param]:
                if not (0 <= intensity <= 255): 
                    IntensityError()
                    return
        else:
            try:
                timing[param]=int(text)
            except ValueError:
                IntegerError()
                return
            
            intensity = timing[param]
            if not (0 <= intensity <= 255): 
                IntensityError()
                return

        textBoxes[param].setText(str(timing[param]))

        #===format grouping values===            
        param = 'grouptime'
        text=retrievedValues[param]
        if ',' in text:
            reader=LineParser()
            try:
                timing[param]=reader.feed(text)
            except ValueError:
                IntegerError()
                return
        else:
            timing[param]=''

        textBoxes[param].setText(str(timing[param]))
        
        pattern=str(self.pattern_select.currentText())
        sel_spots=self.patternspot_select.selectedItems()
        if len(sel_spots)>1:
            message='Sorry, you have more than one spot selected. Cannot edit.'
            msgBox.setText(message)
            msgBox.exec_()
            return
        else:
            spotName = str(sel_spots[0].text())

        '''
        #===check if timing is within laserduration===
        bounds=[0,self.sess_list[self.session_id]['pre']['laserdur']]
        onset=retrievedValues['onset']
        offset=retrievedValues['onset']+retrievedValues['dur']

        if bounds[0] <= onset <= bounds [1] and bounds[0] <= offset <= bounds [1]:
            pass
        else:
            message = 'Spot occurrence exceeds bounds (laserdur) of ' + str(bounds[0])+\
                      ' to ' + str(bounds[1]) + ' ms.'
            msgBox.setText(message)
            msgBox.exec_()
            return
        '''
            

        
        for param, newValue in timing.items():
            self.sess_list[self.session_id]['patterns'][pattern]['defn'][spotName][param]=newValue
            print param,newValue

        if self.autolabel==1:
            self._make_autolabel() #generate autolabel


        self._plot_timing()



    def _pattern_renamed(self):
        newName = str(self.pattern_select.currentText())
        oldName = self.currentPattern
        
        if newName == oldName:
            return
        else:
            if newName in self.sess_list[self.session_id]['patterns']:
                counter = 2
                newName = newName + '-'+str(counter).zfill(2)
                while newName in self.sess_list[self.session_id]['patterns']:
                    counter = counter + 1
                    
                    suffix = str(counter).zfill(2)
                    newName_lst = list(newName)
                    newName_lst[-2]=suffix[0]
                    newName_lst[-1]=suffix[1]
                    newName = "".join(newName_lst) 
                    
            self.sess_list[self.session_id]['patterns'][newName] = self.sess_list[self.session_id]['patterns'].pop(oldName)
            self.currentPattern=newName
            self.pattern_select.setItemText(self.pattern_select.currentIndex(),newName)
            

    def _patternspot_select_changed(self):
        sess=self.sess_list[self.session_id]
        pattern=str(self.pattern_select.currentText())

        self.currentPattern = pattern #stores the current pattern, so that can assign when name is changed

        selected_spotNames=[]
        #==deal with multiple selections==
        selected_items = self.patternspot_select.selectedItems()
        if selected_items:
            self.patternspot_transfer_btn.setText('Remove Spot')
        else:
            self.patternspot_transfer_btn.setText('Add Spot')
            return

        for i in selected_items:
            spotName= str(i.text())
            selected_spotNames.append(spotName)

        selected_spot = sess['patterns'][pattern]['defn'][selected_spotNames[-1]]
        onset = selected_spot['onset'] #take spotName of final loop iteration (dirty)
        dur = selected_spot['dur']

        if 'intensity' in selected_spot: #backward compatibility
            pwr=selected_spot['intensity']
        else:
            pwr=255
            selected_spot['intensity'] = pwr 
        
        if 'grouptime' in selected_spot:
            grouptime = selected_spot['grouptime']
        else:
            grouptime = ''                
        
        self.spot_onset.setText(str(onset))
        self.spot_dur.setText(str(dur))
        self.spot_intensity.setText(str(pwr))
        self.spot_grouptime.setText(str(grouptime))    

        '''
        #OPTIONAL FUNCTIONALITY: ADDS SLOWDOWN BECAUSE OF finditems()
        #mirror spot selection in defined list
        self.spot_select.clearSelection()
        for s in selected_spotNames:
            spot_item=self.spot_select.findItems(s,QtCore.Qt.MatchFixedString)

            spot_item=spot_item[0]
            spot_item.setSelected(True)
        self._spot_select_changed()
        '''

    def _plot_spots(self, spots_on=[]):
        self.ax_spot_disp.clear()
        self.ax_spot_disp.axis('off')
        
        summed_im = np.zeros(self.DMD_dim)
        for s in spots_on:
            summed_im = summed_im + self.spots['list'][s]
        np.max(summed_im>0)*255

        self.ax_spot_disp.imshow(summed_im)
        self.spot_disp_canvas.draw()
                                 
    def _plot_grid(self,spots_on=[]):
        if self.rig=='ALP2':
            self._plot_grid_offset(spots_on)
            return

        self.ax_spot_disp.clear()
        self.ax_spot_disp.axis('off')
        nRows=self.gridmax[0]+1 #0 indexing
        nCols=self.gridmax[1]+1


        x_coord=range(nRows)
        x_coord.reverse() #x coordinate is flipped because the plot starts from bottom to top

        spot_size=0.1
        spacing = 0.1 * spot_size

        x_start=0.1
        y_start=0.1
        x=x_start
        y=y_start

        spot_list={}
        for i in range(nRows):
            x=x_start
            for j in range(nCols):
                handle = self.ax_spot_disp.add_patch(
                    patches.Rectangle(
                        (x, y),
                        spot_size,
                        spot_size,
                        fill=None
                    )
                )

                coords=str([x_coord[i],j])
                spot_list[coords]=handle
                x=x+spacing+spot_size



            y=y+spacing+spot_size


        if 'R' in spots_on:
            if self.spots['list']['R']==['random']:
                #turn entire grid green, then turn the non-random spots white.
                spots_off = self.spots['list'].keys()
    
                for s in spot_list:
                    spot_list[s].set_facecolor([0,0.4,0])
                    spot_list[s].set_fill(True)
    
                spots_on=filter(lambda a: a != 'R', spots_on)
                spots_off=filter(lambda a: a != 'R', spots_off)
    
                for s in spots_off:
                    spot_list_key=str(self.spots['list'][s])
                    spot_list[spot_list_key].set_facecolor([1,1,1])
            elif isinstance(self.spots['list']['R'][0],tuple):

                #nested list of spots. ephys, where random spots are explicit
                for s in self.spots['list']['R']:
                    spot_list_key=str(list(s))
                    spot_list[spot_list_key].set_facecolor([1,0.65,0])
                    spot_list[spot_list_key].set_fill(True)
                
                spots_on=filter(lambda a: a != 'R', spots_on)
                
                    

        #==turn on spots==
        for s in spots_on:

            spot_list_key=str(self.spots['list'][s])
            spot_list[spot_list_key].set_facecolor([1,0,0])
            spot_list[spot_list_key].set_fill(True)

            #==label==
            box=spot_list[spot_list_key].get_bbox()
            xpos=(box.x0+box.x1)/2
            ypos=(box.y0+box.y1)/2

            self.ax_spot_disp.annotate(s, (xpos, ypos), color='black', weight='bold',
                                    ha='center', va='center',fontsize=20)




        #==reset axis limits==
        self.ax_spot_disp.set_xlim([x_start-spacing,x+spacing])
        self.ax_spot_disp.set_ylim([y_start-spacing,y+spacing])

        self.spot_disp_canvas.draw()

    def _plot_grid_offset(self,spots_on):
        if self.rig != 'ALP2':
            raise ValueError('Inappropriate plotting for rig type '+str(self.rig))

        self.ax_spot_disp.clear()
        self.ax_spot_disp.axis('off')
        x_coord=range(self.grid[0][0],self.grid[0][1]+1)
        x_coord.reverse() #x coordinate is flipped because the plot starts from bottom to top

        y_coord=range(self.grid[1][0],self.grid[1][1]+1)


        spot_size=0.1
        spacing = 0.1 * spot_size

        x_start=0.1
        y_start=0.1
        x=x_start
        y=y_start

        spot_list={}
        for xlabel in x_coord:
            x=x_start
            for ylabel in y_coord:
                handle = self.ax_spot_disp.add_patch(
                    patches.Rectangle(
                        (x, y),
                        spot_size,
                        spot_size,
                        fill=None
                    )
                )

                coords=str([xlabel,ylabel])
                spot_list[coords]=handle
                x=x+spacing+spot_size



            y=y+spacing+spot_size


        if 'R' in spots_on:
            if self.spots['list']['R']==['random']:
                #turn entire grid green, then turn the non-random spots white.
                spots_off = self.spots['list'].keys()

                for s in spot_list:
                    spot_list[s].set_facecolor([0,0.4,0])
                    spot_list[s].set_fill(True)

                spots_on=filter(lambda a: a != 'R', spots_on)
                spots_off=filter(lambda a: a != 'R', spots_off)

                for s in spots_off:
                    spot_list_key=str(self.spots['list'][s])
                    spot_list[spot_list_key].set_facecolor([1,1,1])
            elif isinstance(self.spots['list']['R'][0],tuple):

                #nested list of spots. ephys, where random spots are explicit
                for s in self.spots['list']['R']:
                    spot_list_key=str(list(s))
                    spot_list[spot_list_key].set_facecolor([1,0.65,0])
                    spot_list[spot_list_key].set_fill(True)

                spots_on=filter(lambda a: a != 'R', spots_on)



        #==turn on spots==
        for s in spots_on:

            spot_list_key=str(self.spots['list'][s])
            spot_list[spot_list_key].set_facecolor([1,0,0])
            spot_list[spot_list_key].set_fill(True)

            #==label==
            box=spot_list[spot_list_key].get_bbox()
            xpos=(box.x0+box.x1)/2
            ypos=(box.y0+box.y1)/2

            self.ax_spot_disp.annotate(s, (xpos, ypos), color='black', weight='bold',
                                    ha='center', va='center',fontsize=20)




        #==reset axis limits==
        self.ax_spot_disp.set_xlim([x_start-spacing,x+spacing])
        self.ax_spot_disp.set_ylim([y_start-spacing,y+spacing])

        self.spot_disp_canvas.draw()

    def _plot_timing(self):
        self.ax_timing_disp.clear()

        sess=self.sess_list[self.session_id]
        pattern=str(self.pattern_select.currentText())
        spots=sess['patterns'][pattern]['defn']

        x_size=10
        y_size=1
        x_pos=0
        y_pos=0


        spotNames=spots.keys()
        spotNames.sort(reverse=True) #python plots from bottom to up
        for s in spotNames:
            x_pos=spots[s]['onset']
            x_size=spots[s]['dur']
            y_pos=y_pos+y_size

            if isinstance(spots[s]['onset'],list): #random onset
                lower=spots[s]['onset'][0]
                upper=spots[s]['onset'][1]
                
                x_size=(x_size[0]+x_size[1])/2 #TODO: ALSO MAKE ERROR BARS FOR VARAIABLE DURATIONS
                
                x_center = (lower+upper+x_size)/2.0
                x_pos= x_center - (x_size/2.0)
                y_center=(y_pos+y_size)/2.0
                y_center=(y_pos+y_pos+1)/2.0

                self.ax_timing_disp.errorbar(x_center, y_center, xerr=x_center-lower,
                                             fmt='.')

            r = self.ax_timing_disp.add_patch(
                                patches.Rectangle(
                                    (x_pos, y_pos),
                                    x_size,
                                    y_size,
                                    facecolor='Grey',
                                    edgecolor='Black',
                                    fill=True,
                                    zorder=2))

            #==add labels==
            label_xpos=x_pos+x_size/2.0
            label_ypos=y_pos+y_size/2.0
            self.ax_timing_disp.annotate(s, (label_xpos, label_ypos), color='black', weight='bold',
                                    ha='center', va='center',fontsize=20)

        self.ax_timing_disp.autoscale()
        self.ax_timing_disp.set_xlim([0,500])

        #==add x-axis==
        xmin, xmax = self.ax_timing_disp.get_xaxis().get_view_interval()
        ymin, ymax = self.ax_timing_disp.get_yaxis().get_view_interval()
        self.ax_timing_disp.add_artist(Line2D((xmin, xmax), (ymin, ymin), color='black', linewidth=2))

        self.timing_disp_canvas.draw()

    def update_sess_plot(self):
        padding = (2000, 2000)  #TODO: make this changable - this is the number of ms before/afterr trial to extract for stream.

        self.ax_sess.clear()
        sess=self.sess_list[self.session_id]

        if sess['completed']==0:
            self.canvas.draw()
            return
        else:
            to_plot=['left_plot','right_plot','quit-o-meter']
            xvalues=np.arange(len(sess['post'][to_plot[0]]))
            markers=['bo-','ro-','g-']
            for plt,marker in zip(to_plot,markers):
                self.ax_sess.plot(xvalues,sess['post'][plt],marker,label=plt)
            self.ax_sess.legend(loc='upper left',prop={'size':8})
            self.ax_sess.relim()
            self.canvas.draw()



    @QtCore.pyqtSlot(int)
    def showh5(self, sess_idx):
        h5file=self.sess_list[sess_idx]['post']['h5file']
        message=h5file
        msgBox = QtGui.QMessageBox()
        msgBox.setText(message)
        msgBox.exec_()

    @QtCore.pyqtSlot(str)
    def rename_spot(self,newName):
        if self.spots['finalized']:
            self.spots_finalized()
            return
        oldName = str(self.spot_select.currentItem().text())
        newName = str(newName)
        self.spots['list'][newName] = self.spots['list'].pop(oldName)
        self.spot_select.currentItem().setText(newName)


    def delete_session(self):
        if self.sess_list[self.session_id]['completed']==1:
            msgBox = QtGui.QMessageBox()
            msgBox.setStandardButtons(QtGui.QMessageBox.Cancel|QtGui.QMessageBox.Ok)
            msgBox.setDefaultButton(QtGui.QMessageBox.Cancel)
            message='Really delete selected session?'
            msgBox.setText(message)
            ret = msgBox.exec_()
            if ret == QtGui.QMessageBox.Cancel:
                return
        #===delete sess entries in data (don't pickle yet)===
        sess_toremove=[]
        idxes = self.sess_select.selectedIndexes()

        for i in idxes:
            ii = i.row()
            sess_toremove.append(ii)
        sess_toremove.sort(reverse=True) #if you remove from the front, indices change

        for s in sess_toremove:
            del self.sess_list[s]
            self.sess_select.takeItem(s)
        
        self._sess_select_changed()


    def delete_spot(self):
        if self.spots['finalized']:
            self.spots_finalized()
            return

        spotNames=[]
        while self.spot_select.selectedIndexes(): #delete entries in QtList
            i = self.spot_select.selectedIndexes()[0]
            ii = i.row()
            spotNames.append(str(self.spot_select.item(ii).text()))
            self.spot_select.takeItem(ii)


        for s in spotNames:
            del self.spots['list'][s]

        #msgBox = QtGui.QMessageBox()
        #msgBox.setText(str(spotNames))
        #msgBox.exec_()

    def delete_pattern(self): #delete pattern from list of patterns
        if self.sess_list[self.session_id]['completed']==1:
            message='Cannot edit completed session.'
            msgBox = QtGui.QMessageBox()
            msgBox.setText(str(message))
            msgBox.exec_()
            return
        elif self.sess_list[self.session_id]['completed']==0:
            sel=self.pattern_select.currentIndex()
            pattern=str(self.pattern_select.currentText())
            self.pattern_select.removeItem(sel)

            del self.sess_list[self.session_id]['patterns'][pattern]

    def delete_stim(self): #delete pattern from A / B / probe list
        pass

    def RNG_spot(self):
        if self.spots['emulation']:
            print ('Session is in emulation mode. Random spot only for grid mode')
            return
        spot_name='R'
        self.spots['list'][spot_name]=['random']
        self.spot_select.addItem(spot_name)

    def empty_spot(self):
        spot_name='empty'
        if self.spots['emulation']:
            self.spots['list'][spot_name]=np.zeros(self.DMD_dim).astype('uint8')
        else: #grid mode
            self.spots['list'][spot_name]=['empty']
        
        self.spot_select.addItem(spot_name)


    def spots_finalized(self):
        message='Sorry, spots have been finalized. Edit pickle file to undo.'
        msgBox = QtGui.QMessageBox()
        msgBox.setText(str(message))
        msgBox.exec_()




class RNG_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("RNG spot parameters")
        self.gridLayout_2 = QtGui.QGridLayout(Dialog)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.gridLayout = QtGui.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")

        self.label = QtGui.QLabel(Dialog)
        self.label_2 = QtGui.QLabel(Dialog)
        self.label_3 = QtGui.QLabel(Dialog)
        self.label_4 = QtGui.QLabel(Dialog)

        self.label.setText('duration lower bounds (ms)')
        self.label_2.setText('duration upper bounds')
        self.label_3.setText('onset lower bounds (ms)')
        self.label_4.setText('onset upper bounds')

        self.dur_lower = QtGui.QLineEdit(Dialog)
        self.dur_upper = QtGui.QLineEdit(Dialog)
        self.onset_lower = QtGui.QLineEdit(Dialog)
        self.onset_upper = QtGui.QLineEdit(Dialog)

        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        self.gridLayout.addWidget(self.dur_lower, 0, 1, 1, 1)

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)
        self.gridLayout.addWidget(self.dur_upper, 1, 1, 1, 1)

        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)
        self.gridLayout.addWidget(self.onset_lower, 2, 1, 1, 1)

        self.gridLayout.addWidget(self.label_4, 3, 0, 1, 1)
        self.gridLayout.addWidget(self.onset_upper, 3, 1, 1, 1)

        self.gridLayout_2.addLayout(self.gridLayout, 0, 0, 1, 1)
        self.buttonBox = QtGui.QDialogButtonBox(Dialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.gridLayout_2.addWidget(self.buttonBox, 1, 0, 1, 1)

        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("accepted()"), Dialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)



class SessListWidget(QtGui.QListWidget):

    showh5Sig = QtCore.pyqtSignal(int)
    deleteSessionSig = QtCore.pyqtSignal()

    def __init__(self):
        super(SessListWidget, self).__init__()
        self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)


    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            super(SessListWidget, self).mousePressEvent(event)
        elif event.button() == QtCore.Qt.RightButton:
            popMenu = QtGui.QMenu()
            viewh5fnAction = QtGui.QAction('View filename', self)
            viewh5fnAction.setStatusTip("Access h5 file name")
            viewh5fnAction.triggered.connect(self._showh5)
            popMenu.addAction(viewh5fnAction)

            #===right click action: Delete session===
            deleteSessAction = QtGui.QAction('Delete session', self)
            deleteSessAction.triggered.connect(self._delete_session)
            popMenu.addAction(deleteSessAction)


            popMenu.exec_(event.globalPos())

    def _showh5(self):
        idx = self.selectedIndexes()[0].row()
        self.showh5Sig.emit(idx)

    def _delete_session(self):
        self.deleteSessionSig.emit()



class SessInfoWidget(QtGui.QTextEdit):
    def __init__(self):
        super(SessInfoWidget, self).__init__()
        self.setReadOnly(True)
        pal = QtGui.QPalette()
        bgc = QtGui.QColor(200, 200, 200)
        pal.setColor(QtGui.QPalette.Base, bgc)
        self.setPalette(pal)

class SessCommentsWidget(QtGui.QTextEdit):
    def __init__(self):
        super(SessCommentsWidget, self).__init__()
        self.setReadOnly(False)

class SessOptionSelectWidget(QtGui.QComboBox):
    def __init__(self):
        super(SessOptionSelectWidget, self).__init__()

        '''
        sess_options=['debias',
                      'initialtrials',
                      'initialport',
                      'laserdur',
                      'order',
                      'mouse_protocol',
                      'probeMode',
                      'reinforcementpercentage']
        for o in sess_options:
            self.addItem(o)
        '''

class SessOptionValueWidget(QtGui.QLineEdit):
    def __init__(self):
        super(SessOptionValueWidget, self).__init__()


def showMessage(message):
    msgBox = QtGui.QMessageBox()
    msgBox.setText(message)
    msgBox.exec_()


class SpotListWidget(QtGui.QListWidget):
    renameSpotSig = QtCore.pyqtSignal(str)
    deleteSpotSig = QtCore.pyqtSignal()
    RNGSpotSig = QtCore.pyqtSignal()
    emptySpotSig = QtCore.pyqtSignal()

    def __init__(self):
        super(SpotListWidget, self).__init__()
        self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            super(SpotListWidget, self).mousePressEvent(event)
        elif event.button() == QtCore.Qt.RightButton:
            popMenu = QtGui.QMenu()

            #===right click action: Rename spot===
            renamespotAction = QtGui.QAction('Rename spot', self)
            renamespotAction.triggered.connect(self._rename_spot)
            popMenu.addAction(renamespotAction)

            #===right click action: Delete spot===
            deletespotAction = QtGui.QAction('Delete spot', self)
            deletespotAction.triggered.connect(self._delete_spot)
            popMenu.addAction(deletespotAction)

            #===right click action: define a 'random' spot (trial to trial random)===
            RCAction = QtGui.QAction('New RNG spot', self)
            RCAction.triggered.connect(self._RNG_spot)
            popMenu.addAction(RCAction)

            #===right click action: define a 'empty' spot (no stimulation, but laser comes on)===
            RCAction = QtGui.QAction('New empty spot', self)
            RCAction.triggered.connect(self._empty_spot)
            popMenu.addAction(RCAction)            
            

            popMenu.exec_(event.globalPos())

    def _rename_spot(self):
        msgBox = QtGui.QMessageBox()
        selected_idxes = self.selectedIndexes()

        if len(selected_idxes) > 1:
            message='Error: Multiple spots selected!'
            msgBox.setText(message)
            msgBox.exec_()
            return


        newName, ok = QtGui.QInputDialog.getText(self, 'Input', 'Enter spot name:')
        if ok:
            self.renameSpotSig.emit(newName)
        else:
            return #no input

    def _delete_spot(self):
        self.deleteSpotSig.emit()

    def _RNG_spot(self):
        self.RNGSpotSig.emit()

    def _empty_spot(self):
        self.emptySpotSig.emit()
        

class PatternspotListWidget(QtGui.QListWidget):

    def __init__(self):
        super(PatternspotListWidget, self).__init__()
        self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            super(PatternspotListWidget, self).mousePressEvent(event)
        elif event.button() == QtCore.Qt.RightButton:
            popMenu = QtGui.QMenu()

            #===right click action: Delete spot===
            deletespotAction = QtGui.QAction('Delete spot', self)
            deletespotAction.triggered.connect(self._delete_spot)
            popMenu.addAction(deletespotAction)
            popMenu.exec_(event.globalPos())



class PatternSelectWidget(QtGui.QComboBox):
    deletePatternSig = QtCore.pyqtSignal()
    def __init__(self):
        super(PatternSelectWidget, self).__init__()
        self.setInsertPolicy(QtGui.QComboBox.InsertAtCurrent)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            super(PatternSelectWidget, self).mousePressEvent(event)
        elif event.button() == QtCore.Qt.RightButton:
            popMenu = QtGui.QMenu()

            #===right click action: Delete pattern===
            deletePatternAction = QtGui.QAction('Delete pattern', self)
            deletePatternAction.triggered.connect(self._delete_pattern)
            popMenu.addAction(deletePatternAction)

            popMenu.exec_(event.globalPos())
    def _delete_pattern(self):
        self.deletePatternSig.emit()


class StimListWidget(QtGui.QListWidget):
    deleteStimSig = QtCore.pyqtSignal(str)

    def __init__(self,stimtype):
        super(StimListWidget, self).__init__()
        self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.stimtype = stimtype #'target','nontarget','probe'
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            super(StimListWidget, self).mousePressEvent(event)
        elif event.button() == QtCore.Qt.RightButton:
            popMenu = QtGui.QMenu()

            #===right click action: Remove pattern(s)===
            removePatternAction = QtGui.QAction('Remove pattern', self)
            removePatternAction.triggered.connect(self._remove_pattern)
            popMenu.addAction(removePatternAction)
            popMenu.exec_(event.globalPos())





def main(config_path=''):
    import sys
    app = QtGui.QApplication(sys.argv)
    w = CalibrationViewer()
    w.show()
    w._openAction_triggered()
    sys.exit(app.exec_())


if __name__ == "__main__":
    LOGGING_LEVEL = logging.DEBUG
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(LOGGING_LEVEL)
    main()
