import os
from PyQt6.QtCore import QThread, pyqtSignal
from pynetdicom import AE
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
from pynetdicom.sop_class import Verification

from logger_config import setup_logger

logger = setup_logger("dicom_app")

# 支援的 Transfer Syntax 列表 (涵蓋常見壓縮/非壓縮格式)
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


class DicomScuWorker(QThread):
    """
    DICOM SCU 工作執行緒。
    在 QThread 中執行 C-STORE 請求，將本地 DICOM 檔案傳送至遠端 SCP。
    """

    # ---- PyQt Signals ----
    progress = pyqtSignal(int, int, str)
    finished_sending = pyqtSignal(int, int)
    status_changed = pyqtSignal(str)

    def __init__(self, file_paths: list, remote_host: str, remote_port: int,
                 remote_ae_title: str, local_ae_title: str = "DICOM_SCU",
                 parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.remote_ae_title = remote_ae_title
        self.local_ae_title = local_ae_title

    def run(self):
        """執行 C-STORE 傳送"""
        total = len(self.file_paths)
        success_count = 0
        fail_count = 0

        logger.info(
            f"開始傳送 {total} 個 DICOM 檔案 → "
            f"{self.remote_ae_title}@{self.remote_host}:{self.remote_port}"
        )
        self.status_changed.emit(f"正在連線至 {self.remote_host}:{self.remote_port}...")

        # 建立 Application Entity
        ae = AE(ae_title=self.local_ae_title)

        # 先讀取所有檔案，解壓縮後收集需要的 SOP Class UID
        datasets = []
        sop_classes = set()
        for fp in self.file_paths:
            try:
                ds = dcmread(fp)
                # 若檔案為壓縮格式，解壓縮為原始像素 (Implicit VR Little Endian)
                if ds.file_meta.TransferSyntaxUID.is_compressed:
                    ds.decompress()
                    logger.debug(f"已解壓縮: {os.path.basename(fp)}")
                datasets.append((fp, ds))
                sop_classes.add(ds.SOPClassUID)
            except Exception as e:
                logger.error(f"讀取檔案失敗，跳過: {fp} — {e}")
                fail_count += 1

        # 只為實際需要的 SOP Class 加入 Presentation Context
        for sop_uid in sop_classes:
            ae.add_requested_context(sop_uid, [
                ImplicitVRLittleEndian,
                ExplicitVRLittleEndian,
            ])

        if not datasets:
            self.status_changed.emit("沒有可傳送的有效 DICOM 檔案")
            self.finished_sending.emit(0, fail_count)
            return

        # 建立連線 (Association)
        assoc = ae.associate(self.remote_host, self.remote_port,
                             ae_title=self.remote_ae_title)

        if not assoc.is_established:
            msg = f"無法連線至 {self.remote_ae_title}@{self.remote_host}:{self.remote_port}"
            logger.error(msg)
            self.status_changed.emit(msg)
            self.finished_sending.emit(0, total)
            return

        logger.info("Association 已建立，開始傳送...")

        # 逐檔傳送
        for idx, (fp, ds) in enumerate(datasets, start=1):
            filename = os.path.basename(fp)
            self.progress.emit(idx, total, filename)

            try:
                status = assoc.send_c_store(ds)
                if status and status.Status == 0x0000:
                    success_count += 1
                    logger.info(f"傳送成功 ({idx}/{total}): {filename}")
                else:
                    fail_count += 1
                    status_code = status.Status if status else "N/A"
                    logger.warning(f"傳送失敗 ({idx}/{total}): {filename}, Status: 0x{status_code:04X}")
            except Exception as e:
                fail_count += 1
                logger.error(f"傳送異常 ({idx}/{total}): {filename} — {e}")

        # 釋放連線
        assoc.release()
        logger.info(f"傳送完成 — 成功: {success_count}, 失敗: {fail_count}")

        self.status_changed.emit(f"傳送完成 — 成功: {success_count}, 失敗: {fail_count}")
        self.finished_sending.emit(success_count, fail_count)


class DicomEchoWorker(QThread):
    """
    DICOM ECHO 工作執行緒。
    在 QThread 中執行 C-ECHO 請求，測試與遠端 SCP 的連線。
    """
    
    # ---- PyQt Signals ----
    status_changed = pyqtSignal(str)
    finished_echo = pyqtSignal(bool, str)
    
    def __init__(self, remote_host: str, remote_port: int,
                 remote_ae_title: str, local_ae_title: str = "DICOM_SCU",
                 parent=None):
        super().__init__(parent)
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.remote_ae_title = remote_ae_title
        self.local_ae_title = local_ae_title
        
    def run(self):
        """執行 C-ECHO 測試"""
        logger.info(
            f"開始 C-ECHO 測試 → "
            f"{self.remote_ae_title}@{self.remote_host}:{self.remote_port}"
        )
        self.status_changed.emit(f"正在與 {self.remote_host}:{self.remote_port} 建立連線...")

        ae = AE(ae_title=self.local_ae_title)
        ae.add_requested_context(Verification)

        assoc = ae.associate(self.remote_host, self.remote_port,
                             ae_title=self.remote_ae_title)

        if not assoc.is_established:
            msg = f"無法連線至 {self.remote_ae_title}@{self.remote_host}:{self.remote_port}"
            logger.error(msg)
            self.status_changed.emit(msg)
            self.finished_echo.emit(False, msg)
            return

        self.status_changed.emit("連線已建立，發送 C-ECHO 請求...")
        
        status = assoc.send_c_echo()
        if status:
            if status.Status == 0x0000:
                msg = "C-ECHO 成功！連線正常。"
                logger.info(msg)
                self.status_changed.emit(msg)
                self.finished_echo.emit(True, msg)
            else:
                msg = f"C-ECHO 回應異常，Status: 0x{status.Status:04X}"
                logger.warning(msg)
                self.status_changed.emit(msg)
                self.finished_echo.emit(False, msg)
        else:
            msg = "C-ECHO 失敗 (Timeout 或未收到回應)"
            logger.error(msg)
            self.status_changed.emit(msg)
            self.finished_echo.emit(False, msg)

        assoc.release()
