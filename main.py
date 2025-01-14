#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Author: i2cy(i2cy@outlook.com)
# Project: sources
# Filename: main
# Created on: 2021/11/19


import sys
import os
import pyqtgraph as pg
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, \
    QSizePolicy, QListWidgetItem, QMessageBox
from PyQt5.QtGui import QIcon, QImage, QPixmap, QKeyEvent, QMouseEvent, QPainterPath
from PyQt5.QtCore import Qt
from pucleus_ui import Ui_MainWindow
from modules.mca import MCA, Pulses
from modules.utils import ColorManager, get_R_square, ModLogger, Mod_PlotWidget, ModTargetItem
import modules.smooth as smooth
from modules.energy_axis import linear_regression
from modules.threads import PulseGenThread, UpdatePulseInfoThread
from modules.find_peek import SimpleCompare, Peek, Derivative
from modules.libraries import Library, Nucleo


class MCA_MainUI(QMainWindow, Ui_MainWindow, QApplication):

    def __init__(self, logger=None):
        if logger is None:
            logger = ModLogger()

        assert isinstance(logger, ModLogger)

        # init
        QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        logger.bind_QLabel(self)

        self.log_header = "[MainWindow]"
        self.logger = logger
        self.thread_flags = {}

        self.tabWidget_top.setTabVisible(1, False)
        self.tabWidget_top.setTabVisible(2, False)

        # qt connection init
        self.action_exportLog.triggered.connect(self.on_action_exportLog)
        self.action_openFile.triggered.connect(self.on_open_file)
        self.action_restore_file.triggered.connect(self.static_restore_current_file)
        self.action_smooth.triggered.connect(self.on_tool_smooth_clicked)
        self.action_findPeek.triggered.connect(self.on_tool_findPeek_clicked)
        self.action_resetFrame.triggered.connect(self.static_reset_plot_view)
        self.action_zoomIn.triggered.connect(self.on_zoom_in)
        self.action_zoomOut.triggered.connect(self.on_zoom_out)
        self.action_export_chn.triggered.connect(self.on_save_file)
        self.action_showNuclide.toggled.connect(self.on_action_showNucleo_clicked)

        self.toolButton_openFile.clicked.connect(self.on_open_file)
        self.toolButton_save.clicked.connect(self.on_save_file)
        self.toolButton_resetFrame.clicked.connect(self.static_reset_plot_view)
        self.toolButton_zoomIn.clicked.connect(self.on_zoom_in)
        self.toolButton_zoomOut.clicked.connect(self.on_zoom_out)
        self.toolButton_select.clicked.connect(self.on_tool_curse_clicked)
        self.toolButton_findPeek.clicked.connect(self.on_tool_findPeek_clicked)
        self.toolButton_smooth.clicked.connect(self.on_tool_smooth_clicked)
        self.toolButton_section.clicked.connect(self.on_tool_section_clicked)
        self.toolButton_genPulse.clicked.connect(self.on_tool_genPulse_button_clicked)

        self.toolButton_energyX_select.clicked.connect(self.on_energyX_button_select_clicked)
        self.pushButton_energyX_addCalcSpot.clicked.connect(self.on_energyX_buttom_add_clicked)
        self.pushButton_energyX_remove.clicked.connect(self.on_energyX_delete_clicked)

        self.toolButton_file_hide.clicked.connect(self.on_file_hide_clicked)
        self.toolButton_file_open.clicked.connect(self.on_open_file)
        self.toolButton_file_close.clicked.connect(self.on_file_delete_clicked)

        self.pushButton_smooth_no.clicked.connect(self.on_tool_smooth_clicked)
        self.pushButton_smooth_yes.clicked.connect(self.on_tool_smooth_yes_clicked)
        self.pushButton_findPeek_no.clicked.connect(self.on_tool_findPeek_clicked)
        self.pushButton_findPeek_yes.clicked.connect(self.do_find_peeks)

        self.pushButton_export_pulse.clicked.connect(self.on_export_pulse_buttom_clicked)

        self.toolButton_library_add.clicked.connect(self.on_add_library_clicked)
        self.toolButton_library_remove.clicked.connect(self.static_remove_library)

        self.spinBox_section_start.valueChanged.connect(self.on_section_spinbox_start_changed)
        self.spinBox_section_end.valueChanged.connect(self.on_section_spinbox_end_changed)

        self.doubleSpinBox_measure_time.valueChanged.connect(self.on_overview_measure_time_changed)
        self.doubleSpinBox_measure_rate.valueChanged.connect(self.on_overview_measure_rate_changed)

        self.comboBox_originalFile.currentTextChanged.connect(self.static_infoTab_rr_update)

        self.listWidget_file.itemSelectionChanged.connect(self.on_file_changed)
        self.listWidget_findPeek_peeks.itemSelectionChanged.connect(self.on_peek_changed)

        self.pushButton_pulseInfo_draw.clicked.connect(self.static_update_pulseInfo)

        # prob gragh init
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.prob_plot_window = Mod_PlotWidget(self)
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.prob_plot_window.setSizePolicy(sizePolicy)
        self.prob_plot_window.plotItem.setLabels(bottom="Channel(ch)")
        self.prob_plot_window.plotItem.showGrid(x=True, y=True, alpha=0.5)
        self.prob_plot_window.plotItem.showAxes("top")
        self.prob_plot_window.plotItem.showAxes("right")
        self.prob_plot_window.setBackground(None)
        self.prob_plot_window.setMouseEnabled(False, False)
        self.prob_plot_window.setXRange(1, 1024)
        self.prob_plot_window.setYRange(0, 1)
        self.prob_plot = None

        self.verticalLayout_probGragh.addWidget(self.prob_plot_window)
        self.setLayout(self.verticalLayout_probGragh)

        # linear graph init
        self.linearReg_plot_window = Mod_PlotWidget(self)
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.linearReg_plot_window.setSizePolicy(sizePolicy)
        self.linearReg_plot_window.plotItem.setLabels(left="测试谱计数幅度", bottom="原始谱计数幅度")
        self.linearReg_plot_window.plotItem.showGrid(x=True, y=True, alpha=0.5)
        self.linearReg_plot_window.plotItem.showAxes("top")
        self.linearReg_plot_window.plotItem.showAxes("right")
        self.linearReg_plot_window.setBackground(None)
        self.linearReg_plot_window.setMouseEnabled(False, False)
        self.linearReg_plot = None
        self.linearReg_dots_plot = None

        self.verticalLayout_linarGragh.addWidget(self.linearReg_plot_window)
        self.setLayout(self.verticalLayout_linarGragh)

        # pulse graph init
        self.pulse_plot_window = Mod_PlotWidget(self)
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.pulse_plot_window.setSizePolicy(sizePolicy)
        self.pulse_plot_window.plotItem.setLabels(left="幅度", bottom="时间(s)")
        self.pulse_plot_window.plotItem.showGrid(x=False, y=True, alpha=0.5)
        self.pulse_plot_window.plotItem.showAxes("top")
        self.pulse_plot_window.plotItem.showAxes("right")
        self.pulse_plot_window.setBackground(None)
        self.pulse_plot_window.setMouseEnabled(True, True)

        self.verticalLayout_pulse_gragh.addWidget(self.pulse_plot_window)
        self.setLayout(self.verticalLayout_pulse_gragh)

        self.pulse_plot = None

        # pulse time graph init
        self.pulse_plot_time_window = Mod_PlotWidget(self)
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.pulse_plot_time_window.setSizePolicy(sizePolicy)
        self.pulse_plot_time_window.plotItem.setLabels(left="概率", bottom="脉冲间隔时间(ms)")
        self.pulse_plot_time_window.plotItem.showGrid(x=True, y=True, alpha=0.5)
        self.pulse_plot_time_window.plotItem.showAxes("top")
        self.pulse_plot_time_window.plotItem.showAxes("right")
        self.pulse_plot_time_window.setBackground(None)
        self.pulse_plot_time_window.setMouseEnabled(False, False)
        self.linearReg_plot = None
        self.linearReg_dots_plot = None

        self.verticalLayout_pulse_time_gragh.addWidget(self.pulse_plot_time_window)
        self.setLayout(self.verticalLayout_pulse_time_gragh)

        # main graph init
        pg.setConfigOptions(leftButtonPan=True,
                            antialias=True,
                            useOpenGL=True)
        pg.setConfigOption('background', 'k')
        pg.setConfigOption('foreground', 'd')
        self.plot_window = Mod_PlotWidget(self)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.plot_window.setSizePolicy(sizePolicy)
        self.plot_window.setCursor(Qt.CrossCursor)
        self.plot_window.plotItem.setLabels(left="CPS(cps)", bottom="Channel(ch)")
        self.plot_window.plotItem.showGrid(x=True, y=True, alpha=0.5)

        self.signal_mouse_move = pg.SignalProxy(self.plot_window.scene().sigMouseMoved,
                                                rateLimit=60, slot=self.on_mouse_moved)
        self.signal_mouse_click = pg.SignalProxy(self.plot_window.scene().sigMouseClicked,
                                                 rateLimit=60, slot=self.on_mouse_clicked)

        self.plot_window.bind_mousePressEvent(self.on_mouse_section_pressed)
        self.plot_window.bind_mouseReleaseEvent(self.on_mouse_section_released)
        self.plot_window.bind_keyPressEvent(self.on_key_section_ctrl_pressed)
        self.plot_window.bind_keyReleaseEvent(self.on_key_section_ctrl_released)

        self.gridLayout_Graph.addWidget(self.plot_window)
        self.setLayout(self.gridLayout_Graph)

        # random color manager init
        self.color_manager = ColorManager()

        # paint in main graph init
        self.vLine = pg.InfiniteLine(angle=90, movable=False)
        self.vLine.setPen(pg.mkPen(color=(255, 255, 0, 0), width=1.5))

        self.vLine_peek_ROI = pg.PlotDataItem()
        self.vLine_peek_ROI.setPen(pg.mkPen(color=(255, 255, 0, 100), width=3))
        self.vLine_peek_ROI.setBrush(pg.mkBrush(color=(255, 255, 0, 80)))
        self.vLine_peek_ROI.setFillLevel(0)

        self.section_item = pg.LinearRegionItem(pen=pg.mkPen(color=(255, 200, 0, 0), width=1.5))
        self.section_item.setMovable(False)
        self.do_hide_section()

        self.label = pg.TextItem()
        self.plot_window.addItem(self.vLine)
        self.plot_window.addItem(self.label)
        self.plot_window.addItem(self.section_item)
        self.plot_window.addItem(self.vLine_peek_ROI)
        self.plot_window.plotItem.getViewBox().disableAutoRange()
        # self.plot_window.plotItem.disableAutoScale()

        self.section = [0, 0]
        self.plot_limit = 1024

        self.plot_window.plotItem.getViewBox().setLimits(xMin=-9, xMax=self.plot_limit + 9, yMin=-9)

        # flags
        self.flag_file_opened = False
        self.flag_energyX_available = False
        self.flag_section_pressed = False
        self.flag_section_ctrl_pressed = False
        self.flag_vline_visibility = True
        self.flag_shift_pressed = False
        self.flag_energyX_select = False
        self.flag_measure_changing = False
        self.flag_pulse_generating = False

        """
        [文件名, 原始MCA能谱对象, 当前MCA能谱数据, 颜色, 可见状态,
         plotItemData对象, plotSize,
         listWidgetItem对象,
         [进行过的光滑方法],
         文件类型：["MCA", "PUL"],
         Pulse对象
         ]
        """

        self.file_unpack_dict = {
            "filename": 0,
            "original_mca": 1,
            "current_mca": 2,
            "color": 3,
            "visibility": 4,
            "plot": 5,
            "plot_size": 6,
            "list_item": 7,
            "smoothed": 8,
            "type": 9,
            "pulse": 10
        }
        self.files = []

        self.peeks = []
        self.peek_arrows = []

        self.libraries = []

        """
        [channel, energy]
        """
        self.energyX_dots = []
        self.K_energy_a = 0
        self.K_energy_b = 0

        self.thread_pulse_generator = PulseGenThread(self)
        self.thread_pulse_info_updater = UpdatePulseInfoThread(self)

        self.thread_pulse_generator.setParent(self)
        self.thread_pulse_info_updater.setParent(self)

        self.thread_pulse_info_updater.draw_pulse.connect(self.do_draw_pulse)
        self.thread_pulse_info_updater.draw_pulse_time.connect(self.do_draw_pulse_time)
        self.thread_pulse_generator.open_later.connect(self.static_add_file)

    def static_channel_2_energy(self, channel, a=None, b=None):
        if a is None:
            a = self.K_energy_a
        if b is None:
            b = self.K_energy_b
        return a * channel + b

    def static_get_current_curve(self):
        ele = None
        for ele in self.files:
            if ele[self.file_unpack_dict["list_item"]].isSelected():
                break
        return ele

    def static_get_section(self):
        ret = [0, 0]
        ret[0] = min(self.section)
        ret[1] = max(self.section)
        return ret

    def static_set_section(self, xmin=None, xmax=None):
        if xmin is None:
            xmin = min(self.section)
        if xmax is None:
            xmax = max(self.section)
        section = [xmin, xmax]
        if self.section[1] < self.section[0]:
            section = section[::-1]
        self.section = section

    def static_update_overview(self, measure_update="measure_rate"):
        if len(self.files):
            ele = self.static_get_current_curve()

            total_count = ele[self.file_unpack_dict["current_mca"]].sum()
            average_count = np.mean(ele[self.file_unpack_dict["current_mca"]]())
            max_count = ele[self.file_unpack_dict["current_mca"]].max()
            smooth_methods = ""
            for i in ele[self.file_unpack_dict["smoothed"]]:
                smooth_methods += "{}\n".format(i)

            if not smooth_methods:
                smooth_methods = "未光滑"
            else:
                smooth_methods = smooth_methods[:-1]

            self.prob_plot_window.clear()
            x = np.linspace(1, len(ele[self.file_unpack_dict["current_mca"]]) + 1,
                            len(ele[self.file_unpack_dict["current_mca"]]))
            self.prob_plot = self.prob_plot_window.plot(x, ele[self.file_unpack_dict["current_mca"]].to_probDensity(),
                                                        pen=pg.mkPen(color=(220, 0, 0), width=3))

            o_time = ele[self.file_unpack_dict["original_mca"]].total_time

            self.flag_measure_changing = True
            if o_time:
                self.doubleSpinBox_measure_time.setEnabled(False)
                self.doubleSpinBox_measure_rate.setEnabled(False)
                self.doubleSpinBox_measure_time.setValue(o_time)
                self.doubleSpinBox_measure_rate.setValue(total_count / o_time)
            else:
                self.doubleSpinBox_measure_time.setEnabled(True)
                self.doubleSpinBox_measure_rate.setEnabled(True)
                if measure_update == "measure_rate":
                    if self.doubleSpinBox_measure_time.value():
                        self.doubleSpinBox_measure_rate.setValue(total_count / self.doubleSpinBox_measure_time.value())
                elif measure_update == "measure_time":
                    if self.doubleSpinBox_measure_rate.value():
                        self.doubleSpinBox_measure_time.setValue(total_count / self.doubleSpinBox_measure_rate.value())

            filename = ele[self.file_unpack_dict["filename"]]
            if len(filename) >= 20:
                filename = filename.split(".")
                filename = "{}....{}".format(filename[0][:17], filename[1])
            self.label_filename.setText(filename)
            self.label_smooth.setText(smooth_methods)
            # print(self.K_energy_a, self.K_energy_b)
            if self.flag_energyX_available:
                self.label_energyXclac.setText("已校正, \na:{:.4f}, b:{:.4f}".format(
                    self.K_energy_a, self.K_energy_b))
            else:
                self.label_energyXclac.setText("未校正")
            self.label_total_count.setText("{}".format(int(total_count)))
            self.label_average_count.setText("{}".format(int(average_count)))
            self.label_max_count.setText("{}".format(int(max_count)))

            type = ele[self.file_unpack_dict["type"]]
            if type == "MCA":
                self.label_type.setText("能谱文件")
            elif type == "PUL":
                self.label_type.setText("核脉冲文件")

            self.spinBox_section_start.setMaximum(len(ele[self.file_unpack_dict["current_mca"]]))
            self.spinBox_section_end.setMaximum(len(ele[self.file_unpack_dict["current_mca"]]))

            self.flag_measure_changing = False
        else:
            self.label_filename.setText("无")
            self.label_smooth.setText("未光滑")
            self.label_type.setText("未知")
            self.label_total_count.setText("0")
            self.label_max_count.setText("0")
            self.label_average_count.setText("0")
            self.prob_plot_window.clear()

    def static_reset_plot_view(self):
        if len(self.files):
            ele = self.static_get_current_curve()
            ele[self.file_unpack_dict["plot_size"]]["xRange"][1] = len(ele[self.file_unpack_dict["current_mca"]])
            ele[self.file_unpack_dict["plot_size"]]["yRange"][1] = ele[self.file_unpack_dict["current_mca"]].max()
            self.plot_window.plotItem.setRange(**ele[self.file_unpack_dict["plot_size"]], update=True)
            self.static_flush_graph()

    def static_add_file(self, mca_object, filename):
        assert isinstance(mca_object, MCA)

        type = "MCA"
        pulse = None

        if filename.split(".")[-1] == "tps":
            type = "PUL"
            pulse = Pulses(filename)

        filename = filename.split("/")[-1]
        filename = filename.split("\\")[-1]

        if len(self.files) > 32:
            pop_notice(QMessageBox.Warning, "警告", "最多同时打开32个谱线文件，现已打开{}个".format(len(self.files)))
            return

        filenames = [ele[0] for ele in self.files]

        if filename in filenames:
            pop_notice(QMessageBox.Warning, "警告", "\"{}\"已在文件列表中，无需再次读取".format(filename))
            return

        x = np.linspace(1, len(mca_object()) + 1, len(mca_object()))
        color = self.color_manager.get_color()
        axis_range = {"xRange": [0, len(x)], "yRange": [0, max(mca_object())]}

        if self.toolButton_select.isChecked():
            self.do_show_vlineCurse()

        self.plot_window.plotItem.setRange(**axis_range, update=True)

        plot = self.plot_window.plot(x, mca_object.as_numpy(),
                                     name=filename, pen=pg.mkPen(color=color, width=1.7))

        color_icon = np.zeros((64, 64, 3), dtype=np.uint8)
        for i in range(3):
            color_icon[:, :, i] = color[i]

        enX_a = mca_object.energyX_a
        enX_b = mca_object.energyX_b

        if enX_a:
            self.K_energy_a = enX_a
            self.K_energy_b = enX_b

            self.on_energyX_buttom_add_clicked(ch=0,
                                               energy=self.static_channel_2_energy(0),
                                               ignore_if_available=True)
            self.on_energyX_buttom_add_clicked(ch=512,
                                               energy=self.static_channel_2_energy(512),
                                               ignore_if_available=True)

        list_item = QListWidgetItem(QIcon(QPixmap(QImage(color_icon.data,
                                                         color_icon.shape[1],
                                                         color_icon.shape[0],
                                                         color_icon.shape[1] * 3,
                                                         QImage.Format_RGB888)
                                                  )
                                          ), filename, parent=self.listWidget_file
                                    )

        self.listWidget_file.addItem(list_item)
        list_item.setSelected(True)

        if not self.flag_file_opened:
            self.flag_file_opened = True
            list_item.setSelected(True)

        ele = [filename, mca_object, mca_object.copy(),
               color, True, plot, axis_range, list_item, [],
               type, pulse]

        self.files.append(ele)

        self.static_update_overview()
        self.static_flush_graph()
        self.static_infoTab_to_default()
        self.on_file_changed()

        if len(mca_object()) > self.plot_limit:
            self.plot_limit = len(mca_object())

        self.plot_window.plotItem.getViewBox().setLimits(xMin=-9, xMax=self.plot_limit + 9, yMin=-9)

    def static_restore_current_file(self):
        if self.flag_file_opened:
            plot = self.static_get_current_curve()
            plot[self.file_unpack_dict["current_mca"]] = plot[self.file_unpack_dict["original_mca"]].copy()
            plot[self.file_unpack_dict["smoothed"]] = []
            self.static_flush_graph()
            self.static_update_overview()

    def static_update_energyX(self):
        if len(self.energyX_dots) >= 2:
            x = [ele[0] for ele in self.energyX_dots]
            y = [ele[1] for ele in self.energyX_dots]
            b, a = linear_regression(x=x, y=y)
            self.K_energy_a = a
            self.K_energy_b = b
            self.flag_energyX_available = True
        else:
            self.flag_energyX_available = False
            self.label_energyXclac.setText("未校正")

    def static_flush_graph(self):
        for ele in self.files:
            x = np.linspace(1, len(ele[self.file_unpack_dict["current_mca"]] + 1),
                            len(ele[self.file_unpack_dict["current_mca"]]))
            plot = ele[self.file_unpack_dict["plot"]]
            # plot.clear()

            if not ele[self.file_unpack_dict["visibility"]]:
                width = 3
                color = [*ele[self.file_unpack_dict["color"]], 0]
            elif ele[self.file_unpack_dict["list_item"]].isSelected():
                width = 3
                color = [*ele[self.file_unpack_dict["color"]], 255]
            else:
                width = 1
                color = [*ele[self.file_unpack_dict["color"]], 160]

            plot.setData(x, ele[self.file_unpack_dict["current_mca"]],
                         pen=pg.mkPen(color=color, width=width))
        axis_range = {"xRange": self.plot_window.plotItem.getViewBox().viewRange()[0],
                      "yRange": self.plot_window.plotItem.getViewBox().viewRange()[1]}
        self.plot_window.plotItem.setRange(
            **axis_range, padding=0, update=True
        )

    def static_infoTab_to_default(self, plot=None):
        if not self.flag_file_opened:
            return
        if plot is None:
            plot = self.static_get_current_curve()
        if self.toolButton_findPeek.isChecked():
            self.tabWidget_top.setTabVisible(1, True)
            self.stackedWidget_info.setCurrentIndex(0)
        else:
            if plot[self.file_unpack_dict["type"]] == "PUL":
                self.tabWidget_top.setTabVisible(1, True)
                self.stackedWidget_info.setCurrentIndex(2)
                if plot[self.file_unpack_dict["pulse"]].data.ndim == 2:
                    self.tabWidget_top.setTabVisible(2, True)
                else:
                    self.tabWidget_top.setTabVisible(2, False)
            else:
                self.tabWidget_top.setTabVisible(1, False)
                self.tabWidget_top.setTabVisible(2, False)

    def static_infoTab_rr_update(self):
        original_filename = self.comboBox_originalFile.currentText()
        files = [ele[self.file_unpack_dict["filename"]] for ele in self.files]
        self.linearReg_plot_window.clear()
        self.label_r_square.setText("0.0")
        if original_filename not in files:
            return
        original_plot = None
        for i, ele in enumerate(files):
            if original_filename == ele:
                original_plot = self.files[i][self.file_unpack_dict["current_mca"]].copy()
        current_plot = self.static_get_current_curve()[self.file_unpack_dict["current_mca"]].copy()
        rr, a, b = get_R_square(original_plot, current_plot)
        original_plot().sort()
        current_plot().sort()
        self.label_r_square.setText("{:.4f}".format(rr))
        self.linearReg_dots_plot = self.linearReg_plot_window.plot(original_plot, current_plot,
                                                                   pen=None, symbol='o',
                                                                   symbolPen=None, symbolSize=6,
                                                                   symbolBrush=(0, 50, 200))
        x = np.linspace(0, original_plot.max(), len(original_plot))
        y = a * x + b
        self.linearReg_plot = self.linearReg_plot_window.plot(x, y, pen=pg.mkPen(color=(200, 50, 0), width=3))
        self.linearReg_plot_window.setXRange(0, original_plot.max())
        self.linearReg_plot_window.setYRange(0, current_plot.max())

    def static_topBar_update(self):
        csp_rate = self.doubleSpinBox_measure_rate.value()
        total_time = self.doubleSpinBox_measure_time.value()

        self.doubleSpinBox_pulse_csp_rate.setValue(csp_rate)
        self.doubleSpinBox_pulse_measure_time.setValue(total_time)

    def static_update_pulseInfo(self):
        if not self.thread_pulse_info_updater.isFinished():
            self.thread_pulse_info_updater.terminate()
        self.thread_pulse_info_updater.set_curve(self.static_get_current_curve())
        self.thread_pulse_info_updater.start()

    def static_update_windowTitle(self):
        current_curve = self.static_get_current_curve()
        if current_curve is None:
            self.setWindowTitle("Pucleus 核脉冲数据生成分析")
        else:
            self.setWindowTitle("Pucleus 核脉冲数据生成分析 - {}".format(
                current_curve[self.file_unpack_dict["filename"]]
            ))

    def static_output_tch(self, filename):
        curve = self.static_get_current_curve()[self.file_unpack_dict["current_mca"]]
        if curve is None:
            return
        assert isinstance(curve, MCA)
        if self.flag_energyX_available and not curve.energyX_a:
            curve.energyX_a = self.K_energy_a
            curve.energyX_b = self.K_energy_b
        curve.to_file(filename)

    def static_clear_pulseInfo(self):
        self.pulse_plot_window.clear()
        self.pulse_plot_time_window.clear()

    def static_update_findPeekInfo(self):
        self.listWidget_findPeek_peeks.clear()
        for i, ele in enumerate(self.peeks):
            assert isinstance(ele, Peek)
            peek_location = ele.peek_location()
            if len(self.peeks) // 1000:
                peek = "{:0>4}. 峰位 {:.2f} ch".format(i + 1, peek_location)
            elif len(self.peeks) // 100:
                peek = "{:0>3}. 峰位 {:.2f} ch".format(i + 1, peek_location)
            elif len(self.peeks) // 10:
                peek = "{:0>2}. 峰位 {:.2f} ch".format(i + 1, peek_location)
            else:
                peek = "{}. 峰位 {:.2f} ch".format(i + 1, peek_location)
            if self.flag_energyX_available:
                peek += "/{:.2f} KeV".format(self.static_channel_2_energy(peek_location))
            list_item = QListWidgetItem(peek, parent=self.listWidget_findPeek_peeks)
            self.listWidget_findPeek_peeks.addItem(list_item)

    def static_add_library(self, filenames):
        for i in filenames:
            try:
                lib = Library(i)
                if lib.filename in [ele.filename for ele in self.libraries]:
                    raise Exception("{} 已经在核素库列表中".format(lib.filename))
            except Exception as err:
                pop_notice(QMessageBox.Warning, "错误", "无法导入核素库\n\n{}".format(err))
                continue
            self.libraries.append(lib)
            basic, details = lib.summary()
            list_item = QListWidgetItem(basic, self.listWidget_libraries)
            list_item.setToolTip(details)
            self.listWidget_libraries.addItem(list_item)
            self.listWidget_libraries.setCurrentRow(0)

    def static_remove_library(self):
        if self.libraries:
            index = self.listWidget_libraries.currentRow()
            self.libraries.pop(index)
            self.listWidget_libraries.takeItem(index)

    def do_find_peeks(self):
        curve = self.static_get_current_curve()  # 获取当前选中的能谱对象
        if curve is None:  # 若没有获取到能谱则返回
            return
        curve_plot = curve[self.file_unpack_dict["plot"]]
        curve = curve[self.file_unpack_dict["current_mca"]]
        if not isinstance(curve, MCA):  # 若不是MCA对象则返回
            return
        self.do_clear_peek()  # 清楚已经绘制的峰图像
        algorithm = self.comboBox_findPeek_algo.currentText()  # 获取窗口上选择的寻峰算法
        ranges = self.static_get_section()  # 获取当前选区
        if (ranges[1] - ranges[0]) <= 1:  # 若选取为空，则全选k
            ranges = [0, len(curve) - 1]
        pf = []
        self.logger.DEBUG("[寻峰] 正在使用 {} 算法在 {} 区域内寻峰".format(algorithm, ranges))

        if algorithm == "简单比较法":
            k = self.doubleSpinBox_findPeek_sc_K.value()
            m = self.spinBox_findPeek_sc_M.value()
            ranges = [int(ele) for ele in ranges]
            pf = SimpleCompare(curve, scan_range=ranges, k=k, m=m)

        elif algorithm == "导数法":
            level = self.spinBox_findPeek_deri_level.value()
            dots = self.spinBox_findPeek_deri_dots.value()
            if level == 3 and dots > 7:
                pop_notice(QMessageBox.Warning, "错误", "三阶导数法仅支持最高7点设置")
                return
            ranges = [int(ele) for ele in ranges]
            pf = Derivative(curve, ranges, level, dots)

        self.peeks = pf  # 将寻到的峰暂存到内存中
        self.static_update_findPeekInfo()  # 更新画面以显示所寻到的峰

        symbol = QPainterPath()
        symbol.lineTo(0, 0)
        symbol.lineTo(0.2, -1)
        symbol.lineTo(-0.2, -1)
        symbol.lineTo(0, 0)

        for i, peek in enumerate(self.peeks):
            x, y = peek.peek_point()
            item = ModTargetItem((x + 1, y), size=30,
                                 movable=False, symbol=symbol, item_ID=i)
            item.setPen(color=(220, 220, 220, 50), width=1.5)
            item.setBrush(color=(200, 200, 200, 50))
            item.setHoverPen(color=(255, 255, 255), width=1.5)
            item.setHoverBrush(color=(220, 220, 220))
            item.clicked.connect(self.on_peek_arrow_clicked)
            self.plot_window.addItem(item)
            self.peek_arrows.append(item)

        self.do_display_nucleo()

        self.logger.INFO("[寻峰] 找到 {} 个峰, 已将各峰位绘制在图上".format(len(self.peeks)))

    def do_display_nucleo(self):
        if not self.libraries or not self.flag_energyX_available \
                or not self.peeks:
            return
        min_gap = 10
        if self.action_showNuclide.isChecked():
            if self.libraries and self.flag_energyX_available:
                min_gap = self.static_channel_2_energy(self.peeks[-1].mean) - \
                          self.static_channel_2_energy(self.peeks[0].mean)

                for i, ele in enumerate(self.peeks[:-1]):
                    gap = self.static_channel_2_energy(self.peeks[i + 1].mean) - \
                          self.static_channel_2_energy(ele.mean)
                    if gap and gap < min_gap:
                        min_gap = gap

                for i in self.libraries:
                    assert isinstance(i, Library)
                    i.set_KE(min_gap)

            for i, item in enumerate(self.peek_arrows):
                msg = ""
                energy = self.static_channel_2_energy(self.peeks[i].peek_location())
                res = []
                for lib in self.libraries:
                    assert isinstance(lib, Library)
                    res += lib.match(energy)
                for la in res:
                    msg += "{}, ".format(la.name)
                if msg:
                    msg = msg[:-2]
                item.setLabel(msg, labelOpts={"offset": (9, 31),
                                              "anchor": (0, 1),
                                              "angle": 60,
                                              "color": pg.mkColor(150, 150, 128)})

    def do_draw_peek(self, peek, index=0):
        isinstance(peek, Peek)
        res = []

        for i, item in enumerate(self.peek_arrows):
            item.setPen(color=(220, 220, 220, 50), width=1.5)
            item.setBrush(color=(200, 200, 200, 50))
            item.setLabel()

        self.do_display_nucleo()

        signed_plot = peek.get_clip_feature_array()
        self.vLine_peek_ROI.clear()
        self.vLine_peek_ROI.setData(*signed_plot)
        self.vLine_peek_ROI.updateItems()
        item = self.peek_arrows[index]
        item.setPen(color=(255, 255, 0), width=3)
        item.setBrush(color=(200, 200, 0))
        peek_location, peek_hight = peek.peek_point()

        if self.libraries and self.flag_energyX_available:  # 核素识别
            res = []
            for i in self.libraries:
                assert isinstance(i, Library)
                res += i.match(self.static_channel_2_energy(peek_location))

        pos = "{:.2f} ch".format(peek_location)
        if self.flag_energyX_available:
            pos += "/{:.4f} KeV".format(self.static_channel_2_energy(peek_location))
        msg = "峰位：{}\n计数：{:.4f}\n峰面积：{}\n净峰面积：{:.4f}".format(
            pos, peek_hight, peek.area(), peek.pure_area()
        )
        if res:
            msg += "\n------\n可能的核素："
            for i in res:
                msg += "\n{}".format(i)

        item.setLabel(msg, labelOpts={"offset": (-9, 31),
                                      "fill": pg.mkBrush(color=(50, 50, 0)),
                                      "anchor": (0, 1)})

    def do_clear_peek(self):
        self.vLine_peek_ROI.clear()
        self.vLine_peek_ROI.setData([0], [0])
        self.vLine_peek_ROI.updateItems()
        for i in self.peek_arrows:
            self.plot_window.removeItem(i)
        self.listWidget_findPeek_peeks.clear()
        self.peek_arrows = []
        self.peeks = []

    def do_hide_peek_selection(self):
        self.vLine_peek_ROI.clear()
        self.vLine_peek_ROI.setData([0], [0])
        self.vLine_peek_ROI.updateItems()
        for item in self.peek_arrows:
            item.setPen(color=(220, 220, 220, 50), width=1.5)
            item.setBrush(color=(200, 200, 200, 50))
            item.setLabel()
        self.do_display_nucleo()
        self.listWidget_findPeek_peeks.clearSelection()

    def do_draw_pulse(self, data):
        total_time = data[0][-1]

        self.pulse_plot_window.clear()
        self.pulse_plot_window.plotItem.getViewBox().setLimits(xMin=-2,
                                                               xMax=total_time + 2,
                                                               yMin=-9, yMax=1024 + 9)

        self.pulse_plot = self.pulse_plot_window.plot(*data,
                                                      pen=None,
                                                      symbol='o',
                                                      symbolSize=1,
                                                      symbolPen=None,
                                                      symbolBrush=(191, 93, 17, 50)
                                                      )
        self.logger.INFO("[核脉冲模块] 脉冲预览图已绘制")

    def do_draw_pulse_time(self, data):
        max_time = data[0][-1]

        self.pulse_plot_time_window.clear()
        self.pulse_plot_time_window.plotItem.getViewBox().setLimits(xMin=-2,
                                                                    xMax=max_time + 2,
                                                                    yMin=-0.1, yMax=1.1)
        self.pulse_plot = self.pulse_plot_time_window.plot(*data,
                                                           pen=pg.mkPen(color=(200, 50, 0),
                                                                        width=3,
                                                                        stepMode="left")
                                                           )
        self.logger.INFO("[核脉冲模块] 脉冲时间间隔概率密度图已绘制")

    def do_draw_section(self, section=None):
        if section is None:
            section = self.section
        else:
            self.section = list(section)
        if self.flag_energyX_available:
            range_text = "{} ch/{:.2f} KeV - {} ch/{:.2f} KeV".format(
                int(min(section)), self.static_channel_2_energy(min(section)),
                int(max(section)), self.static_channel_2_energy(max(section))
            )
        else:
            range_text = "{} ch -- {} ch".format(
                int(min(section)), int(max(section))
            )
        if not int(min(section)):
            range_text = "按住Ctrl拖动鼠标快速选择区域"
        self.label_findPeek_range.setText(range_text)
        self.section_item.setBrush(color=(230, 180, 0, 50))
        self.section_item.setRegion(section)
        self.spinBox_section_start.setValue(int(min(section)))
        self.spinBox_section_end.setValue(int(max(section)))

    def do_hide_section(self):
        self.label_findPeek_range.setText("按住Ctrl拖动鼠标快速选择区域")
        self.section_item.setBrush(color=(230, 180, 0, 0))

    def do_hide_vlineCurse(self):
        self.vLine.setPen(pg.mkPen((255, 255, 0, 0), width=1.5))
        self.label.setVisible(False)
        self.static_flush_graph()
        self.flag_vline_visibility = False

    def do_show_vlineCurse(self):
        if not self.flag_file_opened:
            return
        self.vLine.setPen(pg.mkPen((255, 255, 0, 255), width=1.5))
        self.label.setVisible(True)
        self.static_flush_graph()
        self.flag_vline_visibility = True

    def do_generate_pulse(self, filename, csp_rate=None, total_time=None, timed=False, open_later=True):
        if not self.flag_file_opened:
            return

        if filename is None:
            return

        if self.flag_pulse_generating:
            return

        self.thread_pulse_generator.set_values(filename, csp_rate,
                                               total_time, timed,
                                               open_later,
                                               self.static_get_current_curve()
                                               )
        self.thread_pulse_generator.start()

    def on_action_showNucleo_clicked(self):
        self.do_hide_peek_selection()
        self.do_display_nucleo()

    def on_add_library_clicked(self):
        filenames = QFileDialog.getOpenFileNames(caption="打开",
                                                 filter="所有支持的文件格式 (*.xls; *.csv);;"
                                                        "CSV UTF-8 逗号分隔 (*.csv);;"
                                                        "Excel 97-2003 工作簿 (*.xls);;",
                                                 parent=self)[0]
        if filenames:
            self.static_add_library(filenames)
            self.do_display_nucleo()

    def on_peek_arrow_clicked(self, item_id):
        self.listWidget_findPeek_peeks.setCurrentRow(item_id)
        self.on_peek_changed()

    def on_peek_changed(self):
        item = self.listWidget_findPeek_peeks.currentIndex().row()
        if not self.peeks:
            self.do_clear_peek()
            return
        peek = self.peeks[item]
        self.do_draw_peek(peek, item)

    def on_energyX_delete_clicked(self):
        item = self.listWidget_energyX_calaSpots.currentItem()
        if item is None:
            return
        self.energyX_dots.pop(self.listWidget_energyX_calaSpots.currentRow())
        # print(self.energyX_dots)
        self.listWidget_energyX_calaSpots.takeItem(self.listWidget_energyX_calaSpots.currentRow())
        del item
        if len(self.files) < 2:
            self.flag_energyX_available = False
        self.static_update_energyX()
        self.static_update_overview()

    def on_file_delete_clicked(self):
        if not self.flag_file_opened:
            return
        item = self.listWidget_file.currentItem()
        for i, ele in enumerate(self.files):
            if ele[self.file_unpack_dict["list_item"]].isSelected():
                self.plot_window.removeItem(ele[self.file_unpack_dict["plot"]])
                self.files.pop(i)
                break
        self.listWidget_file.takeItem(self.listWidget_file.currentRow())
        del item
        if not len(self.files):
            self.listWidget_file.clear()
            self.flag_file_opened = False
        self.on_file_changed()

    def on_mouse_section_pressed(self, event):
        assert isinstance(event, QMouseEvent)
        vb = self.plot_window.plotItem.getViewBox()
        if self.toolButton_section.isChecked() and event.button() == 1:
            # vb.enableAutoRange()
            vb.setMouseEnabled(False, False)
            pos = vb.mapSceneToView(event.pos())
            self.section[0] = pos.x()
            self.flag_section_pressed = True
            self.plot_window.setCursor(Qt.IBeamCursor)
        elif self.flag_energyX_select and event.button() == 1:
            pass
        elif event.button() in (1, 4):
            self.plot_window.setCursor(Qt.ClosedHandCursor)
        elif event.button() == 2:
            self.plot_window.setCursor(Qt.SizeBDiagCursor)

    def on_mouse_section_released(self, event):
        assert isinstance(event, QMouseEvent)
        vb = self.plot_window.plotItem.getViewBox()
        if self.toolButton_section.isChecked() and event.button() == 1:
            # vb.disableAutoRange()
            vb.setMouseEnabled(True, True)
            pos = vb.mapSceneToView(event.pos())
            self.section[1] = pos.x()
        elif self.flag_energyX_select and event.button() == 1:
            plot = self.static_get_current_curve()
            data_len = len(plot[self.file_unpack_dict["current_mca"]])
            pos = vb.mapSceneToView(event.pos())
            if 0 < pos.x() < data_len:
                self.spinBox_energyX_channel_set.setValue(pos.x())
                self.toolButton_energyX_select.setChecked(False)
                self.on_energyX_button_select_clicked()

        self.flag_section_pressed = False
        self.on_tool_curse_clicked()

    def on_overview_measure_time_changed(self):
        if self.flag_measure_changing:
            return
        self.static_update_overview(measure_update="measure_rate")

    def on_overview_measure_rate_changed(self):
        if self.flag_measure_changing:
            return
        self.static_update_overview(measure_update="measure_time")

    def on_section_spinbox_start_changed(self):
        self.static_set_section(xmin=self.spinBox_section_start.value())
        self.spinBox_section_end.setMinimum(self.spinBox_section_start.value())
        self.spinBox_section_start.setMaximum(self.spinBox_section_end.value())
        self.do_draw_section()

    def on_section_spinbox_end_changed(self):
        self.static_set_section(xmax=self.spinBox_section_end.value())
        self.spinBox_section_end.setMinimum(self.spinBox_section_start.value())
        self.spinBox_section_start.setMaximum(self.spinBox_section_end.value())
        self.do_draw_section()

    def on_key_section_ctrl_pressed(self, event):
        assert isinstance(event, QKeyEvent)
        if event.key() == 16777248:
            self.flag_shift_pressed = True

        elif event.key() == 16777249 and not self.toolButton_section.isChecked():
            self.flag_section_ctrl_pressed = True
            self.toolButton_section.setChecked(True)
            self.on_tool_section_clicked()

    def on_key_section_ctrl_released(self, event):
        assert isinstance(event, QKeyEvent)
        if event.key() == 16777248:
            self.flag_shift_pressed = False

        elif event.key() == 16777249 and self.flag_section_ctrl_pressed:
            self.flag_section_ctrl_pressed = False
            self.toolButton_section.setChecked(False)
            self.on_tool_section_clicked()

    def on_energyX_buttom_add_clicked(self, *kwargs, ch=None, energy=None, ignore_if_available=False):
        if self.flag_energyX_available and ignore_if_available:
            return
        if ch is None:
            ch = self.spinBox_energyX_channel_set.value()
        if energy is None:
            energy = self.doubleSpinBox_energyX_energy_set.value()
        dot_str = "{} ch -> {} KeV".format(ch, energy)
        if ch in [ele[0] for ele in self.energyX_dots]:
            pop_notice(QMessageBox.Warning, "提示", "道址为 {} 的校准点已经存在".format(ch))
            return

        list_item = QListWidgetItem(dot_str, parent=self.listWidget_energyX_calaSpots)

        self.spinBox_energyX_channel_set.setValue(1)
        self.doubleSpinBox_energyX_energy_set.setValue(0.0)
        self.listWidget_energyX_calaSpots.addItem(list_item)
        self.energyX_dots.append([ch, energy])

        self.static_update_energyX()
        self.static_update_overview()

    def on_energyX_button_select_clicked(self):
        if not self.flag_file_opened:
            self.toolButton_energyX_select.setChecked(False)
            return

        if self.toolButton_energyX_select.isChecked():
            self.plot_window.setCursor(Qt.ArrowCursor)
            self.flag_energyX_select = True
        else:
            self.flag_energyX_select = False
            self.on_tool_curse_clicked()

    def on_zoom_in(self):
        axis_range = {"xRange": self.plot_window.plotItem.getViewBox().viewRange()[0],
                      "yRange": self.plot_window.plotItem.getViewBox().viewRange()[1]}

        size = axis_range["xRange"][1] - axis_range["xRange"][0]
        size *= 0.1

        axis_range["xRange"][0] += size
        axis_range["xRange"][1] -= size

        size = axis_range["yRange"][1] - axis_range["yRange"][0]
        size *= 0.1

        axis_range["yRange"][0] += size
        axis_range["yRange"][1] -= size

        self.plot_window.plotItem.setRange(
            **axis_range, padding=0, update=True
        )

    def on_zoom_out(self):
        axis_range = {"xRange": self.plot_window.plotItem.getViewBox().viewRange()[0],
                      "yRange": self.plot_window.plotItem.getViewBox().viewRange()[1]}

        size = axis_range["xRange"][1] - axis_range["xRange"][0]
        size *= 0.1

        axis_range["xRange"][0] -= size
        axis_range["xRange"][1] += size

        size = axis_range["yRange"][1] - axis_range["yRange"][0]
        size *= 0.1

        axis_range["yRange"][0] -= size
        axis_range["yRange"][1] += size

        self.plot_window.plotItem.setRange(
            **axis_range, padding=0, update=True
        )

    def on_tool_smooth_yes_clicked(self):
        if not self.flag_file_opened:
            return
        plot = self.static_get_current_curve()

        method = self.comboBox_smoothAlgo.currentIndex()
        method_str = self.comboBox_smoothAlgo.currentText()

        if method == 0:  # 平均移动法
            arg = self.spinBox_smooth_avg.value()
            msg = "{} 点{}".format(arg, method_str)
            plot[self.file_unpack_dict["smoothed"]].append(msg)
            smo = smooth.Mean(plot[self.file_unpack_dict["current_mca"]])
            plot[self.file_unpack_dict["current_mca"]] = smo(arg)

        elif method == 1:  # 重心法
            arg = self.spinBox_smooth_gra.value()
            msg = "{} 点{}".format(arg, method_str)
            plot[self.file_unpack_dict["smoothed"]].append(msg)
            smo = smooth.BaryCenter(plot[self.file_unpack_dict["current_mca"]])
            plot[self.file_unpack_dict["current_mca"]] = smo(arg)

        elif method == 2:  # 最小二乘法
            h = self.spinBox_smooth_LSM_h.value()
            dots = self.spinBox_smooth_LSM_dots.value()
            msg = "{} 点{} 间距{}".format(dots, method_str, h)
            plot[self.file_unpack_dict["smoothed"]].append(msg)
            m = (dots - 1) // 2
            smo = smooth.PolynomialLeastSquareMethod(plot[self.file_unpack_dict["current_mca"]])
            plot[self.file_unpack_dict["current_mca"]] = smo(m, h)

        self.static_flush_graph()
        self.static_update_overview()
        self.toolButton_smooth.setChecked(False)
        self.on_tool_smooth_clicked()

    def on_tool_genPulse_button_clicked(self):
        if self.toolButton_genPulse.isChecked():
            self.toolButton_smooth.setChecked(False)
            self.toolButton_section.setChecked(False)
            self.toolButton_findPeek.setChecked(False)
            self.stackedWidget_tool.setCurrentIndex(4)
            self.stackedWidget_info.setCurrentIndex(2)

            if not self.tabWidget_top.isTabVisible(1):
                self.tabWidget_top.setTabVisible(1, True)

        else:
            self.tabWidget_top.setTabVisible(1, False)
            self.stackedWidget_tool.setCurrentIndex(0)
            self.static_infoTab_to_default()

    def on_tool_section_clicked(self):
        if self.toolButton_section.isChecked():
            self.toolButton_smooth.setChecked(False)
            self.toolButton_genPulse.setChecked(False)
            if not self.toolButton_findPeek.isChecked():
                self.stackedWidget_tool.setCurrentIndex(1)
            self.plot_window.plotItem.getViewBox().setAutoPan(True)
        else:
            if not self.toolButton_findPeek.isChecked():
                self.stackedWidget_tool.setCurrentIndex(0)
            self.plot_window.plotItem.getViewBox().setAutoPan(False)
            self.static_infoTab_to_default()

    def on_tool_smooth_clicked(self):
        if self.toolButton_smooth.isChecked():
            self.toolButton_findPeek.setChecked(False)
            self.toolButton_genPulse.setChecked(False)
            self.toolButton_section.setChecked(False)
            self.stackedWidget_tool.setCurrentIndex(2)
            self.do_hide_section()
        else:
            self.stackedWidget_tool.setCurrentIndex(0)
            self.static_infoTab_to_default()

    def on_tool_findPeek_clicked(self):
        if self.toolButton_findPeek.isChecked():
            self.toolButton_smooth.setChecked(False)
            self.toolButton_genPulse.setChecked(False)
            self.stackedWidget_tool.setCurrentIndex(3)
            if not self.tabWidget_top.isTabVisible(1):
                self.tabWidget_top.setTabVisible(1, True)
            self.tabWidget_top.setCurrentIndex(1)
            self.stackedWidget_info.setCurrentIndex(0)
        else:
            if self.toolButton_section.isChecked():
                self.stackedWidget_tool.setCurrentIndex(1)
            else:
                self.stackedWidget_tool.setCurrentIndex(0)
            self.static_infoTab_to_default()

    def on_tool_curse_clicked(self):
        if self.toolButton_select.isChecked():
            self.do_show_vlineCurse()
            self.plot_window.setCursor(Qt.CrossCursor)
        else:
            self.do_hide_vlineCurse()
            self.plot_window.setCursor(Qt.ArrowCursor)

    def on_file_hide_clicked(self):
        if not self.flag_file_opened:
            return
        ele = self.static_get_current_curve()
        if self.toolButton_file_hide.isChecked():
            ele[self.file_unpack_dict["visibility"]] = False
        else:
            ele[self.file_unpack_dict["visibility"]] = True
        self.on_file_changed()

    def on_file_changed(self):
        # self.static_reset_plot_view()
        self.comboBox_originalFile.clear()
        self.comboBox_originalFile.addItem("选择原始能谱文件")
        self.peeks = []
        for ele in self.files:
            list_item = ele[self.file_unpack_dict["list_item"]]
            filename = ele[self.file_unpack_dict["filename"]]
            if ele[self.file_unpack_dict["visibility"]]:
                list_item.setText("{}".format(filename))
                if list_item.isSelected():
                    self.toolButton_file_hide.setChecked(False)
                    self.static_infoTab_to_default(ele)
                else:
                    self.comboBox_originalFile.addItem(filename)
            else:
                list_item.setText("(已隐藏) {}".format(filename))
                if list_item.isSelected():
                    self.toolButton_file_hide.setChecked(True)

        self.static_infoTab_rr_update()
        self.static_topBar_update()
        self.static_flush_graph()
        self.static_update_overview()
        self.static_clear_pulseInfo()
        self.do_clear_peek()
        # self.static_update_pulseInfo()
        self.static_update_windowTitle()

        self.peek_arrows = []

    def on_mouse_clicked(self, evt):
        evt = evt[0]
        if evt.double():
            if self.toolButton_section.isChecked() and self.flag_file_opened:
                plot = self.static_get_current_curve()
                xmax = len(plot[self.file_unpack_dict["current_mca"]])
                self.section = [0, xmax]
                self.do_draw_section()
            else:
                self.on_open_file()
        else:
            self.do_draw_section((0, 0))
            self.do_hide_peek_selection()
            trans = [evt.scenePos()]
            self.on_mouse_moved(trans)
        evt.accept()

    def on_mouse_moved(self, evt):
        pos = evt[0]  ## using signal proxy turns original arguments into a tuple
        for ele in self.files:
            if not ele[self.file_unpack_dict["list_item"]].isSelected():
                continue
            plot = self.plot_window.plotItem
            vb = plot.getViewBox()
            data = ele[self.file_unpack_dict["current_mca"]]()

            if plot.sceneBoundingRect().contains(pos):
                mouse_point = vb.mapSceneToView(pos)
                index = int(mouse_point.x())
                engergy = "不可用"

                if 0 < index < len(data):
                    if self.flag_energyX_available:
                        engergy = self.static_channel_2_energy(index)
                        engergy = "{:.3f}".format(engergy)

                    self.lcdNumber_currentPathValue.display("{}".format(index))
                    self.lcdNumber_count.display("{}".format(int(data[index])))
                    self.lcdNumber_energy.display("{}".format(engergy))

                    if self.flag_vline_visibility:
                        self.vLine.setPos(mouse_point.x())
                        self.label.setPos(mouse_point.x(), mouse_point.y())
                        if self.flag_energyX_available:
                            engergy = "{} KeV".format(engergy)
                        self.label.setHtml(
                            "<p style='color:white'>道址：{0} ch</p><p style='color:white'>计数：{1:.3f}</p><p "
                            "style='color:white'>能量：{2}</p>".format(
                                index, data[index], engergy))

                    if self.flag_section_pressed:
                        self.section[1] = mouse_point.x()
                        self.do_draw_section()

    def on_open_file(self):
        local_header = "openfile"
        filenames = QFileDialog.getOpenFileNames(caption="打开",
                                                 filter="所有支持的文件格式 (*.chn; *.tch; *.mca; *.txt; *.tps);;"
                                                        "能谱文件 (*.chn; *.tch; *.mca; *.txt);;"
                                                        "核脉冲文件 (*.tps);;"
                                                        "所有文件类型 (*)",
                                                 parent=self)[0]
        for ele in filenames:
            try:
                self.static_add_file(MCA(ele), ele)
            except Exception as err:
                pop_notice(QMessageBox.Warning, "错误", '能谱数据读取失败，请检查文件是否正确。\n\n{}'.format(err))
                break

    def on_save_file(self):
        local_header = "saver"
        name = self.static_get_current_curve()
        if name is None:
            return
        name = name[self.file_unpack_dict["filename"]]
        filename = QFileDialog.getSaveFileName(caption="导出/另存为",
                                               directory="{}.chn".format(name.split(".")[0]),
                                               filter="CHN ORTEC能谱 (*.chn);;"
                                                      "TXT-ASCII (*.txt);;"
                                                      "MCA-ASCII (*.mca);;"
                                                      "TCH 原创能谱 (*.tch)",
                                               parent=self)[0]
        if filename:
            self.static_output_tch(filename)
            self.static_add_file(MCA(filename), filename)

    def on_action_exportLog(self):
        local_header = "export"
        filename = QFileDialog.getSaveFileName(caption="导出",
                                               filter="log(*.log)",
                                               parent=self)[0]
        if not filename:
            return
        try:
            assert isinstance(self.logger, ModLogger)
            self.logger.export_logs(filename)
        except Exception as err:
            self.logger.ERROR("{} {} failed to export logs to file {}, {}".format(
                self.log_header, local_header, filename, err
            ))
        os.system("start /b notepad.exe {}".format(filename))

    def on_export_pulse_buttom_clicked(self):
        if not self.flag_file_opened:
            return
        if self.flag_pulse_generating:
            pop_notice(QMessageBox.Warning, "提示", "核脉冲生成正在进行，请勿重复点击")
            return

        csp_rate = self.doubleSpinBox_pulse_csp_rate.value()
        measure_time = self.doubleSpinBox_pulse_measure_time.value()
        timed = self.checkBox_pulse_addTimeAxis.isChecked()
        open_after = self.checkBox_pulse_openLater.isChecked()
        current_name = self.static_get_current_curve()[
            self.file_unpack_dict["filename"]
        ].split(".")[0]

        filenames = QFileDialog.getSaveFileName(caption="保存",
                                                directory="{}.tps".format(current_name),
                                                filter="核脉冲文件 (*.tps);;"
                                                       "所有文件类型 (*)",
                                                parent=self)

        filenames = filenames[0]

        if not filenames:
            return

        self.do_generate_pulse(filenames,
                               csp_rate,
                               measure_time,
                               timed,
                               open_after)


def pop_notice(type, title, msg):
    """
    弹窗

    :param type: QMessageBox.Warning等
    :param title: str
    :param msg: str
    :return: None
    """
    mb = QMessageBox(type, title, msg)
    mb.setWindowIcon(QIcon(QPixmap(":/图标/assets/diamond_fill_640.svg")))
    mb.exec_()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ui = MCA_MainUI()
    ui.show()
    extco = app.exec_()
    sys.exit(extco)
