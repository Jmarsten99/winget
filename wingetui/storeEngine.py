from __future__ import annotations # to fix NameError: name 'TreeWidgetItemWithQAction' is not defined
import wingetHelpers, scoopHelpers, sys, subprocess, time, os, json
from threading import Thread
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from tools import *
from tools import _

import globals

class PackageInstallerWidget(QGroupBox):
    onCancel = Signal()
    killSubprocess = Signal()
    addInfoLine = Signal(str)
    finishInstallation = Signal(int, str)
    counterSignal = Signal(int)
    callInMain = Signal(object)
    changeBarOrientation = Signal()
    def __init__(self, title: str, store: str, version: list = [], parent=None, customCommand: str = "", args: list = [], packageId="", admin: bool = False, useId: bool = False, packageItem: TreeWidgetItemWithQAction = None):
        super().__init__(parent=parent)
        self.packageItem = packageItem
        self.actionDone = _("installed")
        self.actionDoing = _("installing")
        self.actionName = _("installation")
        self.actionVerb = _("install")
        self.runAsAdmin = admin
        self.useId = useId
        self.adminstr = [sudoPath] if self.runAsAdmin else []
        self.finishedInstallation = True
        self.callInMain.connect(lambda f: f())
        self.setMinimumHeight(500)
        self.store = store.lower()
        self.customCommand = customCommand
        self.setObjectName("package")
        self.setFixedHeight(50)
        self.programName = title
        self.packageId = packageId
        self.version = version
        self.cmdline_args = args
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(30, 10, 10, 10)
        self.label = QLabel(_("{0} installation").format(title))
        self.layout.addWidget(self.label)
        self.layout.addSpacing(5)
        self.progressbar = QProgressBar()
        self.progressbar.setTextVisible(False)
        self.progressbar.setRange(0, 1000)
        self.progressbar.setValue(0)
        self.progressbar.setFixedHeight(4)
        self.changeBarOrientation.connect(lambda: self.progressbar.setInvertedAppearance(not(self.progressbar.invertedAppearance())))
        self.layout.addWidget(self.progressbar, stretch=1)
        self.info = QLineEdit()
        self.info.setStyleSheet("color: grey; border-bottom: inherit;")
        self.info.setText(_("Waiting for other installations to finish..."))
        self.info.setReadOnly(True)
        self.addInfoLine.connect(lambda text: self.info.setText(text))
        self.finishInstallation.connect(self.finish)
        self.layout.addWidget(self.info)
        self.counterSignal.connect(self.counter)
        self.cancelButton = QPushButton(QIcon(realpath+"/resources/cancel.png"), _("Cancel"))
        self.cancelButton.clicked.connect(self.cancel)
        self.cancelButton.setFixedHeight(30)
        self.info.setFixedHeight(30)
        self.layout.addWidget(self.cancelButton)
        self.setLayout(self.layout)
        self.canceled = False
        self.installId = str(time.time())
        queueProgram(self.installId)
        
        self.leftSlow = QVariantAnimation()
        self.leftSlow.setStartValue(0)
        self.leftSlow.setEndValue(1000)
        self.leftSlow.setDuration(900)
        self.leftSlow.valueChanged.connect(lambda v: self.progressbar.setValue(v))
        self.leftSlow.finished.connect(lambda: (self.rightSlow.start(), self.changeBarOrientation.emit()))
        
        self.rightSlow = QVariantAnimation()
        self.rightSlow.setStartValue(1000)
        self.rightSlow.setEndValue(0)
        self.rightSlow.setDuration(900)
        self.rightSlow.valueChanged.connect(lambda v: self.progressbar.setValue(v))
        self.rightSlow.finished.connect(lambda: (self.leftFast.start(), self.changeBarOrientation.emit()))
        
        self.leftFast = QVariantAnimation()
        self.leftFast.setStartValue(0)
        self.leftFast.setEndValue(1000)
        self.leftFast.setDuration(300)
        self.leftFast.valueChanged.connect(lambda v: self.progressbar.setValue(v))
        self.leftFast.finished.connect(lambda: (self.rightFast.start(), self.changeBarOrientation.emit()))

        self.rightFast = QVariantAnimation()
        self.rightFast.setStartValue(1000)
        self.rightFast.setEndValue(0)
        self.rightFast.setDuration(300)
        self.rightFast.valueChanged.connect(lambda v: self.progressbar.setValue(v))
        self.rightFast.finished.connect(lambda: (self.leftSlow.start(), self.changeBarOrientation.emit()))
        
        self.leftSlow.start()

        self.waitThread = KillableThread(target=self.startInstallation, daemon=True)
        self.waitThread.start()
        print(f"🟢 Waiting for install permission... title={self.programName}, id={self.packageId}, installId={self.installId}")
        
    def startInstallation(self) -> None:
        while self.installId != globals.current_program and not getSettings("AllowParallelInstalls"):
            time.sleep(0.2)
        print("🟢 Have permission to install, starting installation threads...")
        self.callInMain.emit(self.runInstallation)

    def runInstallation(self) -> None:
        self.finishedInstallation = False
        self.leftSlow.stop()
        self.leftFast.stop()
        self.rightSlow.stop()
        self.rightFast.stop()
        self.addInfoLine.emit(_("Starting installation..."))
        self.progressbar.setValue(0)
        self.packageId = self.packageId.replace("…", "")
        self.programName = self.programName.replace("…", "")
        if self.progressbar.invertedAppearance(): self.progressbar.setInvertedAppearance(False)
        if(self.store.lower() == "winget"):
            if self.useId:
                self.p = subprocess.Popen(self.adminstr + [wingetHelpers.winget, "install", "-e", "--id", f"{self.packageId}"] + self.version + wingetHelpers.common_params + self.cmdline_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            else:
                self.p = subprocess.Popen(self.adminstr + [wingetHelpers.winget, "install", "-e", "--name", f"{self.programName}"] + self.version + wingetHelpers.common_params + self.cmdline_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            print(self.p.args)
            self.t = KillableThread(target=wingetHelpers.installAssistant, args=(self.p, self.finishInstallation, self.addInfoLine, self.counterSignal))
            self.t.start()
        elif("scoop" in self.store.lower()):
            self.p = subprocess.Popen(' '.join(self.adminstr + ["powershell", "-Command", "scoop", "install", f"{self.programName}"] + self.cmdline_args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            self.t = KillableThread(target=scoopHelpers.installAssistant, args=(self.p, self.finishInstallation, self.addInfoLine, self.counterSignal))
            self.t.start()
        else:
            self.p = subprocess.Popen(self.customCommand, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            self.t = KillableThread(target=genericInstallAssistant, args=(self.p, self.finishInstallation, self.addInfoLine, self.counterSignal))
            self.t.start()

    def counter(self, line: int) -> None:
        if(line == 1):
            self.progressbar.setValue(250)
        if(line == 4):
            self.progressbar.setValue(500)
        elif(line == 6):
            self.cancelButton.setEnabled(False)
            self.progressbar.setValue(750)

    def cancel(self):
        self.leftSlow.stop()
        self.leftFast.stop()
        self.rightSlow.stop()
        self.rightFast.stop()
        print("🔵 Sending cancel signal...")
        if not self.finishedInstallation:
            subprocess.Popen("taskkill /im winget.exe /f", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=os.getcwd(), env=os.environ).wait()
            self.finishedInstallation = True
        self.info.setText(_("Installation canceled by user!"))
        self.cancelButton.setEnabled(True)
        self.cancelButton.setText(_("Close"))
        self.cancelButton.setIcon(QIcon(realpath+"/resources/warn.png"))
        self.cancelButton.clicked.connect(self.close)
        self.onCancel.emit()
        self.progressbar.setValue(1000)
        self.canceled=True
        removeProgram(self.installId)
        try: self.waitThread.kill()
        except: pass
        try: self.t.kill()
        except: pass
        try: self.p.kill()
        except: pass
    
    def finish(self, returncode: int, output: str = "") -> None:
        self.finishedInstallation = True
        self.cancelButton.setEnabled(True)
        removeProgram(self.installId)
        try: self.waitThread.kill()
        except: pass
        try: self.t.kill()
        except: pass
        try: self.p.kill()
        except: pass
        if not(self.canceled):
            if(returncode == 0):
                self.callInMain.emit(lambda: globals.trayIcon.showMessage(_("{0} succeeded").format(self.actionName.capitalize()), _("{0} was {1} successfully!").format(self.programName, self.actionDone), QIcon(getMedia("notif_info"))))
                self.cancelButton.setText("OK")
                self.cancelButton.setIcon(QIcon(realpath+"/resources/tick.png"))
                self.cancelButton.clicked.connect(self.close)
                self.info.setText(_("{0} was {1} successfully!").format(self.programName, self.actionDone))
                self.progressbar.setValue(1000)
                if type(self) == PackageInstallerWidget:
                    if self.packageItem:
                        globals.uninstall.addItem(self.packageItem.text(0), self.packageItem.text(1), self.packageItem.text(2), self.packageItem.text(3)) # Add the package on the uninstaller
                self.startCoolDown()
            else:
                globals.trayIcon.setIcon(QIcon(getMedia("yellowicon"))) 
                self.cancelButton.setText(_("OK"))
                self.cancelButton.setIcon(QIcon(realpath+"/resources/warn.png"))
                self.cancelButton.clicked.connect(self.close)
                self.progressbar.setValue(1000)
                self.err = ErrorMessage(self.window())
                if(returncode == 2):  # if the installer's hash does not coincide
                    errorData = {
                        "titlebarTitle": f"WingetUI - {self.programName} {self.actionName}",
                        "mainTitle": _("{0} aborted").format(self.actionName.capitalize()),
                        "mainText": _("The checksum of the installer does not coincide with the expected value, and the authenticity of the installer can't be verified. If you trust the publisher, {0} the package again skipping the hash check.").format(self.actionVerb),
                        "buttonTitle": _("Close"),
                        "errorDetails": output.replace("-\|/", "").replace("▒", "").replace("█", ""),
                        "icon": QIcon(getMedia("warn")),
                        "notifTitle": _("Can't {0} {1}").format(self.actionVerb, self.programName),
                        "notifText": _("The installer has an invalid checksum"),
                        "notifIcon": QIcon(getMedia("notif_warn")),
                    }
                else: # if there's a generic error
                    errorData = {
                        "titlebarTitle": _("WingetUI - {0} {1}").format(self.programName, self.actionName),
                        "mainTitle": _("{0} failed").format(self.actionName.capitalize()),
                        "mainText": _("We could not {0} {1}. Please try again later. Click on \"Show details\" to get the logs from the installer.").format(self.actionVerb, self.programName),
                        "buttonTitle": _("Close"),
                        "errorDetails": output.replace("-\|/", "").replace("▒", "").replace("█", ""),
                        "icon": QIcon(getMedia("warn")),
                        "notifTitle": _("Can't {0} {1}").format(self.actionVerb, self.programName),
                        "notifText": _("{0} {1} failed").format(self.programName.capitalize(), self.actionName),
                        "notifIcon": QIcon(getMedia("notif_warn")),
                    }
                self.err.showErrorMessage(errorData)

    def startCoolDown(self):
        op1=QGraphicsOpacityEffect(self)
        op2=QGraphicsOpacityEffect(self)
        op3=QGraphicsOpacityEffect(self)
        op4=QGraphicsOpacityEffect(self)
        ops = [op1, op2, op3, op4]
        def updateOp(v: float):
            i = 0
            for widget in [self.cancelButton, self.label, self.progressbar, self.info]:
                ops[i].setOpacity(v)
                widget: QWidget
                widget.setGraphicsEffect(ops[i])
                widget.setAutoFillBackground(True)
                i += 1
        updateOp(1)
        a = QVariantAnimation(self)
        a.setStartValue(1.0)
        a.setEndValue(0.0)
        a.setEasingCurve(QEasingCurve.Linear)
        a.setDuration(300)
        a.valueChanged.connect(lambda v: updateOp(v))
        a.finished.connect(self.heightAnim)
        f = lambda: (time.sleep(3), self.callInMain.emit(a.start))
        Thread(target=f, daemon=True).start()

    def heightAnim(self):
        a = QVariantAnimation(self)
        a.setStartValue(self.height())
        a.setEndValue(0)
        a.setEasingCurve(QEasingCurve.InOutCubic)
        a.setDuration(300)
        a.valueChanged.connect(lambda v: self.setFixedHeight(v))
        a.finished.connect(self.close)
        a.start()
        
    def close(self):
        globals.installersWidget.removeItem(self)
        super().close()
        super().destroy()

class PackageUpdaterWidget(PackageInstallerWidget):

    def __init__(self, title: str, store: str, version: list = [], parent=None, customCommand: str = "", args: list = [], packageId="", packageItem: TreeWidgetItemWithQAction = None, admin: bool = False, useId: bool = False):
        super().__init__(title, store, version, parent, customCommand, args, packageId, admin, useId)
        self.packageItem = packageItem
        self.actionDone = _("updated")
        self.actionDoing = _("updating")
        self.actionName = _("update(noun)")
        self.actionVerb = _("update(verb)")
    
    def startInstallation(self) -> None:
        while self.installId != globals.current_program and not getSettings("AllowParallelInstalls"):
            time.sleep(0.2)
        print("🟢 Have permission to install, starting installation threads...")
        self.callInMain.emit(self.runInstallation)

    def runInstallation(self) -> None:
        self.finishedInstallation = False
        self.leftSlow.stop()
        self.leftFast.stop()
        self.rightSlow.stop()
        self.addInfoLine.emit(_("Applying update..."))
        self.rightFast.stop()
        self.progressbar.setValue(0)
        self.packageId = self.packageId.replace("…", "")
        self.programName = self.programName.replace("…", "")
        if self.progressbar.invertedAppearance(): self.progressbar.setInvertedAppearance(False)
        if(self.store.lower() == "winget"):
            print(self.adminstr)
            if self.useId:
                self.p = subprocess.Popen(self.adminstr + [wingetHelpers.winget, "install", "-e", "--id", f"{self.packageId}"] + self.version + wingetHelpers.common_params + self.cmdline_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            else:
                self.p = subprocess.Popen(self.adminstr + [wingetHelpers.winget, "install", "-e", "--name", f"{self.programName}"] + self.version + wingetHelpers.common_params + self.cmdline_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            print(self.p.args)
            self.t = KillableThread(target=wingetHelpers.installAssistant, args=(self.p, self.finishInstallation, self.addInfoLine, self.counterSignal))
            self.t.start()
        elif("scoop" in self.store.lower()):
            self.p = subprocess.Popen(' '.join(self.adminstr + ["powershell", "-Command", "scoop", "update", f"{self.programName}"] + self.cmdline_args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            self.t = KillableThread(target=scoopHelpers.installAssistant, args=(self.p, self.finishInstallation, self.addInfoLine, self.counterSignal))
            self.t.start()
        else:
            self.p = subprocess.Popen(self.customCommand, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            self.t = KillableThread(target=genericInstallAssistant, args=(self.p, self.finishInstallation, self.addInfoLine, self.counterSignal))
            self.t.start()

    def finish(self, returncode: int, output: str = "") -> None:
        print(returncode)
        if returncode == 0 and not self.canceled:
            if self.packageItem:
                try:
                    self.packageItem.setHidden(True)
                    i = self.packageItem.treeWidget().takeTopLevelItem(self.packageItem.treeWidget().indexOfTopLevelItem(self.packageItem))
                    del i
                except Exception as e:
                    report(e)
                globals.updates.updatePackageNumber()
        super().finish(returncode, output)
    
    def close(self):
        globals.installersWidget.removeItem(self)
        super().destroy()
        super().close()

class PackageUninstallerWidget(PackageInstallerWidget):
    onCancel = Signal()
    killSubprocess = Signal()
    addInfoLine = Signal(str)
    finishInstallation = Signal(int, str)
    counterSignal = Signal(int)
    changeBarOrientation = Signal()
    def __init__(self, title: str, store: str, useId=False, packageId = "", packageItem: TreeWidgetItemWithQAction = None, admin: bool = False, removeData: bool = False, args: list = [], customCommand: list = []):
        self.packageItem = packageItem
        self.useId = useId
        self.programName = title
        self.packageId = packageId
        super().__init__(parent=None, title=title, store=store, packageId=packageId, admin=admin, args=args, packageItem=packageItem, customCommand=customCommand)
        self.actionDone = _("uninstalled")
        self.removeData = removeData
        self.actionDoing = _("uninstalling")
        self.actionName = _("uninstallation")
        self.actionVerb = _("uninstall")
        self.finishedInstallation = True
        self.runAsAdmin = admin
        self.adminstr = [sudoPath] if self.runAsAdmin else []
        self.store = store.lower()
        self.setStyleSheet("QGroupBox{padding-top:15px; margin-top:-15px; border: none}")
        self.setFixedHeight(50)
        self.label.setText(_("{} Uninstallation").format(title))
        
    def startInstallation(self) -> None:
        while self.installId != globals.current_program and not getSettings("AllowParallelInstalls"):
            time.sleep(0.2)
        print("🟢 Have permission to install, starting installation threads...")
        self.callInMain.emit(self.runInstallation)

    def runInstallation(self) -> None:
        self.leftSlow.stop()
        self.leftFast.stop()
        self.rightSlow.stop()
        self.rightFast.stop()
        self.packageId = self.packageId.replace("…", "")
        self.programName = self.programName.replace("…", "")
        self.progressbar.setValue(0)
        if self.progressbar.invertedAppearance(): self.progressbar.setInvertedAppearance(False)
        self.finishedInstallation = False
        if(self.store == "winget" or self.store.lower() == "local pc"):
            self.p = subprocess.Popen(self.adminstr + [wingetHelpers.winget, "uninstall", "-e"] + (["--id", self.packageId] if self.useId else ["--name", self.programName]) + wingetHelpers.common_params + self.cmdline_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            self.t = KillableThread(target=wingetHelpers.uninstallAssistant, args=(self.p, self.finishInstallation, self.addInfoLine, self.counterSignal))
            self.t.start()
            print(self.p.args)
        elif("scoop" in self.store):
            self.p = subprocess.Popen(' '.join(self.adminstr + ["powershell", "-Command", "scoop", "uninstall", f"{self.programName}"] + (["-p"] if self.removeData else [""])), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            self.t = KillableThread(target=scoopHelpers.uninstallAssistant, args=(self.p, self.finishInstallation, self.addInfoLine, self.counterSignal))
            self.t.start()
        else:
            self.p = subprocess.Popen(self.customCommand, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=sudoLocation, env=os.environ)
            self.t = KillableThread(target=genericInstallAssistant, args=(self.p, self.finishInstallation, self.addInfoLine, self.counterSignal))
            self.t.start()


    
    def counter(self, line: int) -> None:
        if(line == 1):
            self.progressbar.setValue(250)
        if(line == 4):
            self.progressbar.setValue(500)
        elif(line == 6):
            self.cancelButton.setEnabled(False)
            self.progressbar.setValue(750)

    def cancel(self):
        print("🔵 Sending cancel signal...")
        self.leftSlow.stop()
        self.leftFast.stop()
        self.rightSlow.stop()
        self.rightFast.stop()
        self.info.setText(_("Uninstall canceled by user!"))
        if not self.finishedInstallation:
            subprocess.Popen("taskkill /im winget.exe /f", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE, shell=True, cwd=os.getcwd(), env=os.environ).wait()
            self.finishedInstallation = True
        self.cancelButton.setEnabled(True)
        self.cancelButton.setText(_("Close"))
        self.cancelButton.setIcon(QIcon(realpath+"/resources/warn.png"))
        self.cancelButton.clicked.connect(self.close)
        self.onCancel.emit()
        self.progressbar.setValue(1000)
        self.canceled=True
        removeProgram(self.installId)
        try: self.waitThread.kill()
        except: pass
        try: self.t.kill()
        except: pass
        try: self.p.kill()
        except: pass
        
    def finish(self, returncode: int, output: str = "") -> None:
        if returncode == 0 and not self.canceled:
            if self.packageItem:
                try:
                    self.packageItem.setHidden(True)
                    i = self.packageItem.treeWidget().takeTopLevelItem(self.packageItem.treeWidget().indexOfTopLevelItem(self.packageItem))
                    del i
                except Exception as e:
                    report(e)
        self.finishedInstallation = True
        self.cancelButton.setEnabled(True)
        removeProgram(self.installId)
        try: self.waitThread.kill()
        except: pass
        try: self.t.kill()
        except: pass
        try: self.p.kill()
        except: pass
        if not(self.canceled):
            if(returncode == 0):
                self.callInMain.emit(lambda: globals.trayIcon.showMessage(_("{0} succeeded").format(self.actionName.capitalize()), _("{0} was {1} successfully!").format(self.programName, self.actionDone), QIcon(getMedia("notif_info"))))
                self.cancelButton.setText(_("OK"))
                self.cancelButton.setIcon(QIcon(realpath+"/resources/tick.png"))
                self.cancelButton.clicked.connect(self.close)
                self.info.setText(f"{self.programName} was uninstalled successfully!")
                self.progressbar.setValue(1000)
                self.startCoolDown()
            else:
                globals.trayIcon.setIcon(QIcon(getMedia("yellowicon"))) 
                self.cancelButton.setText(_("OK"))
                self.cancelButton.setIcon(QIcon(realpath+"/resources/warn.png"))
                self.cancelButton.clicked.connect(self.close)
                self.progressbar.setValue(1000)
                self.err = ErrorMessage(self.window())
                errorData = {
                    "titlebarTitle": _("WingetUI - {0} {1}").format(self.programName, self.actionName),
                    "mainTitle": _("{0} failed").format(self.actionName.capitalize()),
                    "mainText": _("We could not {0} {1}. Please try again later. Click on \"Show details\" to get the logs from the uninstaller.").format(self.actionVerb, self.programName),
                    "buttonTitle": _("Close"),
                    "errorDetails": output.replace("-\|/", "").replace("▒", "").replace("█", ""),
                    "icon": QIcon(getMedia("warn")),
                    "notifTitle": _("Can't {0} {1}").format(self.actionVerb, self.programName),
                    "notifText": _("{0} {1} failed").format(self.programName.capitalize(), self.actionName),
                    "notifIcon": QIcon(getMedia("notif_warn")),
                    }
                self.err.showErrorMessage(errorData)
    
    def close(self):
        globals.installersWidget.removeItem(self)
        super().close()
        super().destroy()

class PackageInfoPopupWindow(QMainWindow):
    onClose = Signal()
    loadInfo = Signal(dict)
    closeDialog = Signal()
    addProgram = Signal(PackageInstallerWidget)
    setLoadBarValue = Signal(str)
    startAnim = Signal(QVariantAnimation)
    changeBarOrientation = Signal()
    packageItem: TreeWidgetItemWithQAction = None
    finishedCount: int = 0
    
    pressed = False
    oldPos = QPoint(0, 0)

    def __init__(self, parent = None):
        super().__init__(parent = parent)
        self.sc = QScrollArea()
        self.setWindowFlags(Qt.Window)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlag(Qt.Tool)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.store = ""
        self.sct = QShortcut(QKeySequence("Esc"), self)
        self.sct.activated.connect(lambda: self.close())
        self.sc.setWidgetResizable(True)
        self.setStyleSheet("""
        QScrollArea{
            border-radius: 5px;
            padding: 5px;
        }
        """)
        self.loadingProgressBar = QProgressBar(self)
        self.loadingProgressBar.setRange(0, 1000)
        self.loadingProgressBar.setValue(0)
        self.loadingProgressBar.setFixedHeight(4)
        self.loadingProgressBar.setTextVisible(False)
        self.setLoadBarValue.connect(self.loadingProgressBar.setValue)
        self.startAnim.connect(lambda anim: anim.start())
        self.changeBarOrientation.connect(lambda: self.loadingProgressBar.setInvertedAppearance(not(self.loadingProgressBar.invertedAppearance())))
        
        self.vLayout = QVBoxLayout()
        self.layout = QVBoxLayout()
        self.title = QLinkLabel()
        self.title.setStyleSheet("font-size: 30pt;font-family: \"Segoe UI Variable Display\";font-weight: bold;")
        self.title.setText(_("Loading..."))

        fortyWidget = QWidget()
        fortyWidget.setFixedWidth(120)

        fortyTopWidget = QWidget()
        fortyTopWidget.setFixedWidth(120)
        fortyTopWidget.setMinimumHeight(30)

        self.mainGroupBox = QGroupBox()

        self.layout.addWidget(self.title)
        self.layout.addStretch()

        self.hLayout = QHBoxLayout()
        self.oLayout = QHBoxLayout()
        self.description = QLinkLabel(_('Description:')+" "+_('Unknown'))
        self.description.setWordWrap(True)

        self.layout.addWidget(self.description)

        self.homepage = QLinkLabel(_('Homepage URL:')+" "+_('Unknown'))
        self.homepage.setWordWrap(True)

        self.layout.addWidget(self.homepage)

        self.publisher = QLinkLabel(_('Publisher:')+" "+_('Unknown'))
        self.publisher.setWordWrap(True)

        self.layout.addWidget(self.publisher)

        self.author = QLinkLabel(_('Author:')+" "+_('Unknown'))
        self.author.setWordWrap(True)

        self.layout.addWidget(self.author)
        self.layout.addStretch()

        self.license = QLinkLabel(_('License:')+" "+_('Unknown'))
        self.license.setWordWrap(True)

        self.layout.addWidget(self.license)
        self.layout.addStretch()
        
        hLayout = QHBoxLayout()
        self.versionLabel = QLinkLabel(_("Version:"))

        
        self.versionCombo = CustomComboBox()
        self.versionCombo.setFixedWidth(150)
        self.versionCombo.setIconSize(QSize(24, 24))
        self.versionCombo.setFixedHeight(35)
        self.installButton = QPushButton()
        self.installButton.setText(_("Install"))
        self.installButton.setObjectName("AccentButton")
        self.installButton.setIconSize(QSize(24, 24))
        self.installButton.clicked.connect(self.install)
        self.installButton.setFixedWidth(150)
        self.installButton.setFixedHeight(30)

        downloadGroupBox = QGroupBox()
        downloadGroupBox.setMinimumHeight(100)
        optionsGroupBox = QGroupBox()

        self.forceCheckbox = QCheckBox()
        self.forceCheckbox.setText(_("Skip hash check"))
        self.forceCheckbox.setChecked(False)
        
        self.interactiveCheckbox = QCheckBox()
        self.interactiveCheckbox.setText(_("Interactive installation"))
        self.interactiveCheckbox.setChecked(False)
        
        self.adminCheckbox = QCheckBox()
        self.adminCheckbox.setText(_("Run as admin"))
        self.adminCheckbox.setChecked(False)

        self.oLayout.addStretch()
        self.oLayout.addWidget(self.forceCheckbox)
        self.oLayout.addWidget(self.interactiveCheckbox)
        self.oLayout.addWidget(self.adminCheckbox)
        self.oLayout.addStretch()

        hLayout.addWidget(self.versionLabel)
        hLayout.addWidget(self.versionCombo)
        hLayout.addWidget(QWidget(), stretch=1)
        hLayout.addWidget(self.installButton)

        vl = QVBoxLayout()
        vl.addStretch()
        vl.addLayout(hLayout)
        vl.addLayout(self.oLayout)
        vl.addStretch()

        downloadGroupBox.setLayout(vl)
        self.layout.addWidget(downloadGroupBox)
        self.layout.addStretch()


        self.packageId = QLinkLabel(_('Program ID:')+" "+_('Unknown'))
        self.packageId.setWordWrap(True)
        self.layout.addWidget(self.packageId)
        self.manifest = QLinkLabel(_('Manifest:')+" "+_('Unknown'))
        self.manifest.setWordWrap(True)
        self.layout.addWidget(self.manifest)
        self.lastver = QLinkLabel(_('Latest version:')+" "+_('Unknown'))
        self.lastver.setWordWrap(True)
        self.layout.addWidget(self.lastver)
        self.sha = QLinkLabel(_('Installer SHA256 (Latest version):')+" "+_('Unknown'))
        self.sha.setWordWrap(True)
        self.layout.addWidget(self.sha)
        self.link = QLinkLabel(_('Installer URL (Latest version):')+" "+_('Unknown'))
        self.link.setWordWrap(True)
        self.layout.addWidget(self.link)
        self.type = QLinkLabel(_('Installer type (Latest version):')+" "+_('Unknown'))
        self.type.setWordWrap(True)
        self.layout.addWidget(self.type)
        self.storeLabel = QLinkLabel(f"Source: {self.store}")
        self.storeLabel.setWordWrap(True)
        self.layout.addWidget(self.storeLabel)
        self.layout.addStretch()
        self.advert = QLinkLabel(_("DISCLAIMER: NEITHER MICROSOFT NOR THE CREATORS OF WINGETUI ARE RESPONSIBLE FOR THE DOWNLOADED APP."))
        self.advert.setWordWrap(True)
        self.layout.addWidget(self.advert)

        self.mainGroupBox.setLayout(self.layout)
        self.mainGroupBox.setMinimumHeight(480)
        self.vLayout.addWidget(self.mainGroupBox)
        self.hLayout.addLayout(self.vLayout, stretch=0)

        self.centralwidget = QWidget()
        self.centralwidget.setLayout(self.hLayout)
        if(isDark()):
            print("🔵 Is Dark")
        self.sc.setWidget(self.centralwidget)
        self.setCentralWidget(self.sc)


        self.backButton = QPushButton(QIcon(getMedia("close")), "", self)
        self.backButton.setStyleSheet("font-size: 22px;")
        self.setStyleSheet("margin: 0px;")
        self.backButton.move(self.width()-40, 0)
        self.backButton.resize(40, 40)
        self.backButton.setFlat(True)
        self.backButton.setStyleSheet("QPushButton{border: none;border-radius:0px;background:transparent}QPushButton:hover{background-color:red;}")
        self.backButton.clicked.connect(lambda: (self.onClose.emit(), self.close()))
        self.backButton.show()

        self.hide()

        self.loadInfo.connect(self.printData)

        
        self.leftSlow = QVariantAnimation()
        self.leftSlow.setStartValue(0)
        self.leftSlow.setEndValue(1000)
        self.leftSlow.setDuration(700)
        self.leftSlow.valueChanged.connect(lambda v: self.loadingProgressBar.setValue(v))
        self.leftSlow.finished.connect(lambda: (self.rightSlow.start(), self.changeBarOrientation.emit()))
        
        self.rightSlow = QVariantAnimation()
        self.rightSlow.setStartValue(1000)
        self.rightSlow.setEndValue(0)
        self.rightSlow.setDuration(700)
        self.rightSlow.valueChanged.connect(lambda v: self.loadingProgressBar.setValue(v))
        self.rightSlow.finished.connect(lambda: (self.leftFast.start(), self.changeBarOrientation.emit()))
        
        self.leftFast = QVariantAnimation()
        self.leftFast.setStartValue(0)
        self.leftFast.setEndValue(1000)
        self.leftFast.setDuration(300)
        self.leftFast.valueChanged.connect(lambda v: self.loadingProgressBar.setValue(v))
        self.leftFast.finished.connect(lambda: (self.rightFast.start(), self.changeBarOrientation.emit()))

        self.rightFast = QVariantAnimation()
        self.rightFast.setStartValue(1000)
        self.rightFast.setEndValue(0)
        self.rightFast.setDuration(300)
        self.rightFast.valueChanged.connect(lambda v: self.loadingProgressBar.setValue(v))
        self.rightFast.finished.connect(lambda: (self.leftSlow.start(), self.changeBarOrientation.emit()))
        
        self.leftSlow.start()
    
    def resizeEvent(self, event = None):
        self.centralwidget.setFixedWidth(self.width()-18)
        g = self.mainGroupBox.geometry()
        self.loadingProgressBar.move(0, 0)
        self.loadingProgressBar.resize(self.width(), 4)
        self.backButton.move(self.width()-40, 0)
        if(event):
            return super().resizeEvent(event)
    
    def loadProgram(self, title: str, id: str, useId: bool, store: str, update: bool = False, packageItem: TreeWidgetItemWithQAction = None) -> None:
        self.packageItem = packageItem
        self.store = store
        self.installButton.setEnabled(False)
        self.versionCombo.setEnabled(False)
        self.isAnUpdate = update
        self.installButton.setText(_("Please wait..."))
        store = store.lower()
        self.title.setText(title)
            
        self.loadingProgressBar.show()
        self.forceCheckbox.setChecked(False)
        self.forceCheckbox.setEnabled(False)
        self.interactiveCheckbox.setChecked(False)
        self.interactiveCheckbox.setEnabled(False)
        self.adminCheckbox.setChecked(False)
        self.adminCheckbox.setEnabled(False)
        self.description.setText(_("Loading..."))
        self.author.setText(_("Author")+": "+_("Loading..."))
        self.publisher.setText(f"{_('Publisher')}: "+_("Loading..."))
        self.homepage.setText(f"{_('Homepage')}: <a style=\"color: {blueColor};\"  href=\"\">{_('Loading...')}</a>")
        self.license.setText(f"{_('License')}: {_('Loading...')} (<a style=\"color: {blueColor};\" href=\"\">{_('Loading...')}</a>)")
        self.lastver.setText(f"{_('Latest version')}: {_('Loading...')}")
        self.sha.setText(f"{_('Installer SHA256')} ({_('Latest version')}): {_('Loading...')}")
        self.link.setText(f"{_('Installer URL')} ({_('Latest version')}): <a  style=\"color: {blueColor};\" href=\"\">{_('Loading...')}</a>")
        self.type.setText(f"{_('Installer type')} ({_('Latest version')}): {_('Loading...')}")
        self.packageId.setText(f"{_('Package ID')}: {_('Loading...')}")
        self.manifest.setText(f"{_('Manifest')}: {_('Loading...')}")
        self.storeLabel.setText(f"{_('Source')}: {self.store.capitalize()}")
        self.versionCombo.addItems([_("Loading...")])
        
        self.finishedCount = 0
        if(store.lower()=="winget"):
            Thread(target=wingetHelpers.getInfo, args=(self.loadInfo, title, id, useId), daemon=True).start()
        elif("scoop" in store.lower()):
            Thread(target=scoopHelpers.getInfo, args=(self.loadInfo, title, id, useId), daemon=True).start()

    def printData(self, appInfo: dict) -> None:
        self.finishedCount += 1
        if not("scoop" in self.store.lower()) or self.finishedCount > 1:
            self.loadingProgressBar.hide()
        if self.isAnUpdate:
            self.installButton.setText(_("Update"))
        else:
            self.installButton.setText(_("Install"))
        self.installButton.setEnabled(True)
        self.versionCombo.setEnabled(True)
        self.adminCheckbox.setEnabled(True)
        self.forceCheckbox.setEnabled(True)
        if(self.store.lower() == "winget"):
            self.interactiveCheckbox.setEnabled(True)
        self.title.setText(appInfo["title"])
        self.description.setText(appInfo["description"])
        self.author.setText(f"{_('Author')}: "+appInfo["author"])
        self.publisher.setText(f"{_('Publisher')}: "+appInfo["publisher"])
        self.homepage.setText(f"{_('Homepage')}: <a style=\"color: {blueColor};\"  href=\"{appInfo['homepage']}\">{appInfo['homepage']}</a>")
        self.license.setText(f"{_('License')}: {appInfo['license']} (<a style=\"color: {blueColor};\" href=\"{appInfo['license-url']}\">{appInfo['license-url']}</a>)")
        try:
            self.lastver.setText(f"{_('Latest version')}: {appInfo['versions'][0]}")
        except IndexError:
            self.lastver.setText(_('Latest version:')+" "+_('Unknown'))
        self.sha.setText(f"{_('Installer SHA256')} ({_('Latest version')}): {appInfo['installer-sha256']}")
        self.link.setText(f"{_('Installer URL')} ({_('Latest version')}): <a style=\"color: {blueColor};\" href=\"{appInfo['installer-url']}\">{appInfo['installer-url']}</a>")
        self.type.setText(f"{_('Installer type')} ({_('Latest version')}): {appInfo['installer-type']}")
        self.packageId.setText(f"{_('Package ID')}: {appInfo['id']}")
        self.manifest.setText(f"{_('Manifest')}: <a style=\"color: {blueColor};\" href=\"file:///"+appInfo['manifest'].replace('\\', '/')+f"\">{appInfo['manifest']}</a>")
        while self.versionCombo.count()>0:
            self.versionCombo.removeItem(0)
        try:
            self.versionCombo.addItems(["Latest"] + appInfo["versions"])
        except KeyError:
            pass

    def install(self):
        title = self.title.text()
        packageId = self.packageId.text().replace(_('Package ID')+":", '').strip()
        print(f"🟢 Starting installation of package {title} with id {packageId}")
        cmdline_args = []
        if(self.forceCheckbox.isChecked()):
            if self.store.lower() == "winget":
                cmdline_args.append("--force")
            elif self.store.lower() == "scoop":
                cmdline_args.append("--skip")
        if(self.interactiveCheckbox.isChecked()):
            cmdline_args.append("--interactive")
        else:
            if not "scoop" in self.store.lower():
                cmdline_args.append("--silent")
        if(self.versionCombo.currentText()==_("Latest") or self.versionCombo.currentText() == "Latest"):
            version = []
        else:
            version = ["--version", self.versionCombo.currentText()]
            print(f"🟡 Issuing specific version {self.versionCombo.currentText()}")
        if self.isAnUpdate:
            p = PackageUpdaterWidget(title, self.store, version, args=cmdline_args, packageId=packageId, admin=self.adminCheckbox.isChecked(), packageItem=self.packageItem, useId=not("…" in packageId))
        else:
            p = PackageInstallerWidget(title, self.store, version, args=cmdline_args, packageId=packageId, admin=self.adminCheckbox.isChecked(), packageItem=self.packageItem, useId=not("…" in packageId))
        self.addProgram.emit(p)
        self.close()

    def show(self) -> None:
        g: QRect = self.parent().window().geometry()
        self.resize(700, 650)
        self.parent().window().blackmatt.show()
        self.move(g.x()+g.width()//2-700//2, g.y()+g.height()//2-650//2)
        print(g.x()+g.width()//2-700//2, g.y()+g.height()//2-650//2)
        return super().show()

    def close(self) -> bool:
        self.parent().window().blackmatt.hide()
        return super().close()

    def hide(self) -> None:
        try:
            self.parent().window().blackmatt.hide()
        except AttributeError:
            pass
        return super().hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.pressed = True
        self.oldPos = event.pos()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.pressed:
            try:
                if not globals.mainWindow.isMaximized() and not globals.mainWindow.isMinimized():
                    globals.mainWindow.move(globals.mainWindow.pos()+(event.pos()-self.oldPos))
            except AttributeError as e:
                report(e)
            self.move(self.pos()+(event.pos()-self.oldPos))
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.pressed = False
        self.oldPos = event.pos()
        return super().mouseReleaseEvent(event)

    def destroy(self, destroyWindow: bool = ..., destroySubWindows: bool = ...) -> None:
        for anim in (self.leftSlow, self.leftFast, self.rightFast, self.rightSlow):
            anim: QVariantAnimation
            anim.pause()
            anim.stop()
            anim.valueChanged.disconnect()
            anim.finished.disconnect()
            anim.deleteLater()
        return super().destroy(destroyWindow, destroySubWindows)

if(__name__=="__main__"):
    import __init__
