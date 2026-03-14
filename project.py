import json
import os
import shutil
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class AudioItem:
    # Basic info
    uid: str
    name: str
    file_path: str
    
    # Grid info
    row: int = -1
    col: int = -1
    color: str = "#333333"
    hotkey: str = ""
    
    # Playback settings
    volume: float = 1.0  # 0.0 to 1.0+
    fade_in: float = 0.0 # seconds
    fade_out: float = 0.1 # seconds
    start_time: float = 0.0 # seconds
    end_time: float = -1.0 # seconds, -1 means end of file
    volume_nodes: List[Dict[str, float]] = field(default_factory=list)

    
    # Mode settings
    play_mode: str = "Toggle" # "Toggle" or "Hold"
    loop_count: int = 1 # 0 means infinite loop
    exclusive: bool = False
    
    # Playlist specific
    is_playlist: bool = False
    auto_next: bool = False
    
    # UI State (not saved)
    is_playing: bool = False
    progress: float = 0.0
    
    def to_dict(self):
        return {
            "uid": self.uid,
            "name": self.name,
            "file_path": self.file_path,
            "row": self.row,
            "col": self.col,
            "color": self.color,
            "hotkey": self.hotkey,
            "volume": self.volume,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "volume_nodes": self.volume_nodes,
            "play_mode": self.play_mode,
            "loop_count": self.loop_count,
            "exclusive": self.exclusive,
            "is_playlist": self.is_playlist,
            "auto_next": self.auto_next
        }
        
    @classmethod
    def from_dict(cls, data):
        return cls(
            uid=data.get("uid", ""),
            name=data.get("name", "Unknown"),
            file_path=data.get("file_path", ""),
            row=data.get("row", -1),
            col=data.get("col", -1),
            color=data.get("color", "#333333"),
            hotkey=data.get("hotkey", ""),
            volume=data.get("volume", 1.0),
            fade_in=data.get("fade_in", 0.0),
            fade_out=data.get("fade_out", 0.1),
            start_time=data.get("start_time", 0.0),
            end_time=data.get("end_time", -1.0),
            volume_nodes=data.get("volume_nodes", []),
            play_mode=data.get("play_mode", "Toggle"),
            loop_count=data.get("loop_count", 1),
            exclusive=data.get("exclusive", False),
            is_playlist=data.get("is_playlist", False),
            auto_next=data.get("auto_next", False)
        )

@dataclass
class ProjectState:
    project_path: str = ""
    rows: int = 4
    cols: int = 5
    master_volume: float = 1.0
    output_device: str = ""
    buffer_size: int = 1024
    items: List[AudioItem] = field(default_factory=list)
    playlist: List[AudioItem] = field(default_factory=list)
    
    def get_audio_folder(self):
        if not self.project_path:
            return ""
        path = os.path.join(self.project_path, "audio")
        if not os.path.exists(path):
            os.makedirs(path)
        return path
    
    def save(self, is_save_as=False):
        if not self.project_path:
            return False
            
        json_path = os.path.join(self.project_path, "project.json")
        audio_folder = self.get_audio_folder()
        
        # Copy external files into project folder, then update paths
        path_updates = []
        for item in self.items + self.playlist:
            if item.file_path and os.path.exists(item.file_path):
                if not item.file_path.startswith(audio_folder):
                    filename = os.path.basename(item.file_path)
                    new_path = os.path.join(audio_folder, filename)

                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(new_path) and new_path != item.file_path:
                        new_path = os.path.join(audio_folder, f"{base}_{counter}{ext}")
                        counter += 1

                    try:
                        shutil.copy2(item.file_path, new_path)
                        path_updates.append((item, new_path))
                    except Exception as e:
                        print(f"Error copying {item.file_path} to project folder: {e}")

        # Apply path updates only after all copies succeed
        for item, new_path in path_updates:
            item.file_path = new_path
        
        data = {
            "rows": self.rows,
            "cols": self.cols,
            "master_volume": self.master_volume,
            "output_device": self.output_device,
            "buffer_size": self.buffer_size,
            "items": [item.to_dict() for item in self.items],
            "playlist": [item.to_dict() for item in self.playlist]
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        return True
        
    def load(self, path):
        self.project_path = path
        json_path = os.path.join(path, "project.json")
        if not os.path.exists(json_path):
            return False
            
        with open(json_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                self.rows = data.get("rows", 4)
                self.cols = data.get("cols", 5)
                self.master_volume = data.get("master_volume", 1.0)
                self.output_device = data.get("output_device", "")
                self.buffer_size = data.get("buffer_size", 1024)
                
                self.items = [AudioItem.from_dict(d) for d in data.get("items", [])]
                self.playlist = [AudioItem.from_dict(d) for d in data.get("playlist", [])]
                return True
            except Exception as e:
                print(f"Error loading project file: {e}")
                return False
