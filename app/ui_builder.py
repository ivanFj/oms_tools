import PyQt6.QtWidgets as widgets
import PyQt6.QtCore as qtcore
import PyQt6.QtGui as qtgui
import PyQt6.QtSvgWidgets as svgwidgets
from oms_api import CountingMethods, Department, LoginFailedToAuthorize
import subprocess
import asyncio
import utils
from qasync import asyncClose
import os
import sys

def _resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

class ButtonWidget(widgets.QPushButton):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setCursor(qtcore.Qt.CursorShape.PointingHandCursor)

class LoadingFrame(widgets.QWidget):
    def __init__(self, width, height, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setGeometry(0, 0, width, height)
        layout = widgets.QVBoxLayout(self)
        svg = svgwidgets.QSvgWidget(_resource_path("loading.svg"))
        svg.setProperty("class", "no-background")
        svg.renderer().setAspectRatioMode(qtcore.Qt.AspectRatioMode.KeepAspectRatio) # type: ignore
        svg.setFixedWidth(300)
        layout.addWidget(svg, alignment = qtcore.Qt.AlignmentFlag.AlignCenter)
        self.setVisible(False)
    
    def show_loading_frame(self):
        self.raise_() # type: ignore
        self.setVisible(True) # type: ignore

    def hide_loading_frame(self):
        self.setVisible(False) # type: ignore

class AnotherWindow(widgets.QWidget):
    def __init__(self, min_width, min_height, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(min_width)
        self.setMinimumHeight(min_height)
        self.setLayout(widgets.QVBoxLayout())

        self.main_container = widgets.QWidget()
        self.main_layout = widgets.QVBoxLayout(self.main_container)
        self.layout().addWidget(self.main_container) # type: ignore

        self.loading_greyout = LoadingFrame(min_width, min_height, parent = self)

class ButtonMenu(widgets.QWidget):
    _previous_button: ButtonWidget | widgets.QPushButton | None = None
    _current_button: ButtonWidget | widgets.QPushButton | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.menu_layout = widgets.QHBoxLayout()
        self.setLayout(self.menu_layout)

    def addWidget(self, widget: ButtonWidget | widgets.QPushButton):
        self.menu_layout.addWidget(widget)
        widget.clicked.connect(lambda: self._set_selected_button(widget))

    def _set_selected_button(self, button):
        self._previous_button = self._current_button
        self._current_button = button

        if self._previous_button:
            self._previous_button.setProperty("class", "")
            self._previous_button.style().unpolish(self._previous_button) # type: ignore
            self._previous_button.style().polish(self._previous_button) # type: ignore
            self._previous_button.update() # type: ignore

        if self._current_button:
            self._current_button.setProperty("class", "selected-button") # type: ignore
            self._current_button.style().unpolish(self._current_button) # type: ignore
            self._current_button.style().polish(self._current_button) # type: ignore
            self._current_button.update() # type: ignore

class ResizableMessageBox(widgets.QMessageBox):
    def __init__(self, *args, **kwargs):
        widgets.QMessageBox.__init__(self, *args, **kwargs)
        ok_button = self.addButton(widgets.QMessageBox.StandardButton.Ok)
        ok_button.setCursor(qtcore.Qt.CursorShape.PointingHandCursor) # type: ignore
        self.setSizeGripEnabled(True)

    def event(self, e):
        result = widgets.QMessageBox.event(self, e)
        self.setMinimumSize(275, 125)
        self.setMaximumSize(500, 500)
        self.setSizePolicy(widgets.QSizePolicy.Policy.Expanding, widgets.QSizePolicy.Policy.Expanding)

        return result

class LoginWidget(widgets.QWidget):
    actionSuccess = qtcore.pyqtSignal(bool)
    error_title = "Login error"
    error_message = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.login_layout = widgets.QVBoxLayout()
        self.setLayout(self.login_layout)
        self.make_inputs()
        self.widget_title = "Login"
    
    def make_inputs(self):
        self.username_container = widgets.QWidget()
        self.username_layout = widgets.QVBoxLayout(self.username_container)
        self.username_label = widgets.QLabel("Username:")
        self.username_input = widgets.QLineEdit()
        self.username_layout.addWidget(self.username_label)
        self.username_layout.addWidget(self.username_input)

        self.password_container = widgets.QWidget()
        self.password_layout = widgets.QVBoxLayout(self.password_container)
        self.password_label = widgets.QLabel("Password:")
        self.password_input = widgets.QLineEdit()
        self.password_layout.addWidget(self.password_label)
        self.password_layout.addWidget(self.password_input)

        self.action_button = ButtonWidget("Login")
        self.username_container.setSizePolicy(widgets.QSizePolicy.Policy.Expanding, widgets.QSizePolicy.Policy.Fixed)
        self.password_container.setSizePolicy(widgets.QSizePolicy.Policy.Expanding, widgets.QSizePolicy.Policy.Fixed)

        self.login_layout.addWidget(self.username_container)
        self.login_layout.addWidget(self.password_container)
        self.login_layout.addWidget(self.action_button)

        self.password_input.returnPressed.connect(lambda: self.action_button.clicked.emit())

    async def run_action(self):
        try:
            await utils.create_user({"username": self.username_input.text(), "password": self.password_input.text()})
            self.actionSuccess.emit(True)
        except LoginFailedToAuthorize as err:
            self.error_message = str(err)
            self.actionSuccess.emit(False)
        except ValueError as err:
            self.error_message = str(err)
            self.actionSuccess.emit(False)
        except TimeoutError as err:
            self.error_message = str(err)
            self.actionSuccess.emit(False)
        
    def reset_widget(self):
        self.password_input.clear()

class PrintWidget(widgets.QWidget):
    actionSuccess = qtcore.pyqtSignal(bool)
    error_title = ""
    error_message = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setLayout(widgets.QVBoxLayout())
        self.make_radiobuttons()
        self.make_data_input()
        self.make_printer_input()
        self.make_action_button()
        self.widget_title = "Print labels"
    
    def make_radiobuttons(self):
        self.radio_group = widgets.QWidget()
        self.radio_layout = widgets.QVBoxLayout(self.radio_group)
        self.radio_label = widgets.QLabel("Select the type of label to print:")
        self.text_radio = widgets.QRadioButton("Text")
        self.qr_radio = widgets.QRadioButton("QR")
        self.itn_radio = widgets.QRadioButton("ITN")
        self.itn_radio.setChecked(True)
        self.radio_layout.addWidget(self.radio_label)
        self.radio_layout.addWidget(self.text_radio)
        self.radio_layout.addWidget(self.qr_radio)
        self.radio_layout.addWidget(self.itn_radio)
        self.layout().addWidget(self.radio_group) # type: ignore

    def make_printer_input(self):
        self.printer_container = widgets.QWidget()
        self.printer_layout = widgets.QVBoxLayout(self.printer_container)
        self.printer_label = widgets.QLabel("Enter the printer to print to:")
        self.printer_input = widgets.QLineEdit()
        self.printer_layout.addWidget(self.printer_label)
        self.printer_layout.addWidget(self.printer_input)
        self.layout().addWidget(self.printer_container) # type: ignore

    def make_data_input(self):
        self.data_container = widgets.QWidget()
        self.data_layout = widgets.QVBoxLayout(self.data_container)
        self.data_multiple = widgets.QCheckBox("Multiple")
        self.data_multiple.setToolTip("Set this flag if you want to print to multiple printers at once.")
        self.data_label = widgets.QLabel("Enter the data to be printed:")
        self.data_input = widgets.QPlainTextEdit()

        self._set_hint_text(self.data_multiple.checkState())
        self.data_layout.addWidget(self.data_label)
        self.data_layout.addWidget(self.data_multiple)
        self.data_layout.addWidget(self.data_input)

        self.data_multiple.checkStateChanged.connect(self._set_hint_text)
        self.data_multiple.checkStateChanged.connect(self._disable_printer_input)
        self.layout().addWidget(self.data_container) # type: ignore

    def make_action_button(self):
        self.action_button = ButtonWidget("Print")
        self.action_button.setFixedHeight(30)
        self.layout().addWidget(self.action_button) # type: ignore

    def _set_hint_text(self, is_checked):
        if is_checked is qtcore.Qt.CheckState.Checked:
            hint_text = "Printer0\nText0\nText1\nPrinter1\nText2\n.\n.\n."
        else:
            hint_text = "Text0\nText1\nText2\n.\n.\n."
        self.data_input.setPlaceholderText(hint_text)
        self.data_input.update()

    def _disable_printer_input(self, is_checked):
        if is_checked is qtcore.Qt.CheckState.Checked:
            self.printer_input.setDisabled(True)
        else:
            self.printer_input.setDisabled(False)

    async def run_action(self):
        try:
            if self.qr_radio.isChecked():
                if self.data_multiple.isChecked():
                    await utils.print_qr_job(self.data_input.toPlainText().strip().split("\n"))
                else:
                    await utils.print_qr_job([self.printer_input.text().strip().upper()] + self.data_input.toPlainText().strip().split("\n"))
            elif self.text_radio.isChecked():
                if self.data_multiple.isChecked():
                    await utils.print_text_job(self.data_input.toPlainText().strip().split("\n"))
                else:
                    await utils.print_text_job([self.printer_input.text().strip().upper()] + self.data_input.toPlainText().split("\n"))
            elif self.itn_radio.isChecked():
                data = list(map(lambda d: d.upper(), self.data_input.toPlainText().strip().split("\n")))
                if self.data_multiple.isChecked():
                    await utils.print_itn_job(data)
                else:
                    await utils.print_itn_job([self.printer_input.text().strip().upper()] + data)
            self.actionSuccess.emit(True)
        except Exception as err:
            self.error_message = str(err)
            self.error_title = "Printing error"
            self.actionSuccess.emit(False)
        
    def reset_widget(self):
        self.printer_input.clear()
        self.data_input.clear()
        self.data_multiple.setChecked(False)
        self.itn_radio.setChecked(True)

class ProductionWidget(widgets.QWidget):
    actionSuccess = qtcore.pyqtSignal(bool)
    error_title = ""
    error_message = ""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setLayout(widgets.QVBoxLayout())
        self.make_datetime_input()
        self.make_department_input()
        self.make_checkboxes()
        self.make_action_button()
        self.widget_title = "Get production"

    def make_datetime_input(self):
        self.datetime_container = widgets.QWidget()
        self.datetime_layout = widgets.QHBoxLayout(self.datetime_container)
        self.start_container = widgets.QWidget()
        self.start_layout = widgets.QVBoxLayout(self.start_container)
        self.start_label = widgets.QLabel("Start:")
        self.start_input = widgets.QDateTimeEdit()
        self.start_input.setDate(qtcore.QDate.currentDate())
        self.start_input.setTime(qtcore.QTime(0, 0, 0))
        self.start_input.setCalendarPopup(True)
        self.start_layout.addWidget(self.start_label)
        self.start_layout.addWidget(self.start_input)
        self.end_container = widgets.QWidget()
        self.end_layout = widgets.QVBoxLayout(self.end_container)
        self.end_label = widgets.QLabel("End:")
        self.end_input = widgets.QDateTimeEdit()
        self.end_input.setDate(qtcore.QDate.currentDate())
        self.end_input.setTime(qtcore.QTime(23, 59, 59))
        self.end_input.setCalendarPopup(True)
        self.end_layout.addWidget(self.end_label)
        self.end_layout.addWidget(self.end_input)
        self.datetime_layout.addWidget(self.start_container)
        self.datetime_layout.addWidget(self.end_container)
        self.layout().addWidget(self.datetime_container) # type: ignore

    def make_department_input(self):
        self.input_container = widgets.QWidget()
        self.input_layout = widgets.QVBoxLayout(self.input_container)
        self.department_label = widgets.QLabel("Department:")
        self.department_input = widgets.QComboBox()
        self.input_layout.addWidget(self.department_label)
        self.input_layout.addWidget(self.department_input)

        depatment_list = [name.capitalize() for name in Department._member_names_]
        self.department_input.insertItems(0, depatment_list)

        self.layout().addWidget(self.input_container) # type: ignore

    def make_checkboxes(self):
        self.checkbox_group = widgets.QWidget()
        self.checkbox_layout = widgets.QVBoxLayout(self.checkbox_group)
        self.checkbox_label = widgets.QLabel("Select the count method:")
        self.itn_checkbox = widgets.QCheckBox("ITNs")
        self.po_checkbox = widgets.QCheckBox("POs")
        self.itn_checkbox.setChecked(True)
        self.po_checkbox.setChecked(True)
        self.checkbox_layout.addWidget(self.checkbox_label)
        self.checkbox_layout.addWidget(self.po_checkbox)
        self.checkbox_layout.addWidget(self.itn_checkbox)
        self.layout().addWidget(self.checkbox_group) # type: ignore

    def make_action_button(self):
        self.action_button = ButtonWidget("Get")
        self.action_button.setFixedHeight(30)
        self.layout().addWidget(self.action_button) # type: ignore

    async def run_action(self):
        methods = []
        dept = self.department_input.currentText()
        if self.po_checkbox.isChecked():
            methods.append(CountingMethods.BY_POS)
        if self.itn_checkbox.isChecked():
            methods.append(CountingMethods.BY_ITNS)
        try:
            await utils.get_production(methods, dept, self.start_input.dateTime().toPyDateTime(), self.end_input.dateTime().toPyDateTime()) # type: ignore
            self.actionSuccess.emit(True)
        except Exception as err:
            self.error_message = str(err)
            self.error_title = "Production error"
            self.actionSuccess.emit(False)

    def reset_widget(self):
        self.department_input.setCurrentText("Receiving")
        self.start_input.setDate(qtcore.QDate.currentDate())
        self.start_input.setTime(qtcore.QTime(0, 0, 0))
        self.end_input.setDate(qtcore.QDate.currentDate())
        self.end_input.setTime(qtcore.QTime(23, 59, 59))
        self.itn_checkbox.setChecked(True)
        self.po_checkbox.setChecked(True)

class ItnInfoWidget(widgets.QWidget):
    actionSuccess = qtcore.pyqtSignal(bool)
    error_title = ""
    error_message = ""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setLayout(widgets.QVBoxLayout())
        self.widget_title = "ITN Info"
        self.make_itn_input()
        self.make_action_button()

    def make_itn_input(self):
        self.itn_container = widgets.QWidget()
        self.itn_layout = widgets.QVBoxLayout(self.itn_container)
        self.itn_label = widgets.QLabel("ITNs:")
        self.itn_input = widgets.QPlainTextEdit()
        self.itn_layout.addWidget(self.itn_label)
        self.itn_layout.addWidget(self.itn_input)
        self.layout().addWidget(self.itn_container) # type: ignore

    def make_action_button(self):
        self.action_button = ButtonWidget("Get")
        self.action_button.setFixedHeight(30)
        self.layout().addWidget(self.action_button) # type: ignore

    def make_another_window(self):
        self.another_window = AnotherWindow(500, 400)
        self.another_window.setWindowTitle("Results")
        self.export_button = ButtonWidget("Export")
        self.result_view = widgets.QTreeWidget(self.another_window)
        self.result_view.setColumnCount(1)
        self.result_view.setHeaderLabel("ITNs")
        self.another_window.main_layout.addWidget(self.export_button) # type: ignore
        self.another_window.main_layout.addWidget(self.result_view) # type: ignore
        self.another_window.main_container.setGraphicsEffect(widgets.QGraphicsBlurEffect())
        self.another_window.main_container.graphicsEffect().setEnabled(False) # type: ignore

        self.export_button.clicked.connect(self.export_action)

    def make_message_box(self):
        self.message = ResizableMessageBox(self.another_window)
        self.message.setWindowTitle("Exported")
        self.message.setText("Complete")
        self.message.setIcon(widgets.QMessageBox.Icon.Question)
        self.message.setInformativeText("Would you like to open the file?")
        self.message.setStandardButtons(widgets.QMessageBox.StandardButton.Open | widgets.QMessageBox.StandardButton.Cancel)
        self.message.setDefaultButton(widgets.QMessageBox.StandardButton.Open)

        option_selected = self.message.exec()
        if option_selected == widgets.QMessageBox.StandardButton.Open:
            subprocess.run(["notepad", "export.txt"])
        elif option_selected == widgets.QMessageBox.StandardButton.Cancel:
            self.message.close()

    def export_action(self):
        self.another_window.loading_greyout.show_loading_frame()
        self.another_window.main_container.graphicsEffect().setEnabled(True) # type: ignore
        self.another_window.main_container.update() # type: ignore
        with open("export.txt", "w+") as file:
            for i in range(self.result_view.topLevelItemCount()):
                parent_item = self.result_view.topLevelItem(i)
                file.write(self._node_print(parent_item, 0))
                #if parent_item.childCount() > 0: # type: ignore
                #    file.write(self._node_print(parent_item, 0))
                #else:
                #    file.write(self._node_print(pre))
        self.another_window.loading_greyout.hide_loading_frame()
        self.another_window.main_container.graphicsEffect().setEnabled(False) # type: ignore
        self.another_window.main_container.update() # type: ignore
        self.make_message_box()

    def _node_print(self, item, depth):
        node_string = f'{"\t" * depth}{item.text(0)}\n'
        if item.childCount() > 0:
            depth += 1
            for i in range(item.childCount()):
                child_item = item.child(i) # type: ignore
                node_string += self._node_print(child_item, depth)
        return node_string

    async def run_action(self):
        timeouts = list(map(lambda e: e.upper(), self.itn_input.toPlainText().strip().split("\n")))
        self.make_another_window()
        try:
            for task_cycle in range(3):
                    retrieved, timeouts = await utils.get_itn_info(timeouts)
                    if retrieved:
                        for itn in retrieved:
                            self._create_tree_listitem(itn)
                    if not timeouts:
                        break
            self.another_window.show()
            self.actionSuccess.emit(True)
        except Exception as err:
            self.error_message = str(err)
            self.error_title = "ITN info error"
            self.actionSuccess.emit(False)

    def reset_widget(self):
        self.itn_input.clear()

    def _tree_widget_helper(self, data, parent_item):
        for k, v in data.items():
            if k != "itn" and k != "InventoryTrackingNumber" and k != "__typename" and v:
                temp_item = widgets.QTreeWidgetItem()
                if type(v) is dict:
                    temp_item.setText(0, k)
                    self._tree_widget_helper(v, temp_item)
                elif type(v) is list:
                    temp_item.setText(0, k)
                    for listitem in v:
                        self._tree_widget_helper(listitem, temp_item)
                else:
                    temp_item.setText(0, f"{k}: {v}")
                parent_item.addChild(temp_item)

    def _create_tree_listitem(self, itn_info):
        item = widgets.QTreeWidgetItem(self.result_view)
        try:
            item.setText(0, itn_info['data']['inventory']['itn'])
            self._tree_widget_helper(itn_info['data']['inventory'], item)
        except TypeError:
            item.setText(0, itn_info.message[:10] + " - Dead")
            item.setBackground(0, qtgui.QBrush(qtcore.Qt.GlobalColor.red))
            item.setForeground(0, qtgui.QBrush(qtcore.Qt.GlobalColor.black))
        self.result_view.addTopLevelItem(item)

class MainWindow(widgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(500)
        self.setMinimumHeight(650)
        self.setWindowIcon(qtgui.QIcon(_resource_path("ops.png")))
        self.status_bar = self.statusBar()
        self.widget_title = "OMS Operations"
        self.setWindowTitle(self.widget_title)
        self.error_popup = None

    def build_app(self):
        self.main_container = widgets.QWidget()
        self.main_layout = widgets.QVBoxLayout(self.main_container)
        self.widget_container = widgets.QStackedWidget()
        self.loading_frame = LoadingFrame(self.minimumWidth(), self.minimumHeight(), parent = self)
        self.print_container = PrintWidget()
        self.production_container = ProductionWidget()
        self.itn_container = ItnInfoWidget()
        self.login_container = LoginWidget()
        
        self.widget_container.addWidget(self.login_container)
        self.widget_container.addWidget(self.print_container)
        self.widget_container.addWidget(self.production_container)
        self.widget_container.addWidget(self.itn_container)

        self.menu_bar = ButtonMenu()
        self.menu_print_bttn = ButtonWidget("Print labels", flat = True)
        self.menu_production_bttn = ButtonWidget("Get production", flat = True)
        self.menu_itn_bttn = ButtonWidget("Get ITN info", flat = True)
        self.menu_print_bttn.clicked.connect(lambda: self.change_widget(self.print_container))
        self.menu_production_bttn.clicked.connect(lambda: self.change_widget(self.production_container))
        self.menu_itn_bttn.clicked.connect(lambda: self.change_widget(self.itn_container))
        self.menu_bar.addWidget(self.menu_print_bttn)
        self.menu_bar.addWidget(self.menu_production_bttn)
        self.menu_bar.addWidget(self.menu_itn_bttn)
        self.menu_bar.setVisible(False)

        self.main_layout.addWidget(self.menu_bar)
        self.main_layout.addWidget(self.widget_container)
        self.setCentralWidget(self.main_container)

        self.main_container.setGraphicsEffect(widgets.QGraphicsBlurEffect())
        self.main_container.graphicsEffect().setEnabled(False) # type: ignore

        self.print_container.action_button.clicked.connect(lambda: asyncio.get_running_loop().create_task(self.start_loading(self.print_container)))
        self.production_container.action_button.clicked.connect(lambda: asyncio.get_running_loop().create_task(self.start_loading(self.production_container)))
        self.itn_container.action_button.clicked.connect(lambda: asyncio.get_running_loop().create_task(self.start_loading(self.itn_container)))
        
        self.change_widget(self.login_container)
        self.login_container.action_button.clicked.connect(lambda: asyncio.get_running_loop().create_task(self.login(self.login_container)))

    def change_widget(self, widget_container):
        self.setWindowTitle(f"{self.widget_title} - {widget_container.widget_title}")
        self.widget_container.setCurrentWidget(widget_container)
    
    def show_error_popup(self, title, message):
        if not self.error_popup:
            self.error_popup = ResizableMessageBox(self)
            self.error_popup.setIcon(widgets.QMessageBox.Icon.Critical)
        
        self.error_popup.finished.connect(lambda: self.unblur_main())
        self.error_popup.setWindowTitle(title)
        self.error_popup.setText(message)
        self.error_popup.show()
    
    async def login(self, app_widget):
        app_widget.actionSuccess.connect(lambda e: self.check_login_success(e, app_widget))
        self.blur_main()
        self.loading_frame.show_loading_frame()
        await app_widget.run_action()

    def check_login_success(self, login_bool, app_widget):
        if login_bool:
            app_widget.reset_widget()
            self.unblur_main()
            self.loading_frame.hide_loading_frame()
            self.menu_print_bttn.click()
            self.menu_bar.setVisible(True)
        else:
            self.loading_frame.hide_loading_frame()
            self.show_error_popup(app_widget.error_title, app_widget.error_message)

    async def start_loading(self, app_widget):
        app_widget.actionSuccess.connect(lambda e: self.end_loading(e, app_widget))
        self.blur_main()
        self.loading_frame.show_loading_frame()
        await app_widget.run_action()

    def end_loading(self, success_bool, app_widget):
        if success_bool:
            app_widget.reset_widget()
            self.unblur_main()
            self.loading_frame.hide_loading_frame()
        else:
            self.loading_frame.hide_loading_frame()
            self.show_error_popup(app_widget.error_title, app_widget.error_message)

    def blur_main(self):
        self.main_container.graphicsEffect().setEnabled(True) # type: ignore
        self.main_container.update() # type: ignore

    def unblur_main(self):
        self.main_container.graphicsEffect().setEnabled(False) # type: ignore
        self.main_container.update() # type: ignore

    @asyncClose
    async def cleanup(self, event):
        await utils.close_session()
