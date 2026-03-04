import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QSlider, QStackedWidget,
                               QGroupBox, QSpinBox, QComboBox, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, QTimer, QTime
from PySide6.QtGui import QFont, QColor

from project import ProjectState, AudioItem
from audio_engine import AudioEngine
from ui_widgets import LevelMeter, WaveformPanel
from ui_cart import CartGrid

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SoundBoard")
        self.resize(1200, 800)
        self.setStyleSheet("background-color: #2b2b2b; color: #ffffff;")
        
        # Core State
        self.project = ProjectState()
        self.audio_engine = AudioEngine()
        self.selected_item = None
        
        self._init_ui()
        self._init_timers()
        
    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # --- Top Bar ---
        top_bar = QHBoxLayout()
        
        # Audio Device Selection
        self.device_combo = QComboBox()
        devices = self.audio_engine.get_devices()
        for i, dev in enumerate(devices):
            if dev['max_output_channels'] > 0:
                # Add index or name to list
                self.device_combo.addItem(f"{dev['name']}", i)
        
        # Make the combobox white text since default in some themes drops to black
        self.device_combo.setStyleSheet("color: white; background: #444;")
        self.device_combo.currentIndexChanged.connect(self._change_device)
        top_bar.addWidget(QLabel("Output Device:"))
        top_bar.addWidget(self.device_combo)
        
        # Master Volume
        self.master_vol_slider = QSlider(Qt.Horizontal)
        self.master_vol_slider.setRange(0, 100)
        self.master_vol_slider.setValue(100)
        self.master_vol_slider.valueChanged.connect(self._change_master_volume)
        top_bar.addWidget(QLabel("Master Vol:"))
        top_bar.addWidget(self.master_vol_slider)
        
        # Global Controls
        self.btn_play_all = QPushButton("▶ Play")
        self.btn_stop_all = QPushButton("⏹ Stop All (ESC)")
        self.btn_stop_all.clicked.connect(self.audio_engine.stop_all)
        top_bar.addWidget(self.btn_play_all)
        top_bar.addWidget(self.btn_stop_all)
        
        # Level Meter
        self.level_meter = LevelMeter()
        top_bar.addWidget(self.level_meter)
        
        # System Time
        self.time_label = QLabel("00:00:00")
        self.time_label.setFont(QFont("Microsoft JhengHei", 16, QFont.Bold))
        top_bar.addWidget(self.time_label)
        
        main_layout.addLayout(top_bar)
        
        # --- View Switcher ---
        view_bar = QHBoxLayout()
        self.btn_view_cart = QPushButton("CART Mode")
        self.btn_view_playlist = QPushButton("Playlist Mode")
        
        view_bar.addWidget(self.btn_view_cart)
        view_bar.addWidget(self.btn_view_playlist)
        view_bar.addStretch()
        main_layout.addLayout(view_bar)
        
        # --- Main Content Area ---
        self.stack = QStackedWidget()
        
        # CART View
        self.cart_view = CartGrid()
        self.cart_view.item_selected.connect(self._on_item_selected)
        self.cart_view.item_play_requested.connect(self._on_item_play)
        self.stack.addWidget(self.cart_view)
        
        # Playlist View (Placeholder)
        self.playlist_view = QWidget() # Will implement List View next
        self.stack.addWidget(self.playlist_view)
        
        main_layout.addWidget(self.stack, 1) # Give it stretch factor 1
        
        # --- Bottom Panel (Waveform + Item Properties) ---
        bottom_layout = QHBoxLayout()
        
        # Properties editor
        self.prop_panel = QGroupBox("Selected Item Properties")
        prop_layout = QVBoxLayout(self.prop_panel)
        self.lbl_selected_name = QLabel("No Selection")
        prop_layout.addWidget(self.lbl_selected_name)
        # Placeholder for property editors
        prop_layout.addStretch()
        bottom_layout.addWidget(self.prop_panel)
        
        # Waveform visualizer
        self.waveform_panel = WaveformPanel()
        bottom_layout.addWidget(self.waveform_panel, 1) # stretch
        
        main_layout.addLayout(bottom_layout)
        
        # Setup Initial State
        self.cart_view.populate(self.project.items, self.project.rows, self.project.cols)
        
        # Default device selection (try to get default output)
        import sounddevice as sd
        try:
            default_out = sd.default.device[1]
            # find index in combo
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == default_out:
                    self.device_combo.setCurrentIndex(i)
                    self._change_device(i)
                    break
        except:
            pass
        
    def _init_timers(self):
        # UI Refresh Timer (60FPS)
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start(1000 // 60)
        
        # Time Display Timer (1 sec)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()
        
    def _update_ui(self):
        # Update level meter
        while not self.audio_engine.meter_queue.empty():
            l, r = self.audio_engine.meter_queue.get()
            self.level_meter.set_levels(l, r)
            
        # Level meter decay
        self.level_meter.set_levels(max(0, self.level_meter.l_level - 0.05), max(0, self.level_meter.r_level - 0.05))
        
        # Update progress and CART cells
        self.cart_view.update_cells()
        
        if self.selected_item and self.selected_item.is_playing:
            self.waveform_panel.update_progress(self.selected_item.progress)
        elif self.selected_item:
            self.waveform_panel.update_progress(0)
            
    def _update_clock(self):
        current_time = QTime.currentTime()
        self.time_label.setText(current_time.toString("hh:mm:ss"))
        
    def _change_device(self, idx):
        device_id = self.device_combo.itemData(idx)
        if device_id is not None:
            self.audio_engine.set_device(device_id)
            
    def _change_master_volume(self, value):
        self.audio_engine.master_volume = value / 100.0
        
    def _on_item_selected(self, item):
        self.selected_item = item
        self.lbl_selected_name.setText(item.name if item.name else "Empty Cart")
        
        if item.file_path and item.uid in self.audio_engine.audio_cache:
            data = self.audio_engine.audio_cache[item.uid]
            sr = self.audio_engine.sr_cache[item.uid]
            self.waveform_panel.set_audio(data, item, sr)
        else:
            self.waveform_panel.set_audio(None, item)
            
    def _on_item_play(self, item):
        import os
        import uuid
        
        if not item.file_path:
            # Need to pick file if empty
            file_path, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.wav *.flac *.ogg)")
            if file_path:
                item.file_path = file_path
                item.name = os.path.basename(file_path)
                item.uid = str(uuid.uuid4())
                
                # Load to get duration
                if self.audio_engine.load_audio(item.uid, item.file_path):
                    data = self.audio_engine.audio_cache[item.uid]
                    sr = self.audio_engine.sr_cache[item.uid]
                    item.end_time = len(data) / sr
                    self.project.items.append(item)
                    self._on_item_selected(item)
                    
        if item.file_path:
            if item.is_playing and item.play_mode == "Toggle":
                # Fade out on toggle
                self.audio_engine.stop(item.uid, fade_out_time=item.fade_out)
                item.is_playing = False # Early hint to UI
            else:
                self.audio_engine.play(item)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.audio_engine.stop_all()
        # Handle custom hotkeys here
        
def main():
    app = QApplication(sys.argv)
    
    # Set global font requirement
    font = QFont("Microsoft JhengHei", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
