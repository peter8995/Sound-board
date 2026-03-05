from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PySide6.QtCore import Qt, Signal, QRect

class CartCell(QWidget):
    clicked = Signal(object, bool) # Emit the AudioItem and a boolean for multi_select modifier
    double_clicked = Signal(object)
    file_dropped = Signal(object, str) # Emit (item, filepath)
    
    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setMinimumSize(100, 100)
        self.setAcceptDrops(True)
        
        # Setup layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.name_label = QLabel(self.item.name)
        self.name_label.setFont(QFont("Microsoft JhengHei", 12, QFont.Bold))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("color: white;")
        
        self.hotkey_label = QLabel(self.item.hotkey)
        self.hotkey_label.setFont(QFont("Microsoft JhengHei", 10))
        self.hotkey_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.hotkey_label.setStyleSheet("color: #aaaaaa;")
        
        self.time_label = QLabel("00:00")
        self.time_label.setFont(QFont("Microsoft JhengHei", 10))
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("color: white;")
        
        layout.addWidget(self.hotkey_label)
        layout.addWidget(self.name_label, 1) # stretch
        layout.addWidget(self.time_label)
        
        self.is_selected = False
        
    def set_selected(self, state):
        self.is_selected = state
        self.update()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            multi_select = bool(event.modifiers() & Qt.ControlModifier) or bool(event.modifiers() & Qt.ShiftModifier)
            self.clicked.emit(self.item, multi_select)
            
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.item)
            
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            filepath = urls[0].toLocalFile()
            self.file_dropped.emit(self.item, filepath)
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        
        # Background Color dependent on state
        if self.item.is_playing:
            bg_color = QColor("#00aa00") # Playing - Green
        elif self.is_selected:
            bg_color = QColor(self.item.color).lighter(150) # Selected highlight
        else:
            bg_color = QColor(self.item.color) # Default color
            
        painter.fillRect(rect, bg_color)
        
        # Sync text dynamically to catch drops or property edits
        self.name_label.setText(self.item.name)
        self.hotkey_label.setText(self.item.hotkey)
        
        # Draw Progress Bar if playing
        if self.item.is_playing and self.item.end_time > 0:
            duration = self.item.end_time - self.item.start_time
            if duration > 0:
                prog_w = int((self.item.progress / duration) * rect.width())
                painter.fillRect(QRect(0, rect.height() - 5, prog_w, 5), QColor("#00ff00"))
                
        # Border
        if self.is_selected:
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawRect(rect.adjusted(1, 1, -2, -2))
        else:
            painter.setPen(QPen(QColor("#555555"), 1))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

class CartGrid(QWidget):
    item_selected = Signal(list) # Now emits list of selected items
    item_play_requested = Signal(object)
    file_dropped = Signal(object, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QGridLayout(self)
        self.layout.setSpacing(5)
        self.cells = []
        
    def populate(self, items, rows, cols):
        # Clear existing
        for i in reversed(range(self.layout.count())): 
            self.layout.itemAt(i).widget().setParent(None)
        self.cells.clear()
        
        # Create grid map
        grid_map = {(item.row, item.col): item for item in items if item.row >= 0 and item.col >= 0}
        
        for r in range(rows):
            for c in range(cols):
                item = grid_map.get((r, c))
                from project import AudioItem
                if not item:
                    # Empty cell placeholder item
                    item = AudioItem(uid=f"empty_{r}_{c}", name="", file_path="", row=r, col=c)
                    
                cell = CartCell(item)
                cell.clicked.connect(self._on_cell_clicked)
                cell.double_clicked.connect(self._on_cell_double_clicked)
                cell.file_dropped.connect(self.file_dropped.emit)
                self.layout.addWidget(cell, r, c)
                self.cells.append(cell)
                
    def _on_cell_clicked(self, item, multi_select):
        # Handle selection logic
        selected_items = []
        if multi_select:
            for cell in self.cells:
                if cell.item == item:
                    cell.set_selected(not cell.is_selected) # toggle target
                if cell.is_selected:
                    selected_items.append(cell.item)
        else:
            for cell in self.cells:
                is_target = (cell.item == item)
                cell.set_selected(is_target)
                if is_target:
                    selected_items.append(cell.item)
                    
        self.item_selected.emit(selected_items)
        
    def _on_cell_double_clicked(self, item):
        self.item_play_requested.emit(item)
        
    def update_cells(self):
        # Called periodically by main window to update progress bars / time labels
        for cell in self.cells:
            if cell.item and cell.item.file_path:
                cell.update() # triggers paintEvent
                
                # Update time text
                if cell.item.is_playing:
                    # Could calculate remaining time, but for now simple elapsed
                    mins = int(cell.item.progress // 60)
                    secs = int(cell.item.progress % 60)
                    
                    if cell.item.end_time > 0:
                        rem = (cell.item.end_time - cell.item.start_time) - cell.item.progress
                        rmins = int(max(0, rem) // 60)
                        rsecs = int(max(0, rem) % 60)
                        cell.time_label.setText(f"{mins:02d}:{secs:02d} / -{rmins:02d}:{rsecs:02d}")
                    else:
                        cell.time_label.setText(f"{mins:02d}:{secs:02d}")
                else:
                    duration = cell.item.end_time - cell.item.start_time
                    if duration > 0:
                        mins = int(duration // 60)
                        secs = int(duration % 60)
                        cell.time_label.setText(f"{mins:02d}:{secs:02d}")
                    else:
                        cell.time_label.setText("")
