import logging
import os
from datetime import datetime


def setup_logger(name: str = "dicom_app", log_dir: str = "./logs",
                 level: int = logging.DEBUG) -> logging.Logger:
    """
    建立並回傳一個統一的 Logger 實例。
    同時輸出到 console 和日誌檔案。

    :param name: Logger 名稱
    :param log_dir: 日誌檔案存放資料夾
    :param level: 日誌等級 (預設 DEBUG)
    :return: 設定好的 Logger 實例
    """
    logger = logging.getLogger(name)

    # 避免重複添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # ---- 日誌格式 ----
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s.%(module)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ---- Console Handler ----
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ---- File Handler ----
    os.makedirs(log_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"dicom_app_{today}.log")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
