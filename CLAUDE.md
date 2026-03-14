# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Professional audio soundboard application for sound engineers. PySide6 GUI with real-time audio mixing via a persistent background `sounddevice.OutputStream` thread.

**Target user:** Sound engineers (live performance, studio, theatre).
**Language:** Traditional Chinese (繁體中文) for all UI text and user-facing strings.

## Running the Application

```bash
pip install -r requirements.txt
python soundboard.py
```

## Building Windows Executable

```bash
pyinstaller soundboard.spec
```

CI/CD: `.github/workflows/build-windows.yml` — manual trigger, builds Windows exe via PyInstaller.

## Architecture

### Audio Pipeline (audio_engine.py)

Single persistent `sounddevice.OutputStream` callback thread mixes all active tracks in real-time:
1. Audio loaded → resampled to device sample rate → cached as float32 numpy array
2. Playback triggered → track added to `active_tracks` dict (protected by `threading.Lock`)
3. Callback reads chunks, applies per-track volume + fade + multipoint envelope → mixes to stereo output
4. Peak levels sent to UI via `queue.Queue` (non-blocking meter updates)

**Critical:** The audio callback runs in a real-time thread. Never use numpy types directly in Qt draw calls — cast to Python `int`/`float` first.

### Data Model (project.py)

- `AudioItem` (dataclass) — all properties for a single audio slot (grid position, volume, fade, hotkey, play mode, etc.)
- `ProjectState` — container with grid dimensions, master volume, device config, items list, playlist list
- Serialized as `project.json` + `audio/` subfolder with copied audio files

### UI Signal Flow (soundboard.py → ui_*.py)

```
CartGrid/PlaylistView  ──item_play_requested──►  MainWindow._on_item_play()  ──►  AudioEngine.play()
                       ──item_selected────────►  MainWindow._on_item_selected() ──► PropertiesPanel + WaveformPanel
                       ──hold_release_requested─► MainWindow._on_hold_released() ──► AudioEngine.stop()
```

UI updates at 60 Hz via `QTimer`. Clock updates at 1 Hz.

### Mouse Interaction Model

- **Left click:** Play (Toggle mode) / Press-to-play (Hold mode)
- **Right click:** Select (opens properties panel)
- **Ctrl+Right click:** Multi-select
- **ESC:** Global stop all

This applies consistently to both CART grid and Playlist.

## Key Constraints

- All audio in `audio_cache` is pre-resampled to the output device's sample rate
- Changing audio device clears all caches and stops all playback
- `item.progress` is written from the audio callback thread — read-only from UI
- Volume slider range is 0–200% (stored as 0.0–2.0 in `item.volume`)
- Font: Microsoft JhengHei (微軟正黑體) globally

## Logging

Log files: `<app_dir>/logs/soundboard_YYYYMMDD_HHMMSS.log`
Format: `[timestamp.ms] LEVEL [module] file:line func() — message`
Uncaught exceptions are captured via `sys.excepthook` and logged before crash dialog.
