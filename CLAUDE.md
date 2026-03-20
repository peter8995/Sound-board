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
                       ──item_selected────────►  MainWindow._on_item_selected() ──► PropertiesDialog + WaveformPanel
                       ──hold_release_requested─► MainWindow._on_hold_released() ──► AudioEngine.stop()
```

UI updates at 60 Hz via `QTimer`. Clock updates at 1 Hz.

### Properties Dialog (ui_properties.py)

`PropertiesDialog` is a **non-modal QDialog** (single instance held by `MainWindow._props_dialog`). Right-clicking an item calls `set_items()` which updates content and `show()`s the dialog. The dialog forwards hotkey events to `MainWindow._handle_hotkey_press/release` via callbacks, so hotkeys work even when editing properties.

### Hotkey System (soundboard.py)

- Hotkeys resolved via `_resolve_key_name()` → `_find_hotkey_item()`
- **Toggle mode:** `_handle_hotkey_press` calls `_on_item_play()` (toggle on/off)
- **Hold mode:** `_handle_hotkey_press` starts playback + tracks in `_hold_keys` dict; `_handle_hotkey_release` stops on key-up
- `event.isAutoRepeat()` is filtered out to prevent re-triggering
- `PropertiesDialog` forwards key events to these handlers, so hotkeys work globally

### Mouse/Keyboard Interaction Model

- **Left click:** Play (Toggle mode) / Press-to-play (Hold mode)
- **Right click:** Select (opens properties dialog)
- **Ctrl+Right click:** Multi-select
- **Keyboard hotkey:** Toggle or Hold mode (Hold: press=play, release=stop)
- **ESC:** Global stop all + reset pause state

This applies consistently to both CART grid and Playlist.

## Key Constraints

- All audio in `audio_cache` is pre-resampled to the output device's sample rate
- Changing audio device clears all caches and stops all playback
- `item.progress` is written from the audio callback thread — read-only from UI
- Volume slider range is 0–200% (stored as 0.0–2.0 in `item.volume`)
- Font: Microsoft JhengHei (微軟正黑體) globally

## Design Decisions

### Properties Panel — 方案 A（已採用）

將 `PropertiesPanel` 從主視窗嵌入元件改為 Non-modal `QDialog`。主視窗持有單一 `_props_dialog` 實例，右鍵 item 時 `show()` + 更新內容。好處：主視窗高度可自由縮小、快捷鍵不被輸入欄位攔截。

### Properties Panel — 方案 B（備用）

將 `ui_properties.py` 整個重寫為獨立 `QDialog` class，完全解耦。更乾淨但改動量大，適合未來大規模重構時採用。

## Logging

Log files: `<app_dir>/logs/soundboard_YYYYMMDD_HHMMSS.log`
Format: `[timestamp.ms] LEVEL [module] file:line func() — message`
Uncaught exceptions are captured via `sys.excepthook` and logged before crash dialog.
