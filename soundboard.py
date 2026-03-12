import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QSlider, QStackedWidget,
                               QGroupBox, QComboBox, QFileDialog, QMessageBox, QMenuBar,
                               QInputDialog, QDialog, QFormLayout, QSpinBox, QDialogButtonBox)
from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtGui import QFont, QColor

from project import ProjectState, AudioItem
from audio_engine import AudioEngine
from ui_widgets import LevelMeter, WaveformPanel
from ui_cart import CartGrid
from ui_playlist import PlaylistView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SoundBoard")
        self.resize(1200, 800)
        self.setStyleSheet("background-color: #2b2b2b; color: #ffffff;")
        
        # Core State
        self.project = ProjectState()
        self.audio_engine = AudioEngine()
        self.selected_items = []
        self.selected_item = None
        self.is_dirty = False
        
        self._init_ui()
        self._init_timers()
        
    def _init_ui(self):
        self._create_menu_bar()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # --- Top Bar ---
        top_bar = QHBoxLayout()
        
        # Global Controls
        self.btn_play_all = QPushButton("▶ Play")
        self.btn_pause_all = QPushButton("⏸ Pause")
        self.btn_stop_all = QPushButton("⏹ Stop All (ESC)")
        
        # We need an audio engine pause function (will be added to engine)
        self.btn_play_all.clicked.connect(self._play_selected)
        self.btn_pause_all.clicked.connect(self._pause_all)
        self.btn_stop_all.clicked.connect(self.audio_engine.stop_all)
        
        top_bar.addWidget(self.btn_play_all)
        top_bar.addWidget(self.btn_pause_all)
        top_bar.addWidget(self.btn_stop_all)
        
        # Output Device Selection
        self.device_combo = QComboBox()
        devices = self.audio_engine.get_devices()
        for i, dev in enumerate(devices):
            if dev['max_output_channels'] > 0:
                self.device_combo.addItem(f"{dev['name']}", i)
        
        self.device_combo.setStyleSheet("color: white; background: #444;")
        self.device_combo.currentIndexChanged.connect(self._change_device)
        top_bar.addWidget(QLabel("Output Device:"))
        top_bar.addWidget(self.device_combo)
        
        # Buffer Size Selection
        self.buffer_combo = QComboBox()
        self.buffer_combo.addItems(["128", "256", "512", "1024", "2048", "4096"])
        self.buffer_combo.setCurrentText(str(self.project.buffer_size))
        self.buffer_combo.setStyleSheet("color: white; background: #444;")
        self.buffer_combo.currentIndexChanged.connect(self._change_buffer_size)
        top_bar.addWidget(QLabel("Buffer:"))
        top_bar.addWidget(self.buffer_combo)
        
        # Master Volume
        self.master_vol_slider = QSlider(Qt.Horizontal)
        self.master_vol_slider.setRange(0, 100)
        self.master_vol_slider.setValue(100)
        self.master_vol_slider.valueChanged.connect(self._change_master_volume)
        top_bar.addWidget(QLabel("Master Vol:"))
        top_bar.addWidget(self.master_vol_slider)
        
        # Level Meter
        self.level_meter = LevelMeter()
        top_bar.addWidget(self.level_meter)
        
        # System Time
        self.time_label = QLabel("00:00:00")
        self.time_label.setFont(QFont("Microsoft JhengHei", 20, QFont.Bold))
        self.time_label.setStyleSheet("color: #00ff00;") # Make it obvious per requirement
        top_bar.addWidget(self.time_label)
        
        main_layout.addLayout(top_bar)
        
        # --- Main Content Area (Splitter) ---
        from PySide6.QtWidgets import QSplitter
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel - CART View
        cart_panel = QWidget()
        cart_layout = QVBoxLayout(cart_panel)
        cart_layout.setContentsMargins(0, 0, 0, 0)
        self.cart_view = CartGrid()
        self.cart_view.item_selected.connect(self._on_item_selected)
        self.cart_view.item_play_requested.connect(self._on_item_play)
        self.cart_view.file_dropped.connect(self._on_file_dropped)
        cart_layout.addWidget(self.cart_view)
        
        # Right Panel - Playlist View
        playlist_panel = QWidget()
        playlist_layout = QVBoxLayout(playlist_panel)
        playlist_layout.setContentsMargins(0, 0, 0, 0)
        self.playlist_view = PlaylistView()
        self.playlist_view.item_selected.connect(self._on_item_selected)
        self.playlist_view.item_play_requested.connect(self._on_item_play)
        self.playlist_view.list_changed.connect(lambda: setattr(self, 'is_dirty', True))
        playlist_layout.addWidget(self.playlist_view)
        
        self.splitter.addWidget(cart_panel)
        self.splitter.addWidget(playlist_panel)
        self.splitter.setStretchFactor(0, 3) # Give Cart area more default width
        self.splitter.setStretchFactor(1, 1) # Give Playlist area less width
        
        main_layout.addWidget(self.splitter, 1)
        
        # --- Bottom Panel (Waveform + Item Properties) ---
        bottom_layout = QHBoxLayout()
        
        # Properties editor
        from ui_properties import PropertiesPanel
        self.prop_group = QGroupBox("Selected Item Properties")
        prop_layout = QVBoxLayout(self.prop_group)
        self.prop_panel = PropertiesPanel()
        self.prop_panel.properties_changed.connect(self._on_properties_changed)
        prop_layout.addWidget(self.prop_panel)
        bottom_layout.addWidget(self.prop_group)
        
        self.waveform_panel = WaveformPanel()
        self.waveform_panel.properties_changed.connect(lambda: self.prop_panel.set_items(self.selected_items))
        bottom_layout.addWidget(self.waveform_panel, 1)
        
        main_layout.addLayout(bottom_layout)
        
        # Init Default Device
        import sounddevice as sd
        try:
            default_out = sd.default.device[1]
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == default_out:
                    self.device_combo.setCurrentIndex(i)
                    self._change_device(i)
                    break
        except:
            pass

        # Populate Views
        self.cart_view.populate(self.project.items, self.project.rows, self.project.cols)
        self.playlist_view.populate(self.project.playlist, self.audio_engine)
            
    def _create_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        action_new = file_menu.addAction("New Project")
        action_new.triggered.connect(self._new_project)
        
        action_open = file_menu.addAction("Open Project")
        action_open.triggered.connect(self._open_project)
        
        file_menu.addSeparator()
        
        action_save = file_menu.addAction("Save")
        action_save.triggered.connect(self._save_project)
        
        action_save_as = file_menu.addAction("Save As...")
        action_save_as.triggered.connect(self._save_project_as)
        
        settings_menu = menubar.addMenu("Settings")
        action_grid = settings_menu.addAction("Configure Grid Size")
        action_grid.triggered.connect(self._configure_grid_size)
        
    def showEvent(self, event):
        super().showEvent(event)
        # Show startup dialog only once when window is first shown
        if not hasattr(self, '_startup_done'):
            self._startup_done = True
            QTimer.singleShot(100, self._show_startup_dialog)

    def _show_startup_dialog(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Welcome to SoundBoard")
        msg.setText("Do you want to create a new project or open an existing one?")
        btn_new = msg.addButton("New Project", QMessageBox.ActionRole)
        btn_open = msg.addButton("Open Project", QMessageBox.ActionRole)
        msg.exec()
        
        if msg.clickedButton() == btn_open:
            self._open_project()
        else:
            self._new_project()
            
    def _new_project(self):
        if self._confirm_save():
            d = QDialog(self)
            d.setWindowTitle("New Project - Grid Size")
            layout = QFormLayout(d)
            
            spin_rows = QSpinBox()
            spin_rows.setRange(1, 20)
            spin_rows.setValue(4)
            
            spin_cols = QSpinBox()
            spin_cols.setRange(1, 20)
            spin_cols.setValue(5)
            
            layout.addRow("Rows:", spin_rows)
            layout.addRow("Columns:", spin_cols)
            
            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            btns.accepted.connect(d.accept)
            btns.rejected.connect(d.reject)
            layout.addWidget(btns)
            
            if d.exec() == QDialog.Accepted:
                self.project = ProjectState()
                self.project.rows = spin_rows.value()
                self.project.cols = spin_cols.value()
                self.cart_view.populate(self.project.items, self.project.rows, self.project.cols)
                self.playlist_view.populate(self.project.playlist, self.audio_engine)
                self.is_dirty = False
                self.setWindowTitle("SoundBoard - Untitled Project")

    def _open_project(self):
        if self._confirm_save():
            folder = QFileDialog.getExistingDirectory(self, "Open Project Folder")
            if folder:
                new_proj = ProjectState()
                if new_proj.load(folder):
                    self.project = new_proj
                    self.cart_view.populate(self.project.items, self.project.rows, self.project.cols)
                    self.playlist_view.populate(self.project.playlist, self.audio_engine)
                    self.is_dirty = False
                    self.setWindowTitle(f"SoundBoard - {os.path.basename(folder)}")
                    
                    # Update global states
                    self.master_vol_slider.setValue(int(self.project.master_volume * 100))
                else:
                    QMessageBox.warning(self, "Error", "Failed to load project from selected folder.")
                    
    def _save_project(self):
        if not self.project.project_path:
            return self._save_project_as()
            
        if self.project.save():
            self.is_dirty = False
            self.setWindowTitle(f"SoundBoard - {os.path.basename(self.project.project_path)}")
            return True
        else:
            QMessageBox.warning(self, "Error", "Failed to save project.")
            return False
            
    def _save_project_as(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Empty Folder for New Project")
        if folder:
            self.project.project_path = folder
            return self._save_project()
        return False

    def _confirm_save(self):
        if self.is_dirty:
            reply = QMessageBox.question(self, "Save Changes?", 
                                         "Project has unsaved changes. Do you want to save them?",
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if reply == QMessageBox.Yes:
                return self._save_project()
            elif reply == QMessageBox.Cancel:
                return False
        return True

    def closeEvent(self, event):
        if self._confirm_save():
            event.accept()
        else:
            event.ignore()

    def _init_timers(self):
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start(1000 // 60)
        
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()
        
    def _update_ui(self):
        while not self.audio_engine.meter_queue.empty():
            l, r = self.audio_engine.meter_queue.get()
            self.level_meter.set_levels(l, r)
            
        for item in self.project.items:
            if item.is_playing:
                # Get exact playback position from engine if needed, but it should be synced
                # Actually audio_engine syncs item.progress automatically in _audio_callback
                pass
                
        self.cart_view.update_cells()
        self.playlist_view.update_cells()
        
        if self.selected_item and self.selected_item.is_playing:
            self.waveform_panel.update_progress(self.selected_item.progress)
        elif self.selected_item:
            self.waveform_panel.update_progress(0)
            
        # Check for auto_next triggers
        for idx, item in enumerate(self.project.playlist):
            if getattr(item, '_needs_auto_next', False):
                item._needs_auto_next = False
                if idx + 1 < len(self.project.playlist):
                    next_item = self.project.playlist[idx + 1]
                    self._on_item_play(next_item)
                    # Automatically select the next item
                    self.playlist_view.list_widget.setCurrentRow(idx + 1)
                    self._on_item_selected([next_item])
            
    def _update_clock(self):
        current_time = QTime.currentTime()
        self.time_label.setText(current_time.toString("hh:mm:ss"))
        
    def _change_device(self, idx):
        device_id = self.device_combo.itemData(idx)
        if device_id is not None:
            self.audio_engine.set_device(device_id, self.project.buffer_size)
            self.project.output_device = self.device_combo.currentText()
            self.is_dirty = True
            
    def _change_buffer_size(self, idx):
        try:
            val = int(self.buffer_combo.currentText())
            self.project.buffer_size = val
            # re-init device
            self._change_device(self.device_combo.currentIndex())
        except ValueError:
            pass
            
    def _configure_grid_size(self):
        d = QDialog(self)
        d.setWindowTitle("Grid Size Configuration")
        layout = QFormLayout(d)
        
        spin_rows = QSpinBox()
        spin_rows.setRange(1, 20)
        spin_rows.setValue(self.project.rows)
        
        spin_cols = QSpinBox()
        spin_cols.setRange(1, 20)
        spin_cols.setValue(self.project.cols)
        
        layout.addRow("Rows:", spin_rows)
        layout.addRow("Columns:", spin_cols)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        layout.addWidget(btns)
        
        if d.exec() == QDialog.Accepted:
            self.project.rows = spin_rows.value()
            self.project.cols = spin_cols.value()
            # Repopulate cart view
            self.cart_view.populate(self.project.items, self.project.rows, self.project.cols)
            self.is_dirty = True
            
    def _change_master_volume(self, value):
        self.project.master_volume = value / 100.0
        self.audio_engine.master_volume = self.project.master_volume
        self.is_dirty = True
        
    def _on_item_selected(self, items):
        if not isinstance(items, list):
            items = [items]
            
        self.selected_items = items
        self.selected_item = items[-1] if items else None
        
        self.prop_panel.set_items(self.selected_items)
        
        item = self.selected_item
        if item and item.file_path:
            if item.uid not in self.audio_engine.audio_cache:
                self.audio_engine.load_audio(item.uid, item.file_path)
                
            if item.uid in self.audio_engine.audio_cache:
                data = self.audio_engine.audio_cache[item.uid]
                sr = self.audio_engine.samplerate
                self.waveform_panel.set_audio(data, item, sr)
            else:
                self.waveform_panel.set_audio(None, item)
        else:
            self.waveform_panel.set_audio(None, item)
            
    def _on_properties_changed(self):
        self.is_dirty = True
        self.cart_view.update_cells()
        self.playlist_view.update_cells()
        # Note: In a larger app, we might need to tell the audio engine if volume changed mid-playback
        # For now, properties impact next playback or waveform render.
        # We also want to redraw waveform if start/end times changed:
        if self.selected_item:
            self.waveform_panel.update()

    def _on_file_dropped(self, item, file_path):
        import uuid
        item.file_path = file_path
        item.name = os.path.basename(file_path)
        if not item.uid or item.uid.startswith("empty_"):
            item.uid = str(uuid.uuid4())
            if item not in self.project.items:
                self.project.items.append(item)
                
        if self.audio_engine.load_audio(item.uid, item.file_path):
            data = self.audio_engine.audio_cache[item.uid]
            sr = self.audio_engine.samplerate
            item.end_time = len(data) / sr
            
        self.is_dirty = True
        self.cart_view.update_cells()
        if self.selected_item == item:
            self._on_item_selected(self.selected_items)
            
    def _play_selected(self):
        if self.selected_item:
            self._on_item_play(self.selected_item)

    def _pause_all(self):
        # We will add it to engine
        if hasattr(self.audio_engine, 'pause_all'):
            self.audio_engine.pause_all()

    def _on_item_play(self, item):
        import uuid
        
        if not item.file_path:
            file_path, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.wav *.flac *.ogg *.mp3)")
            if file_path:
                item.file_path = file_path
                item.name = os.path.basename(file_path)
                item.uid = str(uuid.uuid4())
                
                if self.audio_engine.load_audio(item.uid, item.file_path):
                    data = self.audio_engine.audio_cache[item.uid]
                    sr = self.audio_engine.samplerate
                    item.end_time = len(data) / sr
                    self.project.items.append(item)
                    self.is_dirty = True
                    self._on_item_selected(item)
                    
        if item.file_path:
            if item.is_playing and item.play_mode == "Toggle":
                self.audio_engine.stop(item.uid, fade_out_time=item.fade_out)
                item.is_playing = False 
            else:
                self.audio_engine.play(item)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.audio_engine.stop_all()
            return
            
        # Ignore hotkeys if user is editing text (like Name or Hotkey field)
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QDoubleSpinBox, QSpinBox)):
            super().keyPressEvent(event)
            return
            
        # Match hotkeys
        key_name = event.text().upper()
        if not key_name and event.key():
            from PySide6.QtGui import QKeySequence
            key_name = QKeySequence(event.key()).toString().upper()
            
        if not key_name:
            return
            
        for item in self.project.items:
            if item.hotkey.upper() == key_name:
                self._on_item_play(item)
                return
                
        super().keyPressEvent(event)
        
def main():
    app = QApplication(sys.argv)
    font = QFont("Microsoft JhengHei", 10)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
