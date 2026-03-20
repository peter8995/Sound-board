# SoundBoard

專業音效觸發器軟體，專為音效工程師設計，適用於現場演出、錄音室及劇場音效播放。

## 功能特色

### CART 格網系統
- 自訂行列數量，格子自動縮放填滿畫面
- 拖曳音檔至格子載入
- 左鍵單擊播放（Toggle/Hold 模式），右鍵選取開啟屬性彈出視窗
- 每個格子可設定：名稱、音量(0\~200%)、快捷鍵、顏色、淡入淡出、起始/結束時間、播放模式、播放次數、獨佔播放
- 播放中顯示綠色背景、進度條、正計時/倒計時
- 支援 Ctrl+右鍵多選，批次設定屬性

### 播放清單
- 新增、刪除、拖曳排序
- 拖曳音檔或點擊按鈕加入
- 左鍵播放、右鍵選取、空白鍵播放選取項目
- 選取項目黃底、播放中綠底（同時作為進度條）
- 支援結束自動下一首、獨佔播放
- 多選批次設定

### 波形編輯器
- 全曲波形圖（黑底白色波形）
- 綠色播放位置線即時更新
- 白色虛線標記起始/結束播放位置，可拖曳調整
- 黃色多點音量包絡線，可新增/刪除/拖曳控制點

### 音訊引擎
- 單一持續背景混音執行緒，低延遲即時混音
- 音檔載入時自動轉換 Sample Rate 至輸出裝置相同
- 可選擇輸出音效裝置及 Buffer Size (128\~4096)
- 總音量即時調整
- 立體聲音量表（綠/黃/紅色段顯示）

### 專案管理
- 儲存專案為資料夾（含 project.json + audio 子資料夾）
- 存檔、另存新檔、開啟舊檔
- 關閉時詢問是否儲存
- 開啟時選擇新增或開啟舊專案

### 其他
- ESC 全局停止播放
- 快捷鍵錄製（彈出視窗捕捉按鍵）
- 快捷鍵全域有效（即使焦點在屬性視窗輸入欄位中）
- Hold 模式快捷鍵支援（按住播放、放開停止）
- 系統時間顯示
- Pause/Play 切換按鈕 + Stop All
- Crash Log 自動記錄至 `logs/soundboard_YYYYMMDD_HHMMSS.log`

## 系統需求

- Python 3.10+
- 作業系統：Windows / Linux

## 安裝

```bash
pip install -r requirements.txt
```

### 依賴套件

| 套件 | 用途 |
|------|------|
| PySide6 | GUI 框架 |
| sounddevice | 音訊輸出 |
| soundfile | 音檔讀取 |
| numpy | 音訊資料處理 |
| scipy | Sample Rate 轉換 |

## 執行

```bash
python soundboard.py
```

## 專案結構

```
Sound-board/
├── soundboard.py      # 主程式入口及 UI 編排
├── audio_engine.py    # 音訊引擎（混音、播放、音量表）
├── project.py         # 資料模型及專案存讀取
├── ui_cart.py         # CART 格網 UI 元件
├── ui_playlist.py     # 播放清單 UI 元件
├── ui_properties.py   # 屬性編輯彈出視窗 (PropertiesDialog + PropertiesPanel)
├── ui_widgets.py      # 音量表及波形圖元件
├── logger.py          # 日誌系統
└── requirements.txt   # 依賴套件
```

## 操作說明

| 操作 | CART 格網 | 播放清單 |
|------|----------|---------|
| 播放 | 左鍵單擊 | 左鍵單擊 / 空白鍵 |
| 選取 | 右鍵單擊 | 右鍵單擊 |
| 多選 | Ctrl+右鍵 | Ctrl+右鍵 |
| 停止全部 | ESC | ESC |

## Log 位置

閃退時的日誌記錄在：

exe 或 .py 同層目錄下的 `logs/soundboard_YYYYMMDD_HHMMSS.log`（每次啟動產生獨立檔案，自動保留最近 10 個）

## 授權

MIT License
