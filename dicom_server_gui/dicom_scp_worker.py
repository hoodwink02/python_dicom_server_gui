import os
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal
from pynetdicom import AE, evt, AllStoragePresentationContexts
from pydicom import dcmread
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    DeflatedExplicitVRLittleEndian,
    JPEGLosslessSV1,
    JPEGLossless,
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEG2000Lossless,
    JPEG2000,
    RLELossless,
)

from logger_config import setup_logger

logger = setup_logger("dicom_app")

# SCP 支援的 Transfer Syntax 列表
TRANSFER_SYNTAXES = [
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian,
    DeflatedExplicitVRLittleEndian,
    JPEGLosslessSV1,
    JPEGLossless,
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEG2000Lossless,
    JPEG2000,
    RLELossless,
]


class DicomScpWorker(QThread):
    """
    DICOM SCP 工作執行緒。
    在 QThread 中啟動 pynetdicom 的 AE (Application Entity)，
    監聽指定 Port 接收 C-STORE 請求，避免阻塞 PyQt6 主執行緒。
    """

    # ---- PyQt Signals ----
    # 當一筆 DICOM 檔案儲存並解析完畢後，發送包含 metadata 與檔案路徑的 dict
    dicom_received = pyqtSignal(dict)
    # 當伺服器狀態有變化時 (啟動 / 停止 / 錯誤)，發送狀態訊息字串
    status_changed = pyqtSignal(str)

    def __init__(self, port: int = 11112, ae_title: str = "DICOM_SCP",
                 storage_dir: str = "./dicom_files", parent=None):
        """
        初始化 DICOM SCP Worker。

        :param port: 監聽的 Port，預設 11112
        :param ae_title: AE Title (應用程式實體名稱)
        :param storage_dir: DICOM 檔案儲存資料夾，預設 ./dicom_files
        :param parent: 父 QObject
        """
        super().__init__(parent)
        self.port = port
        self.ae_title = ae_title
        self.storage_dir = storage_dir
        self._is_running = False
        self._ae = None  # pynetdicom Application Entity 實例

    def run(self):
        """
        QThread 的主要執行方法。
        建立 AE、綁定 C-STORE 事件處理器，並以阻塞模式啟動 SCP 伺服器。
        """
        # 確保儲存資料夾存在
        os.makedirs(self.storage_dir, exist_ok=True)

        # 建立 Application Entity
        self._ae = AE(ae_title=self.ae_title)

        # 支援所有標準 Storage SOP Classes，加入多種 Transfer Syntax (含壓縮格式)
        for context in AllStoragePresentationContexts:
            self._ae.add_supported_context(context.abstract_syntax, TRANSFER_SYNTAXES)

        # 支援 Verification SOP Class (C-ECHO)
        self._ae.add_supported_context("1.2.840.10008.1.1")

        # 定義事件處理器列表
        handlers = [
            (evt.EVT_C_STORE, self._handle_c_store),
            (evt.EVT_C_ECHO, self._handle_c_echo),
        ]

        self._is_running = True
        logger.info(f"DICOM SCP 啟動中 — AE Title: {self.ae_title}, Port: {self.port}")
        self.status_changed.emit(f"DICOM SCP 已啟動 — 監聯 Port {self.port}")

        try:
            # 以阻塞模式啟動伺服器
            self._ae.start_server(
                ("0.0.0.0", self.port),
                block=True,
                evt_handlers=handlers,
            )
        except Exception as e:
            logger.error(f"SCP 執行錯誤: {e}", exc_info=True)
            self.status_changed.emit(f"SCP 錯誤: {e}")
        finally:
            self._is_running = False
            logger.info("DICOM SCP 已停止")
            self.status_changed.emit("DICOM SCP 已停止")

    def stop(self):
        """優雅地關閉 SCP 伺服器"""
        logger.info("正在關閉 DICOM SCP...")
        if self._ae is not None:
            self._ae.shutdown()
        self._is_running = False

    # ------------------------------------------------------------------
    # 事件處理器
    # ------------------------------------------------------------------
    def _handle_c_store(self, event):
        """
        處理收到的 C-STORE 請求。
        1. 將 DICOM 檔案寫入磁碟
        2. 用 pydicom 讀取 metadata
        3. 透過 Signal 將結果送回主執行緒

        :param event: pynetdicom 的 C-STORE 事件物件
        :return: 0x0000 表示成功
        """
        dataset = event.dataset
        dataset.file_meta = event.file_meta

        # ---- 儲存檔案 ----
        # 以 SOP Instance UID 作為檔名，確保唯一性
        sop_instance_uid = dataset.SOPInstanceUID
        filename = f"{sop_instance_uid}.dcm"
        file_path = os.path.join(self.storage_dir, filename)
        file_path = os.path.abspath(file_path)

        try:
            dataset.save_as(file_path, write_like_original=False)
            logger.info(f"DICOM 檔案已儲存: {file_path}")
        except Exception as e:
            logger.error(f"檔案儲存失敗: {file_path} — {e}", exc_info=True)
            self.status_changed.emit(f"檔案儲存失敗: {e}")
            return 0xC001  # 回傳失敗狀態碼

        # ---- 從記憶體中的 dataset 直接讀取 metadata ----
        try:
            metadata = {
                "patient_id": str(getattr(dataset, "PatientID", "")),
                "patient_name": str(getattr(dataset, "PatientName", "")),
                "study_uid": str(getattr(dataset, "StudyInstanceUID", "")),
                "series_uid": str(getattr(dataset, "SeriesInstanceUID", "")),
                "instance_uid": str(getattr(dataset, "SOPInstanceUID", "")),
                "receive_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file_path": file_path,
            }
        except Exception as e:
            logger.error(f"DICOM 解析失敗: {file_path} — {e}", exc_info=True)
            self.status_changed.emit(f"DICOM 解析失敗: {e}")
            return 0xC002

        # ---- 發送 Signal 給主執行緒 ----
        logger.debug(f"發送 dicom_received signal — PatientID: {metadata['patient_id']}, Instance: {metadata['instance_uid']}")
        self.dicom_received.emit(metadata)

        return 0x0000  # Success

    def _handle_c_echo(self, event):
        """
        處理 C-ECHO 請求 (Verification)。
        回傳 0x0000 表示連線正常。
        """
        logger.info(f"收到 C-ECHO 請求 — 來自: {event.assoc.requestor.ae_title}")
        return 0x0000


# ==========================================
# 獨立測試 (需搭配 PyQt6 主迴圈)
# ==========================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    def on_dicom_received(metadata: dict):
        print("收到 DICOM 檔案:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")

    def on_status_changed(msg: str):
        print(f"[狀態] {msg}")

    worker = DicomScpWorker(port=11112)
    worker.dicom_received.connect(on_dicom_received)
    worker.status_changed.connect(on_status_changed)
    worker.start()

    print("SCP Worker 執行中，按 Ctrl+C 停止...")

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        worker.stop()
        worker.wait()
        print("已停止")
