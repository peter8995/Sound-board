from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtCore import Qt, QRect

class LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(150, 20)
        self.l_level = 0.0
        self.r_level = 0.0
        
    def set_levels(self, l, r):
        # Decay logic could be added here, or handled by the caller
        self.l_level = min(1.0, max(0.0, l))
        self.r_level = min(1.0, max(0.0, r))
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        w = rect.width()
        h = rect.height()
        
        # Draw background
        painter.fillRect(rect, QColor("#1e1e1e"))
        
        # Segment bars
        segments = 30
        gap = 2
        seg_w = (w - (segments+1)*gap) / segments
        
        half_h = (h - 3) / 2
        
        for i in range(segments):
            x = gap + i * (seg_w + gap)
            
            # Color logic based on position
            ratio = i / segments
            if ratio < 0.6:
                c = QColor("#00ff00") # Green
            elif ratio < 0.85:
                c = QColor("#ffff00") # Yellow
            else:
                c = QColor("#ff0000") # Red
                
            # Left channel
            if ratio <= self.l_level:
                painter.fillRect(QRect(x, 1, seg_w, half_h), c)
            else:
                painter.fillRect(QRect(x, 1, seg_w, half_h), c.darker(300))
                
            # Right channel
            if ratio <= self.r_level:
                painter.fillRect(QRect(x, 1 + half_h + 1, seg_w, half_h), c)
            else:
                painter.fillRect(QRect(x, 1 + half_h + 1, seg_w, half_h), c.darker(300))

class WaveformPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        
        self.audio_data = None
        self.samplerate = 44100
        
        # Visuals
        self.bg_color = QColor("#000000")
        self.wave_color = QColor("#ffffff")
        self.pos_color = QColor("#00ff00")
        self.fade_color = QColor("#ffff00")
        self.marker_color = QColor("#ffffff")
        
        # State
        self.item = None
        self.progress = 0.0 # 0.0 to 1.0 (relative to total length)
        
        # Interaction modes: none, start, end, node_drag
        self.drag_mode = "none"
        self.drag_node_idx = -1
        
    def set_audio(self, numpy_data, item, samplerate=44100):
        if numpy_data is not None and len(numpy_data) > 0:
            self.audio_data = numpy_data
        else:
            self.audio_data = None
            
        self.item = item
        self.samplerate = samplerate
        self.update()
        
    def update_progress(self, progress_seconds):
        if self.audio_data is None:
            return
        total_seconds = len(self.audio_data) / self.samplerate
        if total_seconds > 0:
            self.progress = progress_seconds / total_seconds
            self.update()
            
    def set_item_params(self, item):
        self.item = item
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        w = rect.width()
        h = rect.height()
        
        painter.fillRect(rect, self.bg_color)
        
        if self.audio_data is None or self.item is None:
            painter.setPen(QColor("#555555"))
            painter.drawText(rect, Qt.AlignCenter, "No Audio Selected")
            return
            
        total_samples = len(self.audio_data)
        total_seconds = total_samples / self.samplerate
        if total_seconds <= 0: return

        # Draw waveform
        samples_per_pixel = total_samples // w
        if samples_per_pixel > 0:
            painter.setPen(QPen(self.wave_color, 1))
            if self.audio_data.ndim > 1:
                mono = self.audio_data.mean(axis=1)
            else:
                mono = self.audio_data
                
            path = QPainterPath()
            half_h = h / 2
            step = max(1, samples_per_pixel)
            
            for x in range(w):
                start = x * step
                end = min(total_samples, start + step)
                if start < end:
                    chunk = mono[start:end]
                    vmin = chunk.min()
                    vmax = chunk.max()
                    
                    y1 = half_h - (vmax * half_h)
                    y2 = half_h - (vmin * half_h)
                    
                    if x == 0:
                        path.moveTo(x, y1)
                        path.lineTo(x, y2)
                    else:
                        painter.drawLine(x, y1, x, y2)
                        
        # Draw Playback line (Green)
        pos_x = int(self.progress * w)
        painter.setPen(QPen(self.pos_color, 2))
        painter.drawLine(pos_x, 0, pos_x, h)
        
        # Draw Start / End crop lines (White dashed)
        start_ratio = self.item.start_time / total_seconds
        end_time = self.item.end_time if self.item.end_time >= 0 else total_seconds
        end_ratio = end_time / total_seconds
        
        start_x = int(start_ratio * w)
        end_x = int(end_ratio * w)
        
        painter.setPen(QPen(self.marker_color, 2, Qt.DashLine))
        painter.drawLine(start_x, 0, start_x, h)
        painter.drawLine(end_x, 0, end_x, h)
        
        # Draw multi-point envelope (Yellow curve)
        nodes = self.item.volume_nodes
        if not nodes:
            # Default max volume curve
            nodes = [{"time": self.item.start_time, "volume": 1.0}, {"time": end_time, "volume": 1.0}]
            
        # Optional: ensure nodes are sorted by time
        nodes = sorted(nodes, key=lambda n: n["time"])
        
        painter.setPen(QPen(self.fade_color, 2))
        painter.setBrush(QBrush(self.fade_color))
        
        prev_x, prev_y = None, None
        
        for node in nodes:
            nx = int((node["time"] / total_seconds) * w)
            ny = int(h - (node["volume"] * h)) # volume 0-1, 1 is top (y=0)
            
            if prev_x is not None:
                painter.drawLine(prev_x, prev_y, nx, ny)
                
            # Draw point
            painter.drawEllipse(nx - 4, ny - 4, 8, 8)
            
            prev_x, prev_y = nx, ny
            
    def mousePressEvent(self, event):
        if self.audio_data is None or self.item is None:
            return
            
        total_seconds = len(self.audio_data) / self.samplerate
        w = self.width()
        h = self.height()
        
        ex = event.position().x()
        ey = event.position().y()
        time_val = (ex / w) * total_seconds
        vol_val = 1.0 - (ey / h)
        
        # 1. Check start/end points
        start_x = (self.item.start_time / total_seconds) * w
        end_time = self.item.end_time if self.item.end_time >= 0 else total_seconds
        end_x = (end_time / total_seconds) * w
        
        margin = 8
        if abs(ex - start_x) < margin:
            self.drag_mode = "start"
            return
        elif abs(ex - end_x) < margin:
            self.drag_mode = "end"
            return
            
        # 2. Check nodes
        nodes = self.item.volume_nodes
        if not nodes:
            # Bootstrap default nodes
            nodes = [{"time": self.item.start_time, "volume": 1.0}, {"time": end_time, "volume": 1.0}]
            self.item.volume_nodes = nodes
        
        clicked_node_idx = -1
        for i, node in enumerate(nodes):
            nx = (node["time"] / total_seconds) * w
            ny = h - (node["volume"] * h)
            
            if abs(ex - nx) < margin and abs(ey - ny) < margin:
                clicked_node_idx = i
                break
                
        if clicked_node_idx != -1:
            if event.button() == Qt.RightButton:
                # Remove node
                if len(nodes) > 2: # Keep at least 2 nodes
                    nodes.pop(clicked_node_idx)
                    self.item.volume_nodes = nodes
                    self.update()
            else:
                self.drag_mode = "node"
                self.drag_node_idx = clicked_node_idx
        else:
            if event.button() == Qt.LeftButton:
                # Add new node
                new_node = {"time": time_val, "volume": max(0.0, min(1.0, vol_val))}
                nodes.append(new_node)
                nodes.sort(key=lambda n: n["time"])
                self.item.volume_nodes = nodes
                self.drag_mode = "node"
                # find index
                self.drag_node_idx = nodes.index(new_node)
                self.update()
            
    def mouseMoveEvent(self, event):
        if self.audio_data is None or self.item is None or self.drag_mode == "none":
            return
            
        total_seconds = len(self.audio_data) / self.samplerate
        w = self.width()
        h = self.height()
        ex = max(0, min(event.position().x(), w))
        ey = max(0, min(event.position().y(), h))
        
        time_val = (ex / w) * total_seconds
        vol_val = 1.0 - (ey / h)
        
        if self.drag_mode == "start":
            end_t = self.item.end_time if self.item.end_time > 0 else total_seconds
            self.item.start_time = max(0.0, min(time_val, end_t))
        elif self.drag_mode == "end":
            self.item.end_time = max(self.item.start_time, min(time_val, total_seconds))
        elif self.drag_mode == "node" and self.drag_node_idx != -1:
            nodes = self.item.volume_nodes
            # Clamp time to preserve order (roughly)
            min_t = nodes[self.drag_node_idx - 1]["time"] if self.drag_node_idx > 0 else 0
            max_t = nodes[self.drag_node_idx + 1]["time"] if self.drag_node_idx < len(nodes) - 1 else total_seconds
            
            time_val = max(min_t, min(time_val, max_t))
            
            nodes[self.drag_node_idx]["time"] = time_val
            nodes[self.drag_node_idx]["volume"] = max(0.0, min(1.0, vol_val))
            
        self.update()
        
    def mouseReleaseEvent(self, event):
        self.drag_mode = "none"
        self.drag_node_idx = -1
