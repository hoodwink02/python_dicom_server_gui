import io
import numpy as np
from pydicom import dcmread
from PyQt6.QtGui import QImage, QPixmap

import matplotlib
matplotlib.use("Agg")  # 非互動式後端，避免與 PyQt 衝突
import matplotlib.pyplot as plt

from logger_config import setup_logger

logger = setup_logger("dicom_app")

# 標準 12 導程名稱
STANDARD_12_LEAD = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]


def load_ecg_as_pixmap(file_path: str, width: int = 1200, height: int = 900) -> QPixmap:
    """
    讀取 DICOM ECG 檔案，繪製波形圖並轉換為 QPixmap。

    :param file_path: DICOM ECG 檔案的完整路徑
    :param width: 輸出圖片寬度 (像素)
    :param height: 輸出圖片高度 (像素)
    :return: 波形圖的 QPixmap
    :raises ValueError: 當檔案不含波形資料時拋出
    """
    logger.debug(f"讀取 ECG DICOM 檔案: {file_path}")
    ds = dcmread(file_path)

    if "WaveformSequence" not in ds:
        raise ValueError("此 DICOM 檔案不含波形資料 (WaveformSequence)")

    waveform = ds.WaveformSequence[0]
    num_channels = int(waveform.NumberOfWaveformChannels)
    num_samples = int(waveform.NumberOfWaveformSamples)
    sampling_freq = float(waveform.SamplingFrequency)

    logger.debug(f"ECG — {num_channels} 導程, {num_samples} 取樣點, {sampling_freq} Hz")

    # ---- 解析波形資料 ----
    # WaveformData 為 raw bytes，根據 WaveformBitsAllocated 解碼
    bits = int(waveform.WaveformBitsAllocated)
    if bits == 16:
        dtype = np.int16
    elif bits == 32:
        dtype = np.int32
    else:
        dtype = np.int16

    raw_data = np.frombuffer(waveform.WaveformData, dtype=dtype).copy()
    # 重塑為 (samples, channels)
    waveform_data = raw_data.reshape(num_samples, num_channels).astype(np.float64)

    # ---- 套用 Channel Sensitivity (校正) ----
    channel_defs = waveform.ChannelDefinitionSequence
    channel_names = []
    for i, ch_def in enumerate(channel_defs):
        # 取得導程名稱
        source = getattr(ch_def, "ChannelSourceSequence", None)
        if source and len(source) > 0:
            name = str(getattr(source[0], "CodeMeaning", f"Ch{i+1}"))
        else:
            name = f"Ch{i+1}"
        # 簡化名稱 (去掉 "Lead " 前綴)
        name = name.replace("Lead ", "")
        channel_names.append(name)

        # 套用 sensitivity
        sensitivity = float(getattr(ch_def, "ChannelSensitivity", 1))
        correction = float(getattr(ch_def, "ChannelSensitivityCorrectionFactor", 1))
        baseline = float(getattr(ch_def, "ChannelBaseline", 0))
        waveform_data[:, i] = (waveform_data[:, i].astype(np.float64) + baseline) * sensitivity * correction

    # ---- 時間軸 ----
    duration = num_samples / sampling_freq
    time_axis = np.linspace(0, duration, num_samples)

    # ---- 繪製波形圖 ----
    dpi = 100
    fig_w = width / dpi
    fig_h = height / dpi

    fig, axes = plt.subplots(num_channels, 1, figsize=(fig_w, fig_h), dpi=dpi, sharex=True)
    fig.patch.set_facecolor("#263238")

    if num_channels == 1:
        axes = [axes]

    for i, ax in enumerate(axes):
        ax.plot(time_axis, waveform_data[:, i], color="#4fc3f7", linewidth=0.6)
        ax.set_facecolor("#263238")
        ax.set_ylabel(channel_names[i], fontsize=8, color="#e0e0e0", rotation=0,
                       labelpad=30, va="center")
        ax.tick_params(axis="both", colors="#90a4ae", labelsize=6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("#546e7a")
        ax.spines["left"].set_color("#546e7a")
        # 網格線 (模擬 ECG 紙)
        ax.grid(True, color="#37474f", linewidth=0.3, alpha=0.8)

    axes[-1].set_xlabel("Time (s)", fontsize=9, color="#e0e0e0")

    # 標題
    patient_name = str(getattr(ds, "PatientName", ""))
    patient_id = str(getattr(ds, "PatientID", ""))
    fig.suptitle(f"ECG — {patient_name} ({patient_id})", fontsize=11,
                 color="#ffffff", y=0.98)

    plt.tight_layout(rect=[0.05, 0.02, 1, 0.96])

    # ---- Figure → QPixmap ----
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    q_image = QImage()
    q_image.loadFromData(buf.read())
    return QPixmap.fromImage(q_image)


def is_ecg_dicom(file_path: str) -> bool:
    """
    快速判斷 DICOM 檔案是否為 ECG 類型。

    :param file_path: DICOM 檔案路徑
    :return: True 若為 ECG 類型
    """
    try:
        ds = dcmread(file_path, stop_before_pixels=True)
        modality = str(getattr(ds, "Modality", "")).upper()
        return modality == "ECG" or "WaveformSequence" in ds
    except Exception:
        return False
