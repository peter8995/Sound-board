import os
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QListWidget, QListWidgetItem, QStyledItemDelegate, 
                               QAbstractItemView, QFileDialog, QStyle)
from PySide6.QtCore import Qt, Signal, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from project import AudioItem

class PlaylistDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        item_data = index.data(Qt.UserRole)
        is_selected = option.state & QStyle.State_Selected

        rect = option.rect
        
        if item_data and getattr(item_data, 'is_playing', False):
            # Playing: Green bg representing progress
            duration = getattr(item_data, 'end_time', 0) - getattr(item_data, 'start_time', 0)
            prog = getattr(item_data, 'progress', 0)
            
            painter.fillRect(rect, QColor("#2b2b2b")) # base
            if duration > 0:
                prog_w = int((prog / duration) * rect.width())
                painter.fillRect(QRect(rect.left(), rect.top(), prog_w, rect.height()), QColor("#00ff00"))
            text_color = QColor("black")
        elif is_selected:
            # Selected: Yellow bg
            painter.fillRect(rect, QColor("yellow"))
            text_color = QColor("black")
        else:
            # Normal
            painter.fillRect(rect, QColor("#333333"))
            text_color = QColor("white")
            
        # Draw Border
        painter.setPen(QPen(QColor("#111111"), 1))
        painter.drawRect(rect)
            
        painter.setPen(QPen(text_color))
        
        if item_data:
            idx = index.row() + 1
            name = getattr(item_data, 'name', 'Unknown')
            
            prog_s = getattr(item_data, 'progress', 0)
            end = getattr(item_data, 'end_time', 0)
            start = getattr(item_data, 'start_time', 0)
            dur = end - start
            rem = max(0, dur - prog_s) if dur > 0 else 0
            
            pm = int(prog_s // 60)
            ps = int(prog_s % 60)
            rm = int(rem // 60)
            rs = int(rem % 60)
            
            if getattr(item_data, 'is_playing', False):
                time_str = f"{pm:02d}:{ps:02d} / -{rm:02d}:{rs:02d}"
            else:
                if dur > 0:
                    time_str = f"{int(dur//60):02d}:{int(dur%60):02d}"
                else:
                    time_str = "00:00"
            
            # Draw Text
            font = QFont("Microsoft JhengHei", 12)
            painter.setFont(font)
            painter.drawText(rect.adjusted(10, 0, -100, 0), Qt.AlignLeft | Qt.AlignVCenter, f"{idx:02d}. {name}")
            
            font = QFont("Microsoft JhengHei", 10)
            painter.setFont(font)
            painter.drawText(rect.adjusted(0, 0, -10, 0), Qt.AlignRight | Qt.AlignVCenter, time_str)
            
    def sizeHint(self, option, index):
        return QSize(200, 40)

class CustomListWidget(QListWidget):
    files_dropped = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths)
        else:
            super().dropEvent(event)

class PlaylistView(QWidget):
    item_selected = Signal(list)
    item_play_requested = Signal(object)
    list_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_list = None
        self.audio_engine = None # Reference to engine to get duration
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        toolbar = QHBoxLayout()
        self.btn_add = QPushButton("Add Files")
        self.btn_del = QPushButton("Delete Selected")
        
        self.btn_add.clicked.connect(self._add_files_dialog)
        self.btn_del.clicked.connect(self._delete_selected)
        
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_del)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        self.list_widget = CustomListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.setItemDelegate(PlaylistDelegate())
        
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        self.list_widget.files_dropped.connect(self._on_files_dropped)
        self.list_widget.model().rowsMoved.connect(self._on_rows_moved)
        
        layout.addWidget(self.list_widget)
        
    def populate(self, playlist, audio_engine):
        self.project_list = playlist
        self.audio_engine = audio_engine
        self._refresh_list()
        
    def _refresh_list(self):
        self.list_widget.clear()
        if self.project_list is None: return
        
        for item in self.project_list:
            l_item = QListWidgetItem(self.list_widget)
            l_item.setData(Qt.UserRole, item)
            
    def _add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Audio Files", "", "Audio Files (*.wav *.flac *.ogg *.mp3)")
        if files:
            self._on_files_dropped(files)
            
    def _on_files_dropped(self, paths):
        if self.project_list is None: return
        
        for path in paths:
            uid = str(uuid.uuid4())
            name = os.path.basename(path)
            # Create AudioItem
            item = AudioItem(uid=uid, name=name, file_path=path, is_playlist=True)
            
            # Preload briefly to get length
            if self.audio_engine.load_audio(uid, path):
                data = self.audio_engine.audio_cache[uid]
                sr = self.audio_engine.sr_cache[uid]
                item.end_time = len(data) / sr
                
            self.project_list.append(item)
            
        self._refresh_list()
        self.list_changed.emit()
        
    def _delete_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items: return
        
        for sel in selected_items:
            item_data = sel.data(Qt.UserRole)
            if item_data in self.project_list:
                self.project_list.remove(item_data)
                
        self._refresh_list()
        self.list_changed.emit()
        
    def _on_selection_changed(self):
        selected_items = [i.data(Qt.UserRole) for i in self.list_widget.selectedItems()]
        self.item_selected.emit(selected_items)
        
    def _on_double_click(self, list_item):
        item_data = list_item.data(Qt.UserRole)
        self.item_play_requested.emit(item_data)
        
    def _on_rows_moved(self, sourceParent, sourceStart, sourceEnd, destinationParent, destinationRow):
        # Update underlying list logic (Reordering project_list)
        # Using simple clear and rebuild since Qt internal drag/drop manipulates the view model
        new_list = []
        for i in range(self.list_widget.count()):
            new_list.append(self.list_widget.item(i).data(Qt.UserRole))
        self.project_list.clear()
        self.project_list.extend(new_list)
        self.list_changed.emit()
        self.list_widget.viewport().update()
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            selected = self.list_widget.selectedItems()
            if selected:
                item_data = selected[0].data(Qt.UserRole)
                self.item_play_requested.emit(item_data)
        else:
            super().keyPressEvent(event)
            
    def update_cells(self):
        # Trigger repaint for progress
        self.list_widget.viewport().update()
