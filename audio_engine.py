import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
import queue
import time
from typing import Dict, Optional

class AudioEngine:
    def __init__(self):
        self.samplerate = 44100
        self.blocksize = 1024
        self.channels = 2
        self.dtype = 'float32'
        
        self.stream = None
        self.is_running = False
        self.master_volume = 1.0
        
        # Audio memory: uid -> numpy array (stereo float32)
        self.audio_cache: Dict[str, np.ndarray] = {}
        # Info cache: uid -> samplerate
        self.sr_cache: Dict[str, int] = {}
        
        # Active playback state: uid -> {position: int, volume: float, fade_in: float, fade_out: float, start_idx: int, end_idx: int, loop: int}
        self.active_tracks: Dict[str, dict] = {}
        self.active_lock = threading.Lock()
        
        # Metering queue (for UI)
        self.meter_queue = queue.Queue(maxsize=100)
        
    def get_devices(self):
        return sd.query_devices()
        
    def set_device(self, device_id, buffer_size=1024):
        self.stop_stream()
        self.blocksize = buffer_size
        try:
            self.stream = sd.OutputStream(
                device=device_id,
                channels=self.channels,
                samplerate=self.samplerate,
                dtype=self.dtype,
                blocksize=self.blocksize,
                callback=self._audio_callback
            )
            self.stream.start()
            self.is_running = True
            return True
        except Exception as e:
            print(f"Error opening audio stream: {e}")
            return False

    def stop_stream(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.is_running = False
            
    def load_audio(self, uid: str, file_path: str):
        try:
            data, sr = sf.read(file_path, dtype=self.dtype)
            
            # Resample if needed (simplified for now, ideally use librosa or scipy resample)
            if sr != self.samplerate:
                # Basic fix for differing sample rates, but for generic use we recommend matching project SR
                # We will handle it naively for now or just trust soundfile
                pass
                
            # Convert to stereo if mono
            if data.ndim == 1:
                data = np.column_stack((data, data))
            elif data.ndim > 2:
                data = data[:, :2]
                
            self.audio_cache[uid] = data
            self.sr_cache[uid] = sr
            return True
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return False
            
    def play(self, item):
        with self.active_lock:
            if item.uid not in self.audio_cache:
                if not self.load_audio(item.uid, item.file_path):
                    return False
            
            data = self.audio_cache[item.uid]
            sr = self.sr_cache[item.uid]
            
            start_idx = int(item.start_time * sr)
            end_idx = int(item.end_time * sr) if item.end_time > 0 else len(data)
            
            if start_idx >= len(data):
                start_idx = 0
            if end_idx > len(data):
                end_idx = len(data)
                
            self.active_tracks[item.uid] = {
                'position': start_idx,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'volume': item.volume,
                'fade_in_samples': int(item.fade_in * sr),
                'fade_out_samples': int(item.fade_out * sr),
                'loop_count': item.loop_count,
                'loops_done': 0,
                'exclusive': item.exclusive,
                'fade_out_triggered': False,
                'fade_out_pos': 0,
                'item_ref': item  # Keep ref to update progress
            }
            
            if item.exclusive:
                # Stop all others
                for u in list(self.active_tracks.keys()):
                    if u != item.uid:
                        del self.active_tracks[u]
        return True
        
    def stop(self, uid: str, fade_out_time=None):
        with self.active_lock:
            if uid in self.active_tracks:
                track = self.active_tracks[uid]
                if fade_out_time is not None:
                    track['fade_out_samples'] = int(fade_out_time * self.samplerate)
                
                if track['fade_out_samples'] > 0:
                    track['fade_out_triggered'] = True
                    track['fade_out_pos'] = track['fade_out_samples'] # Start countdown
                else:
                    del self.active_tracks[uid]
                    
    def stop_all(self):
        with self.active_lock:
            self.active_tracks.clear()
            
    def pause_all(self):
        with self.active_lock:
            for uid, state in self.active_tracks.items():
                state['paused'] = not state.get('paused', False)
                if state['paused']:
                    state['item_ref'].is_playing = False
                else:
                    state['item_ref'].is_playing = True
            
    def _audio_callback(self, outdata, frames, time_info, status):
        if status:
            print(status)
            
        outdata.fill(0.0)
        
        with self.active_lock:
            finished = []
            
            for uid, state in self.active_tracks.items():
                if state.get('paused', False):
                    continue
                    
                data = self.audio_cache.get(uid)
                if data is None:
                    continue
                    
                pos = state['position']
                end_idx = state['end_idx']
                start_idx = state['start_idx']
                
                # Calculate how many frames we can process
                frames_left = end_idx - pos
                if frames_left <= 0:
                    if state['loop_count'] == 0 or state['loops_done'] < state['loop_count'] - 1:
                        # Loop
                        if state['loop_count'] > 0:
                            state['loops_done'] += 1
                        state['position'] = start_idx
                        pos = start_idx
                        frames_left = end_idx - pos
                    else:
                        finished.append(uid)
                        continue
                        
                chunk_size = min(frames, frames_left)
                
                chunk = data[pos:pos+chunk_size].copy()
                
                # Apply volume
                chunk *= state['volume']
                
                # Apply fade in
                fade_in_smp = state['fade_in_samples']
                if fade_in_smp > 0 and pos < start_idx + fade_in_smp:
                    fi_start = pos - start_idx
                    fi_end = fi_start + chunk_size
                    if fi_end > fade_in_smp:
                        fi_end = fade_in_smp
                        chunk_size_fi = fi_end - fi_start
                        curve = np.linspace(fi_start/fade_in_smp, fi_end/fade_in_smp, chunk_size_fi, dtype=np.float32)
                        chunk[:chunk_size_fi] *= curve[:, np.newaxis]
                    else:
                        curve = np.linspace(fi_start/fade_in_smp, fi_end/fade_in_smp, chunk_size, dtype=np.float32)
                        chunk *= curve[:, np.newaxis]
                        
                # Apply fade out
                fade_out_smp = state['fade_out_samples']
                if state['fade_out_triggered']:
                    fo_frames = min(chunk_size, state['fade_out_pos'])
                    curve = np.linspace(state['fade_out_pos']/fade_out_smp, (state['fade_out_pos']-fo_frames)/fade_out_smp, fo_frames, dtype=np.float32)
                    chunk[:fo_frames] *= curve[:, np.newaxis]
                    state['fade_out_pos'] -= fo_frames
                    if state['fade_out_pos'] <= 0:
                        finished.append(uid)
                elif fade_out_smp > 0 and pos > end_idx - fade_out_smp:
                    fo_start = pos - (end_idx - fade_out_smp)
                    fo_end = fo_start + chunk_size
                    curve = np.linspace(1.0 - fo_start/fade_out_smp, 1.0 - fo_end/fade_out_smp, chunk_size, dtype=np.float32)
                    curve = np.clip(curve, 0.0, 1.0)
                    chunk *= curve[:, np.newaxis]

                # Apply Multipoint Envelope
                nodes = state['item_ref'].volume_nodes
                if nodes and len(nodes) >= 2:
                    try:
                        sr = self.sr_cache[uid]
                        t_arr = np.linspace(pos/sr, (pos+chunk_size)/sr, chunk_size, dtype=np.float32)
                        xp = [n['time'] for n in nodes]
                        fp = [n['volume'] for n in nodes]
                        env_curve = np.interp(t_arr, xp, fp)
                        chunk *= env_curve[:, np.newaxis]
                    except Exception as e:
                        pass

                # Add to output mix
                outdata[:chunk_size] += chunk
                
                # Update position
                state['position'] += chunk_size
                
                # Update UI reference progress
                try:
                    sr = self.sr_cache[uid]
                    state['item_ref'].progress = state['position'] / sr
                    state['item_ref'].is_playing = True
                except:
                    pass

            for f in finished:
                if f in self.active_tracks:
                    try:
                        self.active_tracks[f]['item_ref'].is_playing = False
                        self.active_tracks[f]['item_ref'].progress = 0
                    except:
                        pass
                    del self.active_tracks[f]
                    
        # Apply master volume
        outdata *= self.master_volume
        
        # Calculate level meter (Peak and RMS)
        left_channel = outdata[:, 0]
        right_channel = outdata[:, 1]
        
        l_peak = np.max(np.abs(left_channel)) if len(left_channel) > 0 else 0.0
        r_peak = np.max(np.abs(right_channel)) if len(right_channel) > 0 else 0.0
        
        # Avoid queue block
        try:
            self.meter_queue.put_nowait((l_peak, r_peak))
        except queue.Full:
            pass
