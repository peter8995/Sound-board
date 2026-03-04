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
        
        # Interaction modes: none, fade_in, fade_out, start, end
        self.drag_mode = "none"
        
    def set_audio(self, numpy_data, item, samplerate=44100):
        # downsample for display if needed
        if numpy_data is not None and len(numpy_data) > 0:
            # We'll calculate min/max pairs per pixel during paint or cache it
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

        # Draw waveform (simplified downsampling visualizer)
        samples_per_pixel = total_samples // w
        if samples_per_pixel > 0:
            painter.setPen(QPen(self.wave_color, 1))
            
            # Convert to mono for display
            if self.audio_data.ndim > 1:
                mono = self.audio_data.mean(axis=1)
            else:
                mono = self.audio_data
                
            path = QPainterPath()
            half_h = h / 2
            
            # Simple min/max decimation
            # For massive files this should be cached in set_audio
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
                        
        # Draw Playback line
        pos_x = int(self.progress * w)
        painter.setPen(QPen(self.pos_color, 2))
        painter.drawLine(pos_x, 0, pos_x, h)
        
        # Draw Start / End crop lines
        start_ratio = self.item.start_time / total_seconds
        end_ratio = self.item.end_time / total_seconds if self.item.end_time >= 0 else 1.0
        
        start_x = int(start_ratio * w)
        end_x = int(end_ratio * w)
        
        painter.setPen(QPen(self.marker_color, 2, Qt.DashLine))
        painter.drawLine(start_x, 0, start_x, h)
        painter.drawLine(end_x, 0, end_x, h)
        
        # Draw Fade Curves (Yellow)
        painter.setPen(QPen(self.fade_color, 2))
        # Fade in curve
        fade_in_end_x = int((self.item.start_time + self.item.fade_in) / total_seconds * w)
        painter.drawLine(start_x, h, fade_in_end_x, 0) # Bottom to Top
        
        # Fade out curve
        fade_out_start_x = int((self.item.end_time - self.item.fade_out if self.item.end_time > 0 else total_seconds - self.item.fade_out) / total_seconds * w)
        painter.drawLine(fade_out_start_x, 0, end_x, h) # Top to Bottom
        
        
    def mousePressEvent(self, event):
        if self.audio_data is None or self.item is None:
            return
            
        total_seconds = len(self.audio_data) / self.samplerate
        w = self.width()
        x = event.position().x()
        
        # Hit detection (rough)
        start_x = (self.item.start_time / total_seconds) * w
        end_x = (self.item.end_time / total_seconds if self.item.end_time >= 0 else 1.0) * w
        
        fade_in_x = ((self.item.start_time + self.item.fade_in) / total_seconds) * w
        fade_out_x = ((self.item.end_time - self.item.fade_out if self.item.end_time > 0 else total_seconds - self.item.fade_out) / total_seconds) * w

        margin = 10
        if abs(x - start_x) < margin:
            self.drag_mode = "start"
        elif abs(x - end_x) < margin:
            self.drag_mode = "end"
        elif abs(x - fade_in_x) < margin:
            self.drag_mode = "fade_in"
        elif abs(x - fade_out_x) < margin:
            self.drag_mode = "fade_out"
        else:
            self.drag_mode = "none"
            
    def mouseMoveEvent(self, event):
        if self.audio_data is None or self.item is None or self.drag_mode == "none":
            return
            
        total_seconds = len(self.audio_data) / self.samplerate
        w = self.width()
        x = max(0, min(event.position().x(), w))
        
        time_val = (x / w) * total_seconds
        
        if self.drag_mode == "start":
            self.item.start_time = max(0.0, min(time_val, self.item.end_time if self.item.end_time > 0 else total_seconds))
            # clamp fade in
            max_fade = (self.item.end_time if self.item.end_time > 0 else total_seconds) - self.item.start_time
            self.item.fade_in = min(self.item.fade_in, max_fade)
        elif self.drag_mode == "end":
            self.item.end_time = max(self.item.start_time, min(time_val, total_seconds))
            # clamp fade out
            max_fade = self.item.end_time - self.item.start_time
            self.item.fade_out = min(self.item.fade_out, max_fade)
        elif self.drag_mode == "fade_in":
            self.item.fade_in = max(0.0, time_val - self.item.start_time)
        elif self.drag_mode == "fade_out":
            end_t = self.item.end_time if self.item.end_time > 0 else total_seconds
            self.item.fade_out = max(0.0, end_t - time_val)
            
        self.update()
        
    def mouseReleaseEvent(self, event):
        self.drag_mode = "none"
