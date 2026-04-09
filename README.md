# DICOM Server GUI

[繁體中文](#繁體中文) | [English](#english)

---

## 繁體中文

一個基於 Python `PyQt6` 與 `pynetdicom` 打造的輕量級 DICOM 伺服器與影像管理工具。  
此專案旨在提供一個完整的圖形化介面，讓醫療資訊工程人員或研究者能輕鬆地接收、傳送、預覽以及編輯 DICOM 檔案。

### 🌟 核心功能特色

#### 1. DICOM 網路通訊 (SCP / SCU)
- **DICOM 接收端 (SCP)**：支援在背景啟動 C-STORE 服務，監聽特定 Port 並接收外部節點傳送的 DICOM 影像。支援多種 Transfer Syntax，涵蓋 JPEG Lossless/Lossy、JPEG 2000、RLE 等壓縮格式。
- **DICOM 傳送端 (SCU)**：支援將本地選取的 DICOM 檔案推播 (C-STORE) 至遠端伺服器 (如 PACS)。傳送前會自動解壓縮並動態偵測所需的 SOP Class，確保相容性最大化。
- **連線測試 (C-ECHO)**：提供一鍵 Ping 遠端 DICOM 節點，測試網路連線狀態 (Verification SOP Class)。
- **連線節點管理 (Peers)**：內建以 `QSettings` 持久化的連線對象儲存功能，自動記錄並快速切換常用的 AE Title、IP 與 Port 設定。

#### 2. 多功能 DICOM 檢視器
- **基礎影像預覽**：支援從 SQLite 資料庫或匯入本地檔案進行 2D 灰階/彩色影像顯示，並自動套用 Rescale Slope/Intercept (HU 值轉換)。
- **動態多幀支援**：針對多幀影像 (Multi-frame) 具備滑桿導航系統，支援跨檔案的統一幀索引 — 同一檢查 (Study) 底下的多個 DICOM 檔案會被自動展開為連續幀序列。
- **ECG 波形圖檢視**：支援 12 導程 (12-Lead) 的 DICOM 心電圖 (ECG) 繪製與捲動預覽，具備 Channel Sensitivity 校正與深色主題風格。
- **文件解析支援**：自動偵測 Encapsulated PDF 類型的 DICOM 並提供「一鍵匯出以外部程式開啟」功能。
- **響應式影像縮放**：影像會隨視窗大小自動等比縮放，ECG 波形圖則保持原始解析度並透過 ScrollArea 提供捲動瀏覽。

#### 3. Metadata 管理與隱私保護
- **標籤檢視 (DICOM Tags)**：一鍵展開完整的 DICOM Tag 階層式文字內容，使用等寬字型對齊顯示。
- **標籤編輯器**：內建防呆機制的編輯介面，支援文字/數值/Multi-value (反斜線分隔) 型別的安全覆寫。自動排除不安全的 VR 類型 (OB, OW, OF, OD, SQ, UN) 與 PixelData 等標籤。
- **一鍵匿名化**：提供專用的「去識別化/匿名化」工具，勾選機敏屬性 (如 Patient Name, Patient ID, Birth Date, Sex, Institution Name 等) 即可自動抹除或替換為安全字串。支援全部勾選/全部取消的快速操作。

#### 4. 檔案與紀錄管理
- **以 Study 為單位的檢查管理**：左側清單以 Study UID 為群組，聚合同一檢查的所有影像，方便整體瀏覽與刪除操作。
- **整筆檢查刪除**：選取清單紀錄後可一次刪除該檢查的所有資料庫紀錄與實體檔案，含二次確認防呆。
- **單張影像刪除**：在右側影像預覽區可精準刪除當前顯示的單一影像檔案，並自動跳轉至該檢查的下一張。

#### 5. 內建輕量級資料庫與日誌
- **SQLite 紀錄追蹤**：所有接收與開啟的患者 Metadata 會自動同步存入 `dicom_local.db` 進行索引管理，搭配 `database_manager.py` 封裝完整的 CRUD 操作。
- **記憶體快取 (LRU Cache)**：透過 `functools.lru_cache` 為 DICOM Dataset 提供記憶體級快取，避免重複磁碟 I/O，並在編輯/匿名化後自動清除快取以確保一致性。
- **每日日誌記錄**：整合 `logging` 模組,同時輸出至 Console 與每日 Rotating Log 檔案 (`logs/dicom_app_YYYY-MM-DD.log`)，並於主視窗的狀態列 (Status Bar) 顯示重要活動變化。

---

### 🛠️ 環境配置與依賴項

請確保您的系統已安裝 `Python 3.9+`，並具備以下依賴套件：

```bash
pip install PyQt6 pydicom pynetdicom numpy matplotlib
```

> **📌 補充說明**  
> 若需處理壓縮格式的影像 (如 JPEG-LS、JPEG 2000)，可能額外需要安裝解碼引擎：
> ```bash
> pip install pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg
> ```
> 或使用 GDCM：
> ```bash
> pip install python-gdcm
> ```

---

### 🚀 快速開始

直接執行 `main_window.py` 啟動主程式：

```bash
python main_window.py
```

#### 打包為執行檔 (可選)

如需打包為獨立的 Windows 執行檔，可使用 PyInstaller：

```bash
pip install pyinstaller
pyinstaller --noconsole --name DICOM_Server main_window.py
```

打包完成後，執行檔位於 `dist/DICOM_Server/` 目錄下。

---

### 🖥️ 介面佈局簡介

```
┌──────────────────────────────────────────────────────────────────┐
│  AE Title: [DICOM_SCP]  Port: [11112]  [▶ 啟動] [■ 停止]       │
│                     [📂 開啟 DICOM] [🗑 刪除紀錄] [📤 傳送 DICOM] │
├───────────────────┬──────────────────────────────────────────────┤
│   檢查清單         │  影像預覽    [📋 標籤] [✏️ 編輯] [👤 匿名化] [🗑 刪除]│
│                   │                                              │
│  Patient ID │ ... │         ┌──────────────────────┐             │
│  ────────── │ ... │         │                      │             │
│  P12345     │ ... │         │    DICOM Image       │             │
│  P98765     │ ... │         │    / ECG / PDF        │             │
│             │     │         │                      │             │
│             │     │         └──────────────────────┘             │
│             │     │        [◀] ════════════════ [▶]  3 / 10      │
├─────────────┴─────┴──────────────────────────────────────────────┤
│  狀態列: 已接收: John Doe (P12345)                                │
└──────────────────────────────────────────────────────────────────┘
```

1. **頂部控制列**：輸入 AE Title 與 Port 後，點擊「▶ 啟動」即可將本機作為 DICOM Server 運行。啟動後輸入欄位會自動鎖定，直到停止為止。
2. **左側清單**：顯示曾接收或開啟過的「檢查紀錄」(以 Study 為單位分組)，點擊即可展開預覽。
3. **右側操作區**：DICOM 專屬影像/波形畫布，上方提供「📋 DICOM 標籤」、「✏️ 編輯 DICOM」、「👤 匿名化」、「🗑 刪除單張」的操作按鈕。底部為多幀導航控制列 (僅在多幀/多檔案時顯示)。
4. **狀態列**：即時顯示最新的操作訊息與檔案活動紀錄。

---

### 📁 專案架構

```
dicom_server_gui/
├── main_window.py              # 主程式進入點與整體 GUI 視窗框架
├── dicom_scp_worker.py         # DICOM SCP (接收端) — QThread 背景監聽 C-STORE/C-ECHO
├── dicom_scu_worker.py         # DICOM SCU (傳送端) — QThread 背景執行 C-STORE 與 C-ECHO 測試
├── send_dicom_dialog.py        # 「傳送 DICOM」功能的操作視窗介面 (含 Peer 管理)
├── dicom_editor_dialog.py      # DICOM Tag 編輯器表單 (含 VR 型別安全轉換)
├── dicom_anonymize_dialog.py   # 去識別化/匿名化工具的對話框介面
├── dicom_image_utils.py        # 像素萃取、HU Windowing、多幀處理、PDF 提取 (含 LRU Cache)
├── ecg_utils.py                # 12 導程 ECG 波形解析與 Matplotlib 繪製
├── database_manager.py         # SQLite 資料庫封裝 — 病患/檢查紀錄的 CRUD 操作
├── logger_config.py            # 集中控制 Console 與檔案日誌輸出格式
└── README.md                   # 專案說明文件
```

> **📌 執行時自動產生的目錄與檔案 (不含在版本控制中)**
> - `dicom_local.db` — SQLite 資料庫，首次啟動時自動建立
> - `dicom_files/` — SCP 接收的 DICOM 檔案存放目錄
> - `logs/` — 每日日誌檔輸出目錄

#### 模組依賴關係

```
main_window.py
├── database_manager.py
├── dicom_scp_worker.py
├── dicom_scu_worker.py (via send_dicom_dialog.py)
├── send_dicom_dialog.py
├── dicom_editor_dialog.py
├── dicom_anonymize_dialog.py
├── dicom_image_utils.py
├── ecg_utils.py
└── logger_config.py (所有模組共用)
```

---

### 🔧 支援的 Transfer Syntax

SCP / SCU 皆已配置支援以下 Transfer Syntax：

| Transfer Syntax | UID |
|---|---|
| Implicit VR Little Endian | `1.2.840.10008.1.2` |
| Explicit VR Little Endian | `1.2.840.10008.1.2.1` |
| Explicit VR Big Endian | `1.2.840.10008.1.2.2` |
| Deflated Explicit VR Little Endian | `1.2.840.10008.1.2.1.99` |
| JPEG Baseline (8-bit) | `1.2.840.10008.1.2.4.50` |
| JPEG Extended (12-bit) | `1.2.840.10008.1.2.4.51` |
| JPEG Lossless SV1 | `1.2.840.10008.1.2.4.70` |
| JPEG Lossless | `1.2.840.10008.1.2.4.57` |
| JPEG 2000 Lossless | `1.2.840.10008.1.2.4.90` |
| JPEG 2000 | `1.2.840.10008.1.2.4.91` |
| RLE Lossless | `1.2.840.10008.1.2.5` |

---

### ⚠️ 注意事項

- **Patient ID 一致性**：當使用「編輯」或「匿名化」更改了 `Patient ID` 時，基於 DICOM 架構中以 Patient ID 作為病患唯一識別的設計，系統會將該檔案作為一名全新病患重新登錄，左側清單中也會多出一筆紀錄。操作前皆會跳出二次確認視窗。
- **防火牆設定**：若要作為 DICOM Server (SCP) 運作，請確保選用的 Port (如 `11112`) 在您的作業系統防火牆規則中處於放行狀態。
- **DICOM 快取機制**：系統使用 LRU Cache 快取最近讀取的 2 筆 DICOM 資料集以提升效能。在編輯或匿名化操作後，快取會自動被清除以避免顯示過期資料。
- **檔案命名規則**：SCP 接收到的檔案會以 `SOPInstanceUID.dcm` 作為檔名自動儲存至 `dicom_files/` 目錄，確保檔案唯一性。

---

### 📜 授權與聲明

此工具僅供醫療資訊研究與測試用途，**不應用於臨床診斷**。使用者須自行確保符合所有適用的醫療資訊安全與隱私法規 (如 HIPAA, GDPR 等)。

<br>

---
---

## English

A lightweight DICOM server and image management tool built with Python `PyQt6` and `pynetdicom`.
This project aims to provide a complete graphical interface for medical IT engineers or researchers to easily receive, send, preview, and edit DICOM files.

### 🌟 Core Features

#### 1. DICOM Network Communication (SCP / SCU)
- **DICOM Receiver (SCP)**: Supports running a C-STORE service in the background, listening on a specific port to receive DICOM images from external nodes. Supports various Transfer Syntaxes, including JPEG Lossless/Lossy, JPEG 2000, RLE, etc.
- **DICOM Sender (SCU)**: Supports pushing locally selected DICOM files (C-STORE) to remote servers (e.g., PACS). Automatically decompresses and dynamically detects required SOP Classes before transmission to maximize compatibility.
- **Connection Test (C-ECHO)**: Provides a one-click Ping to remote DICOM nodes to test network connectivity (Verification SOP Class).
- **Peer Management**: Built-in connection saving feature persistent via `QSettings`, automatically recording and quickly switching commonly used AE Title, IP, and Port settings.

#### 2. Multi-functional DICOM Viewer
- **Basic Image Preview**: Supports displaying 2D grayscale/color images from SQLite database or imported local files, automatically applying Rescale Slope/Intercept (HU value conversion).
- **Dynamic Multi-frame Support**: Features a slider navigation system for multi-frame images. Unifies frame indexing across files - multiple DICOM files under the same Study are automatically expanded into a continuous frame sequence.
- **ECG Waveform Viewer**: Supports DICOM Electrocardiogram (ECG) 12-lead drawing and scrolling preview, featuring Channel Sensitivity correction and a dark theme.
- **PDF Document Parsing**: Automatically detects Encapsulated PDF DICOMs and provides a "one-click export and open externally" feature.
- **Responsive Image Scaling**: Images automatically scale proportionally with window size, while ECG waveforms keep their original resolution and provide scrolling via ScrollArea.

#### 3. Metadata Management & Privacy Protection
- **DICOM Tags Viewer**: One-click expansion of the complete DICOM Tag hierarchical text content, displayed with monospace fonts.
- **Tag Editor**: Built-in foolproof editing interface supporting text/numeric/multi-value (backslash separated) types for safe overwriting. Automatically excludes unsafe VR types (OB, OW, OF, OD, SQ, UN) and tags like PixelData.
- **One-click Anonymizer**: Dedicated de-identification/anonymization tool. Select sensitive attributes (e.g., Patient Name, Patient ID, Birth Date, Sex, Institution Name) to automatically erase or replace them with safe strings. Supports select-all/deselect-all for quick operations.

#### 4. File & Record Management
- **Study-based Inspection Management**: The left list groups records by Study UID, aggregating all images of the same study for an easy overview and deletion operations.
- **Bulk Study Deletion**: After selecting a record, you can delete all database records and physical files of that study at once with a confirmation prompt.
- **Single Image Deletion**: In the right image preview area, you can precisely delete the single image file currently displayed, and the viewer automatically jumps to the next image of the study.

#### 5. Built-in Lightweight Database & Logging
- **SQLite Tracking**: Patient metadata for all received and opened files is automatically synchronized to `dicom_local.db` for index management, with `database_manager.py` encapsulating complete CRUD operations.
- **Memory Cache (LRU Cache)**: Provides memory-level caching for DICOM Datasets via `functools.lru_cache` to avoid repeated disk I/O, and automatically clears the cache after editing/anonymization to ensure consistency.
- **Daily Logging**: Integrates the `logging` module to output to both console and daily Rotating Log files (`logs/dicom_app_YYYY-MM-DD.log`), and displays important activity changes on the main window's Status Bar.

---

### 🛠️ Environment & Dependencies

Please make sure your system has `Python 3.9+` installed, with the following dependencies:

```bash
pip install PyQt6 pydicom pynetdicom numpy matplotlib
```

> **📌 Note**  
> If you need to handle compressed images (e.g., JPEG-LS, JPEG 2000), additional decode engines might be required:
> ```bash
> pip install pylibjpeg pylibjpeg-libjpeg pylibjpeg-openjpeg
> ```
> Or using GDCM:
> ```bash
> pip install python-gdcm
> ```

---

### 🚀 Quick Start

Run the main program directly:

```bash
python main_window.py
```

#### Package as Executable (Optional)

If you need to package it as a standalone Windows executable, use PyInstaller:

```bash
pip install pyinstaller
pyinstaller --noconsole --name DICOM_Server main_window.py
```

After packaging, the executable file is located in the `dist/DICOM_Server/` directory.

---

### 🖥️ Interface Layout Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  AE Title: [DICOM_SCP]  Port: [11112]  [▶ Start] [■ Stop]        │
│                     [📂 Open DICOM] [🗑 Delete Record] [📤 Send] │
├───────────────────┬──────────────────────────────────────────────┤
│   Study List      │  Image Preview [📋 Tags] [✏️ Edit] [👤 Anon] │
│                   │                                              │
│  Patient ID │ ... │         ┌──────────────────────┐             │
│  ────────── │ ... │         │                      │             │
│  P12345     │ ... │         │    DICOM Image       │             │
│  P98765     │ ... │         │    / ECG / PDF        │             │
│             │     │         │                      │             │
│             │     │         └──────────────────────┘             │
│             │     │        [◀] ════════════════ [▶]  3 / 10      │
├─────────────┴─────┴──────────────────────────────────────────────┤
│  Status Bar: Received: John Doe (P12345)                          │
└──────────────────────────────────────────────────────────────────┘
```

1. **Top Control Bar**: Enter AE Title and Port, then click "▶ Start" to run your local machine as a DICOM Server. Input fields are locked while running until stopped.
2. **Left List**: Displays received or opened "Study Records" (grouped by Study), click to preview.
3. **Right Operation Area**: DICOM exclusive image/waveform canvas. Top buttons provide "📋 DICOM Tags", "✏️ Edit DICOM", "👤 Anonymize", "🗑 Delete Single Frame" features. Bottom has a multi-frame navigation bar (only shows for multi-frame/multi-file records).
4. **Status Bar**: Real-time display of the latest operation messages and file activity records.

---

### 📁 Project Structure

```
dicom_server_gui/
├── main_window.py              # Main entry point and main GUI frame
├── dicom_scp_worker.py         # DICOM SCP (Receiver) — QThread for C-STORE/C-ECHO
├── dicom_scu_worker.py         # DICOM SCU (Sender) — QThread for C-STORE & C-ECHO testing
├── send_dicom_dialog.py        # "Send DICOM" dialog UI (includes Peer Management)
├── dicom_editor_dialog.py      # DICOM Tag Editor dialog (includes safeguard for VR types)
├── dicom_anonymize_dialog.py   # De-identification/anonymization tool dialog UI
├── dicom_image_utils.py        # Pixel extraction, HU Windowing, Multi-frame processing, PDF extraction (with LRU Cache)
├── ecg_utils.py                # 12-lead ECG waveform parsing & Matplotlib drawing
├── database_manager.py         # SQLite database encapsulation — CRUD operations for Study records
├── logger_config.py            # Centralized logger config for Console and file outputs
└── README.md                   # Project documentation
```

> **📌 Auto-generated Directories and Files (Not in Version Control)**
> - `dicom_local.db` — SQLite database, created on first launch
> - `dicom_files/` — Directory for SCP received DICOM files 
> - `logs/` — Directory for daily log file outputs

#### Module Dependencies

```
main_window.py
├── database_manager.py
├── dicom_scp_worker.py
├── dicom_scu_worker.py (via send_dicom_dialog.py)
├── send_dicom_dialog.py
├── dicom_editor_dialog.py
├── dicom_anonymize_dialog.py
├── dicom_image_utils.py
├── ecg_utils.py
└── logger_config.py (Shared by all modules)
```

---

### 🔧 Supported Transfer Syntax

Both SCP / SCU are configured to support the following Transfer Syntaxes:

| Transfer Syntax | UID |
|---|---|
| Implicit VR Little Endian | `1.2.840.10008.1.2` |
| Explicit VR Little Endian | `1.2.840.10008.1.2.1` |
| Explicit VR Big Endian | `1.2.840.10008.1.2.2` |
| Deflated Explicit VR Little Endian | `1.2.840.10008.1.2.1.99` |
| JPEG Baseline (8-bit) | `1.2.840.10008.1.2.4.50` |
| JPEG Extended (12-bit) | `1.2.840.10008.1.2.4.51` |
| JPEG Lossless SV1 | `1.2.840.10008.1.2.4.70` |
| JPEG Lossless | `1.2.840.10008.1.2.4.57` |
| JPEG 2000 Lossless | `1.2.840.10008.1.2.4.90` |
| JPEG 2000 | `1.2.840.10008.1.2.4.91` |
| RLE Lossless | `1.2.840.10008.1.2.5` |

---

### ⚠️ Notes & Disclaimers

- **Patient ID Consistency**: When changing `Patient ID` via "Edit" or "Anonymize", based on the DICOM architecture where Patient ID is the unique identifier, the system will re-register the file as an entirely new patient, adding a new record in the left list. A confirmation dialog will always appear before doing this.
- **Firewall Settings**: To run as a DICOM Server (SCP), make sure the selected Port (e.g., `11112`) is allowed in your Operating System's firewall rules.
- **DICOM Cache Mechanism**: The system uses an LRU Cache to cache the recently read 2 DICOM datasets for performance optimization. After edit or anonymization operations, the cache is automatically cleared to avoid displaying outdated data.
- **File Naming Convention**: Files received by the SCP will be automatically saved into the `dicom_files/` directory, using `SOPInstanceUID.dcm` as the filename to ensure uniqueness.

---

### 📜 License & Disclaimer

This tool is strictly intended for Medical IT Research and Testing purposes only, and **should NOT be used for clinical diagnosis**. Users must ensure compliance with all applicable medical information security and privacy regulations (e.g., HIPAA, GDPR, etc.).
