"""SynoStream-styled review/season selection; writes only after the explicit Delete action."""
import contextlib
from PyQt6.QtCore import QTimer,Qt
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QCheckBox,QPushButton,QPlainTextEdit,QScrollArea,QWidget
from synostream_deletion import Inventory


class DeleteMediaDialog(QDialog):
    def __init__(self,parent,title,movie,seeds,roots,protected,client_factory,task_factory,run_worker,can_write,on_deleted,translate=lambda s:s,edit_menu=lambda widget:None):
        super().__init__(parent)
        self.t=translate;self.movie=movie;self.client_factory=client_factory;self.task_factory=task_factory;self.run_worker=run_worker
        self.can_write=can_write;self.on_deleted=on_deleted;self.inventory=None;self.plan=None;self.worker=None;self.writing=False;self.attempted=False
        self.seeds=seeds;self.roots=roots;self.protected=protected;self.boxes=[]
        self.setWindowTitle(translate('Törlés a NAS-ról'));self.resize(720,560)
        layout=QVBoxLayout(self)
        heading=QLabel();heading.setTextFormat(Qt.TextFormat.PlainText);heading.setText(title);layout.addWidget(heading)
        note=QLabel(translate('Ez a NAS-on lévő fájlokat törli, nem csak a kártyát rejti el. Ellenőrizd a listát a törlés előtt.'))
        note.setWordWrap(True);layout.addWidget(note)
        self.season_widget=QWidget();self.season_layout=QVBoxLayout(self.season_widget)
        self.season_scroll=QScrollArea();self.season_scroll.setWidgetResizable(True);self.season_scroll.setWidget(self.season_widget);self.season_scroll.setMaximumHeight(150);self.season_scroll.setVisible(not movie);layout.addWidget(self.season_scroll)
        self.unknown=QCheckBox(translate("Az ismeretlen fájlokat is töröljem"));self.unknown.setChecked(False);self.unknown.toggled.connect(self.update_plan);layout.addWidget(self.unknown);self.unknown.hide()
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);edit_menu(self.preview);layout.addWidget(self.preview,1)
        self.status=QLabel(translate('Törlendő tartalom ellenőrzése…'));self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();layout.addLayout(row)
        self.delete=QPushButton(translate('Törlés a NAS-ról'));self.delete.setObjectName('ConfirmNASDeletion');self.delete.setEnabled(False)
        self.delete.setStyleSheet('QPushButton {background:#692f3b;color:white;border:1px solid #a65a69;border-radius:8px;padding:8px;} QPushButton:disabled {color:#99858a;}')
        self.cancel=QPushButton(translate('Mégse'));row.addWidget(self.delete);row.addWidget(self.cancel)
        self.cancel.clicked.connect(self.reject);self.delete.clicked.connect(self.confirm)
        QTimer.singleShot(0,self.prepare)

    def start(self,operation,success):
        worker=self.task_factory(operation);self.worker=worker
        worker.succeeded.connect(success)
        worker.failed.connect(self.failed)
        worker.finished.connect(lambda:setattr(self,'worker',None))
        self.run_worker(worker)

    def prepare(self):
        def work(stop):
            with contextlib.closing(self.client_factory(stop)) as client:
                return Inventory(self.seeds,self.roots,self.movie,client.list_folder,self.protected)
        def ready(inventory):
            if self.result()==QDialog.DialogCode.Rejected and not self.isVisible():return
            self.inventory=inventory
            if not self.movie:
                for season in inventory.seasons:
                    box=QCheckBox((self.t('Különkiadások') if season==0 else str(season)+'. '+self.t('évad')))
                    box.setProperty('season',season);box.setChecked(len(inventory.seasons)==1)
                    box.toggled.connect(self.update_plan);self.season_layout.addWidget(box);self.boxes.append(box)
            self.update_plan()
        self.start(work,ready)

    def update_plan(self):
        if not self.inventory:return
        try:
            self.plan=self.inventory.plan(None if self.movie else [b.property('season') for b in self.boxes if b.isChecked()],self.unknown.isChecked())
            self.preview.setPlainText('\n'.join(self.plan.files)+'\n\n'+self.t('Üresen maradó mappák takarítása:')+'\n'+'\n'.join(self.plan.folders))
            self.unknown.setVisible(bool(self.plan.unknown))
            if self.plan.unknown:self.preview.appendPlainText("\n"+self.t("Ismeretlen fájlok – alapértelmezés szerint megmaradnak")+"\n"+"\n".join(self.plan.unknown))
            self.status.setText(str(len(self.plan.files))+' '+self.t('fájl törlése. A nem üres és a médiatár gyökérmappái megmaradnak.'))
            self.delete.setEnabled(True)
        except ValueError as error:
            self.plan=None;self.preview.clear();self.status.setText(self.t(str(error)));self.delete.setEnabled(False)

    def confirm(self):
        if not self.plan or self.writing:return
        self.delete.setEnabled(False)
        if not self.can_write():
            self.status.setText(self.t('A folyamatban lévő beolvasás befejezésére várunk…'))
            QTimer.singleShot(300,self.confirm);return
        self.writing=True;self.attempted=True;self.cancel.setEnabled(False);self.season_widget.setEnabled(False);self.unknown.setEnabled(False)
        self.status.setText(self.t('Törlés folyamatban…'))
        plan=self.plan;inventory=self.inventory
        def work(stop):
            with contextlib.closing(self.client_factory(stop)) as client:
                inventory.list_folder=client.list_folder
                return inventory.execute(plan,client.delete_paths)
        def done(result):
            self.writing=False
            try:self.on_deleted(result)
            except Exception:
                self.failed(self.t('A NAS-fájlok törlése megtörtént, de a helyi lista mentése nem sikerült. Zárd be ezt az ablakot a médiatár újraellenőrzéséhez.'));return
            super(DeleteMediaDialog,self).accept()
        self.start(work,done)

    def failed(self,message):
        self.writing=False;self.status.setText(str(message));self.cancel.setEnabled(True)
        self.delete.setEnabled(False)  # A partial/uncertain operation is never repeated with an old plan.

    def reject(self):
        if self.writing:return
        if self.worker and self.worker.isRunning():self.worker.requestInterruption()
        self.plan=None
        super().reject()
