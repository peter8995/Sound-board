import logging
import numpy as np
import sounddevice as sd
import soundfile as sf
import threading
import queue
import scipy.signal
import time
from typing import Dict, List

logger = logging.getLogger("soundboard.audio")

class AudioEngine:
    def __init__(self):
        self.samplerate = 48000  # Default to 48kHz, will be updated based on device later if needed
        self.blocksize = 1024
        self.channels = 2
        self.dtype = 'float32'
        
        self.stream = None
        self.is_running = False
        self.master_volume = 1.0
        
        # Audio memory: uid -> numpy array (stereo float32)
        # All cached audio is pre-resampled to self.samplerate
        self.audio_cache: Dict[str, np.ndarray] = {}
        
        # Active playback state
        # uid -> {position: int, start_idx: int, end_idx: int, volume: float, ...}
        self.active_tracks: Dict[str, dict] = {}
        self.active_lock = threading.Lock()
        
        # Metering queue (for UI to display Volume Meter)
        self.meter_queue = queue.Queue(maxsize=1)
        
    def get_devices(self):
        return sd.query_devices()
        
    def set_device(self, device_id, buffer_size=1024):
        self.stop_stream()
        self.blocksize = buffer_size
        
        # Try to get device default sample rate so we avoid unnecessary SRC in OS
        try:
            device_info = sd.query_devices(device_id, 'output')
            dev_sr = int(device_info['default_samplerate'])
            if dev_sr > 0:
                self.samplerate = dev_sr
        except Exception as e:
            logger.warning("Could not get device info: %s", e)
            
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
            
            # Clear cache when changing device because sample rate might have changed
            # (In a real scenario we'd re-resample the existing cache, but for safety we clear)
            with self.active_lock:
                self.active_tracks.clear()
                self.audio_cache.clear()
                
            return True
        except Exception as e:
            logger.error("Error opening audio stream: %s", e)
            return False

    def stop_stream(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.is_running = False
            
    def load_audio(self, uid: str, file_path: str):
        """Loads audio file, converts it to target sample rate, and caches it."""
        try:
            data, sr = sf.read(file_path, dtype=self.dtype)
            
            # Resample if needed
            if sr != self.samplerate:
                logger.info("Resampling %s from %d to %d", file_path, sr, self.samplerate)
                data = scipy.signal.resample_poly(data, self.samplerate, sr, axis=0)
                
            # Convert to stereo if mono, or keep first 2 channels if surround
            if data.ndim == 1:
                data = np.column_stack((data, data))
            elif data.ndim > 2:
                data = data[:, :2]
                
            with self.active_lock:
                self.audio_cache[uid] = data.astype(np.float32)
                
            return True
        except Exception as e:
            logger.error("Error loading %s: %s", file_path, e)
            return False
            
    def play(self, item):
        if item.uid not in self.audio_cache:
            if not self.load_audio(item.uid, item.file_path):
                return False

        with self.active_lock:
            data = self.audio_cache[item.uid]
            
            start_idx = int(item.start_time * self.samplerate)
            end_idx = int(item.end_time * self.samplerate) if item.end_time > 0 else len(data)
            
            if start_idx >= len(data):
                start_idx = 0
            if end_idx > len(data):
                end_idx = len(data)
                
            # Prepare volume envelope nodes
            processed_nodes = []
            if hasattr(item, 'volume_nodes') and item.volume_nodes:
                for n in item.volume_nodes:
                    node_idx = int(n['time'] * self.samplerate)
                    processed_nodes.append((node_idx, n['volume']))
                processed_nodes.sort(key=lambda x: x[0])
                
            self.active_tracks[item.uid] = {
                'position': start_idx,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'volume': getattr(item, 'volume', 1.0),
                'fade_in_samples': int(getattr(item, 'fade_in', 0.0) * self.samplerate),
                'fade_out_samples': int(getattr(item, 'fade_out', 0.1) * self.samplerate),
                'loop_count': getattr(item, 'loop_count', 1),
                'loops_done': 0,
                'exclusive': getattr(item, 'exclusive', False),
                'fade_out_triggered': False,
                'fade_out_pos': 0,
                'item_ref': item,
                'processed_nodes': processed_nodes
            }
            
            item.is_playing = True
            item.progress = 0.0
            
            if getattr(item, 'exclusive', False):
                # Stop all other tracks
                for u in list(self.active_tracks.keys()):
                    if u != item.uid:
                        self._mark_track_finished(u)
                        
        return True
        
    def stop(self, uid: str, fade_out_time=None):
        with self.active_lock:
            if uid in self.active_tracks:
                track = self.active_tracks[uid]
                if fade_out_time is not None:
                    track['fade_out_samples'] = int(fade_out_time * self.samplerate)
                
                if track['fade_out_samples'] > 0:
                    track['fade_out_triggered'] = True
                    track['fade_out_pos'] = track['fade_out_samples']
                else:
                    self._mark_track_finished(uid)
                    
    def stop_all(self):
        with self.active_lock:
            for uid in list(self.active_tracks.keys()):
                track = self.active_tracks[uid]
                # Initiate a fast fade out to avoid pop
                if track['fade_out_samples'] == 0:
                    track['fade_out_samples'] = int(0.05 * self.samplerate) # 50ms smooth fade
                track['fade_out_triggered'] = True
                track['fade_out_pos'] = track['fade_out_samples']
            
    def pause_all(self):
        with self.active_lock:
            for uid, state in self.active_tracks.items():
                state['paused'] = not state.get('paused', False)
                state['item_ref'].is_playing = not state['paused']

    def _mark_track_finished(self, uid):
        try:
            state = self.active_tracks[uid]
            state['item_ref'].is_playing = False
            state['item_ref'].progress = 0.0
            # For playlist auto_next
            if getattr(state['item_ref'], 'auto_next', False):
                # We could signal the UI here, but callback to UI is better handled via periodic timer
                state['item_ref']._needs_auto_next = True 
            del self.active_tracks[uid]
        except Exception:
            pass

    def _apply_envelope(self, chunk, pos, chunk_size, nodes):
        """Applies multipoint envelope to a chunk."""
        if len(nodes) < 2:
            return
            
        # Time array for interpolation
        t_arr = np.arange(pos, pos + chunk_size)
        xp = [n[0] for n in nodes]
        fp = [n[1] for n in nodes]
        
        env_curve = np.interp(t_arr, xp, fp).astype(np.float32)
        chunk *= env_curve[:, np.newaxis]

    def _audio_callback(self, outdata, frames, time_info, status):
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
                
                frames_left = end_idx - pos
                if frames_left <= 0:
                    if state['loop_count'] == 0 or state['loops_done'] < state['loop_count'] - 1:
                        # Process loop
                        if state['loop_count'] > 0:
                            state['loops_done'] += 1
                        state['position'] = start_idx
                        pos = start_idx
                        frames_left = end_idx - pos
                    else:
                        finished.append(uid)
                        continue
                        
                chunk_size = min(frames, frames_left)
                if chunk_size <= 0:
                    finished.append(uid)
                    continue
                
                # Copy original slice to avoid modifying cache
                chunk = data[pos:pos+chunk_size].copy()
                
                # Base track volume (read live from item for real-time slider updates)
                chunk *= state['item_ref'].volume
                
                # Apply Fade In
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
                        
                # Apply Fade Out
                fade_out_smp = state['fade_out_samples']
                if state['fade_out_triggered']:
                    # Manual stop triggered
                    fo_frames = min(chunk_size, state['fade_out_pos'])
                    start_val = state['fade_out_pos'] / fade_out_smp
                    end_val = (state['fade_out_pos'] - fo_frames) / fade_out_smp
                    curve = np.linspace(start_val, end_val, fo_frames, dtype=np.float32)
                    chunk[:fo_frames] *= curve[:, np.newaxis]
                    state['fade_out_pos'] -= fo_frames
                    if state['fade_out_pos'] <= 0:
                        chunk[fo_frames:] = 0.0
                        finished.append(uid)
                elif fade_out_smp > 0 and pos > end_idx - fade_out_smp:
                    # End-of-file automatic fade out
                    fo_start = pos - (end_idx - fade_out_smp)
                    fo_end = fo_start + chunk_size
                    curve = np.linspace(1.0 - fo_start/fade_out_smp, 1.0 - fo_end/fade_out_smp, chunk_size, dtype=np.float32)
                    curve = np.clip(curve, 0.0, 1.0)
                    chunk *= curve[:, np.newaxis]

                # Apply Multipoint Volume Nodes (Envelope)
                if state['processed_nodes']:
                    self._apply_envelope(chunk, pos, chunk_size, state['processed_nodes'])

                # Mix into master output
                outdata[:chunk_size] += chunk
                
                # Update position
                state['position'] += chunk_size
                
                # Update UI reference progress occasionally
                try:
                    state['item_ref'].progress = state['position'] / self.samplerate
                except:
                    pass

            for uid in finished:
                self._mark_track_finished(uid)
                    
        # Apply Master Volume
        outdata *= self.master_volume
        
        # Calculate Level Meter (Peak & RMS)
        # Using peak for simplicity in meter, RMS is also fine. Let's send peak per channel.
        if not self.meter_queue.full():
            if np.any(np.abs(outdata) > 0.0001):
                l_peak = np.max(np.abs(outdata[:, 0])) if outdata.shape[1] > 0 else 0.0
                r_peak = np.max(np.abs(outdata[:, 1])) if outdata.shape[1] > 1 else 0.0
            else:
                l_peak, r_peak = 0.0, 0.0
                
            try:
                # Remove existing, keep only latest
                while not self.meter_queue.empty():
                    self.meter_queue.get_nowait()
                self.meter_queue.put_nowait((l_peak, r_peak))
            except Exception:
                pass
