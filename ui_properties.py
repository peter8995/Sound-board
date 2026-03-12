from PySide6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QDoubleSpinBox, 
                               QSpinBox, QComboBox, QCheckBox, QPushButton, 
                               QColorDialog)
from PySide6.QtCore import Signal, Qt

class PropertiesPanel(QWidget):
    properties_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self._is_updating = False
        
        self.layout = QFormLayout(self)
        
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)
        
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.textChanged.connect(self._on_hotkey_changed)
        
        self.color_btn = QPushButton("Select Color")
        self.color_btn.clicked.connect(self._on_color_clicked)
        
        self.vol_spin = QDoubleSpinBox()
        self.vol_spin.setRange(0.0, 5.0)
        self.vol_spin.setSingleStep(0.1)
        self.vol_spin.valueChanged.connect(self._on_vol_changed)
        
        self.fi_spin = QDoubleSpinBox()
        self.fi_spin.setRange(0.0, 60.0)
        self.fi_spin.valueChanged.connect(self._on_fi_changed)
        
        self.fo_spin = QDoubleSpinBox()
        self.fo_spin.setRange(0.0, 60.0)
        self.fo_spin.valueChanged.connect(self._on_fo_changed)
        
        self.st_spin = QDoubleSpinBox()
        self.st_spin.setRange(0.0, 3600.0)
        self.st_spin.valueChanged.connect(self._on_st_changed)
        
        self.et_spin = QDoubleSpinBox()
        self.et_spin.setRange(-1.0, 3600.0)
        self.et_spin.valueChanged.connect(self._on_et_changed)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Toggle", "Hold"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        
        self.loop_spin = QSpinBox()
        self.loop_spin.setRange(0, 999)
        self.loop_spin.setSpecialValueText("Infinite (0)")
        self.loop_spin.valueChanged.connect(self._on_loop_changed)
        
        self.excl_check = QCheckBox()
        self.excl_check.stateChanged.connect(self._on_excl_changed)
        
        self.auto_next_check = QCheckBox()
        self.auto_next_check.stateChanged.connect(self._on_auto_next_changed)
        
        self.layout.addRow("Name:", self.name_edit)
        self.layout.addRow("Hotkey:", self.hotkey_edit)
        self.layout.addRow("Color:", self.color_btn)
        self.layout.addRow("Volume:", self.vol_spin)
        self.layout.addRow("Fade In (s):", self.fi_spin)
        self.layout.addRow("Fade Out (s):", self.fo_spin)
        self.layout.addRow("Start Time:", self.st_spin)
        self.layout.addRow("End Time (-1=End):", self.et_spin)
        self.layout.addRow("Play Mode:", self.mode_combo)
        self.layout.addRow("Loop Count:", self.loop_spin)
        self.layout.addRow("Exclusive:", self.excl_check)
        self.layout.addRow("Auto Next (Playlist):", self.auto_next_check)
        
        self.setEnabled(False)
        
    def set_items(self, items):
        self._is_updating = True
        self.items = items
        
        if not items:
            self.setEnabled(False)
            self._is_updating = False
            return
            
        self.setEnabled(True)
        
        def get_common(attr):
            first = getattr(items[0], attr)
            for item in items[1:]:
                if getattr(item, attr) != first:
                    return None
            return first

        # Name
        c_name = get_common("name")
        self.name_edit.setText(c_name if c_name is not None else "<Multiple>")
        
        # Hotkey
        c_hotkey = get_common("hotkey")
        self.hotkey_edit.setText(c_hotkey if c_hotkey is not None else "<Multiple>")
        
        # Volume
        c_vol = get_common("volume")
        if c_vol is not None: self.vol_spin.setValue(c_vol)
        
        # Fade In
        c_fi = get_common("fade_in")
        if c_fi is not None: self.fi_spin.setValue(c_fi)
        
        # Fade Out
        c_fo = get_common("fade_out")
        if c_fo is not None: self.fo_spin.setValue(c_fo)
        
        # Start Time
        c_st = get_common("start_time")
        if c_st is not None: self.st_spin.setValue(c_st)
        
        # End Time
        c_et = get_common("end_time")
        if c_et is not None: self.et_spin.setValue(c_et)
        
        # Play Mode
        c_mode = get_common("play_mode")
        if c_mode is not None:
            self.mode_combo.setCurrentText(c_mode)
            
        # Loop Count
        c_loop = get_common("loop_count")
        if c_loop is not None: self.loop_spin.setValue(c_loop)
        
        # Exclusive
        c_excl = get_common("exclusive")
        if c_excl is not None: 
            self.excl_check.setCheckState(Qt.Checked if c_excl else Qt.Unchecked)
        else:
            self.excl_check.setCheckState(Qt.PartiallyChecked)
            
        # Auto Next
        c_auto = get_common("auto_next")
        if c_auto is not None:
            self.auto_next_check.setCheckState(Qt.Checked if c_auto else Qt.Unchecked)
        else:
            self.auto_next_check.setCheckState(Qt.PartiallyChecked)
            
        self._is_updating = False

    def _apply_to_all(self, attr, value):
        if self._is_updating or not self.items: return
        for item in self.items:
            # only modify if it's changing real info
            setattr(item, attr, value)
        self.properties_changed.emit()

    def _on_name_changed(self, text):
        if text != "<Multiple>": self._apply_to_all("name", text)
        
    def _on_hotkey_changed(self, text):
        if text != "<Multiple>": self._apply_to_all("hotkey", text)
        
    def _on_vol_changed(self, val):
        self._apply_to_all("volume", val)
        
    def _on_fi_changed(self, val):
        self._apply_to_all("fade_in", val)
        
    def _on_fo_changed(self, val):
        self._apply_to_all("fade_out", val)
        
    def _on_st_changed(self, val):
        self._apply_to_all("start_time", val)
        
    def _on_et_changed(self, val):
        self._apply_to_all("end_time", val)
        
    def _on_mode_changed(self, idx):
        self._apply_to_all("play_mode", self.mode_combo.currentText())
        
    def _on_loop_changed(self, val):
        self._apply_to_all("loop_count", val)
        
    def _on_excl_changed(self, state):
        if state != Qt.PartiallyChecked.value:
            self._apply_to_all("exclusive", state == Qt.Checked.value)
            
    def _on_auto_next_changed(self, state):
        if state != Qt.PartiallyChecked.value:
            self._apply_to_all("auto_next", state == Qt.Checked.value)
            
    def _on_color_clicked(self):
        # Open color picker
        color = QColorDialog.getColor(Qt.white, self, "Select Color for Item(s)")
        if color.isValid():
            hex_color = color.name()
            self._apply_to_all("color", hex_color)
