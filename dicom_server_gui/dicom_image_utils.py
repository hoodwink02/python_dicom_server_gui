import numpy as np
from pydicom import dcmread
from PyQt6.QtGui import QImage, QPixmap
from functools import lru_cache

from logger_config import setup_logger

logger = setup_logger("dicom_app")


@lru_cache(maxsize=2)
def _get_cached_dataset(file_path: str):
    logger.debug(f"從硬碟實際載入並快取 DICOM: {file_path}")
    return dcmread(file_path)

def clear_dicom_cache():
    """清除 dataset 快取，以便重新載入更新後的檔案"""
    _get_cached_dataset.cache_clear()


def load_dicom_as_pixmap(file_path: str, frame_index: int = 0) -> QPixmap:
    """
    讀取 DICOM 檔案並轉換為 PyQt6 QPixmap。

    處理流程：
      1. 使用 pydicom 讀取 pixel_array (透過 lru_cache 快取避免重複 I/O)
      2. 若為多幀影像，取指定 frame
      3. 套用 Rescale Slope / Intercept 轉換為 HU 值 (若有)
      4. 正規化至 0–255 (8-bit 灰階)
      5. 轉換為 QImage → QPixmap

    :param file_path: DICOM 檔案的完整路徑
    :param frame_index: 多幀影像時要顯示的幀索引，預設 0 (第一幀)
    :return: 可直接設給 QLabel 的 QPixmap 物件
    :raises ValueError: 當檔案不含影像資料時拋出
    """
    ds = _get_cached_dataset(file_path)

    # ---- 取得像素陣列 ----
    if "PixelData" not in ds:
        modality = str(getattr(ds, "Modality", "未知"))
        logger.warning(f"DICOM 檔案不含影像資料 (Modality: {modality}): {file_path}")
        raise ValueError(f"此 DICOM 檔案不含影像資料\n(Modality: {modality}，可能為 ECG、Structured Report 等非影像類型)")

    pixel_array = ds.pixel_array

    # ---- 判斷多幀影像 ----
    num_frames = int(getattr(ds, "NumberOfFrames", 1))
    samples_per_pixel = int(getattr(ds, "SamplesPerPixel", 1))

    if num_frames > 1:
        logger.debug(f"多幀影像 — 共 {num_frames} 幀, 顯示第 {frame_index} 幀")
        # 多幀: pixel_array shape = (frames, rows, cols) 或 (frames, rows, cols, channels)
        frame_index = min(frame_index, num_frames - 1)
        pixel_array = pixel_array[frame_index]

    # ---- 轉換為 float 做後續處理 ----
    pixel_array = pixel_array.astype(np.float64)

    # ---- 套用 Rescale Slope / Intercept (HU 轉換) ----
    slope = float(getattr(ds, "RescaleSlope", 1))
    intercept = float(getattr(ds, "RescaleIntercept", 0))
    logger.debug(f"HU 轉換 — Slope: {slope}, Intercept: {intercept}")
    pixel_array = pixel_array * slope + intercept

    # ---- 正規化至 0 ~ 255 ----
    pixel_min = pixel_array.min()
    pixel_max = pixel_array.max()

    if pixel_max - pixel_min == 0:
        normalized = np.zeros_like(pixel_array, dtype=np.uint8)
    else:
        normalized = ((pixel_array - pixel_min) / (pixel_max - pixel_min) * 255).astype(np.uint8)

    # ---- numpy array → QImage → QPixmap ----
    if normalized.ndim == 3 and samples_per_pixel >= 3:
        # RGB 彩色影像 (例如超音波彩色)
        height, width = normalized.shape[:2]
        logger.debug(f"彩色影像尺寸: {width}x{height}")
        bytes_per_line = 3 * width
        q_image = QImage(
            normalized.tobytes(), width, height,
            bytes_per_line, QImage.Format.Format_RGB888,
        )
    else:
        # 灰階影像 (最常見，含單幀或已取出的多幀)
        if normalized.ndim == 3:
            normalized = normalized[:, :, 0]  # 取第一通道
        height, width = normalized.shape[:2]
        logger.debug(f"灰階影像尺寸: {width}x{height}")
        bytes_per_line = width
        q_image = QImage(
            normalized.tobytes(), width, height,
            bytes_per_line, QImage.Format.Format_Grayscale8,
        )

    return QPixmap.fromImage(q_image)


def get_frame_count(file_path: str) -> int:
    """
    取得 DICOM 檔案的幀數。

    :param file_path: DICOM 檔案路徑
    :return: 幀數 (單幀影像回傳 1)
    """
    ds = _get_cached_dataset(file_path)
    return int(getattr(ds, "NumberOfFrames", 1))

def is_pdf_dicom(file_path: str) -> bool:
    """判斷 DICOM 是否為封裝的 PDF 文件"""
    ds = _get_cached_dataset(file_path)
    # 若有 EncapsulatedDocument 標籤且內容看似 PDF
    if "EncapsulatedDocument" in ds:
        mime_type = str(getattr(ds, "MIMETypeOfEncapsulatedDocument", ""))
        if "pdf" in mime_type.lower() or ds.EncapsulatedDocument.startswith(b"%PDF"):
            return True
    return False

def extract_pdf_dicom(file_path: str, out_path: str):
    """將 DICOM 中的 PDF 匯出到指定路徑"""
    ds = _get_cached_dataset(file_path)
    if "EncapsulatedDocument" in ds:
        with open(out_path, "wb") as f:
            f.write(ds.EncapsulatedDocument)

