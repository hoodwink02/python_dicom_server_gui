import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QPushButton, QProgressBar, QFileDialog, QMessageBox,
    QTextEdit, QComboBox
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QFont

from dicom_scu_worker import DicomScuWorker, DicomEchoWorker
from logger_config import setup_logger

logger = setup_logger("dicom_app")


class SendDicomDialog(QDialog):
    """
    DICOM 傳送對話框。
    讓使用者設定遠端 SCP 資訊、選擇檔案並傳送。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scu_worker = None
        self.echo_worker = None
        self.settings = QSettings("DicomApp", "SendPeers")
        self.saved_peers = self._load_peers_from_settings()
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("傳送 DICOM 檔案")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        style = """
            QDialog { background-color: #fafafa; }
            QLabel { font-size: 9pt; color: #212121; }
            QLineEdit, QSpinBox, QComboBox {
                border: 1px solid #bdbdbd; border-radius: 4px;
                padding: 4px 8px; font-size: 9pt;
                background-color: #ffffff; color: #212121;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff; color: #212121;
                selection-background-color: #1976d2;
                selection-color: #ffffff;
            }
        """
        self.setStyleSheet(style)

        # ---- 遠端 SCP 設定 ----
        title = QLabel("遠端 DICOM Server 設定")
        title.setFont(QFont("Microsoft JhengHei", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        # Saved Peers ComboBox
        row_peers = QHBoxLayout()
        row_peers.addWidget(QLabel("已儲存的配置:"))
        self.combo_peers = QComboBox()
        self.combo_peers.addItem("--- 請選擇或輸入新配置 ---")
        for p in self.saved_peers:
            self.combo_peers.addItem(f"{p['ae_title']}@{p['host']}:{p['port']}", p)
        self.combo_peers.currentIndexChanged.connect(self._on_peer_selected)
        row_peers.addWidget(self.combo_peers)
        
        self.btn_save_peer = QPushButton("💾 儲存目前配置")
        self.btn_save_peer.setFixedHeight(28)
        self.btn_save_peer.setStyleSheet("""
            QPushButton {
                background-color: #f57c00; color: white;
                border: none; border-radius: 4px;
                padding: 0 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #e65100; }
        """)
        self.btn_save_peer.clicked.connect(self._save_current_peer)
        row_peers.addWidget(self.btn_save_peer)
        
        layout.addLayout(row_peers)

        # Host
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Host / IP:"))
        self.input_host = QLineEdit("127.0.0.1")
        row1.addWidget(self.input_host)
        layout.addLayout(row1)

        # Port
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Port:"))
        self.input_remote_port = QSpinBox()
        self.input_remote_port.setRange(1, 65535)
        self.input_remote_port.setValue(11112)
        self.input_remote_port.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        row2.addWidget(self.input_remote_port)
        layout.addLayout(row2)

        # AE Title
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("AE Title:"))
        self.input_remote_ae = QLineEdit("DICOM_SCP")
        row3.addWidget(self.input_remote_ae)
        layout.addLayout(row3)

        # ---- 檔案選擇 ----
        file_row = QHBoxLayout()
        self.btn_select_files = QPushButton("📂  選擇 DICOM 檔案")
        self.btn_select_files.setFixedHeight(32)
        self.btn_select_files.setStyleSheet("""
            QPushButton {
                background-color: #1976d2; color: white;
                border: none; border-radius: 4px;
                padding: 0 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        self.label_file_count = QLabel("尚未選擇檔案")
        file_row.addWidget(self.btn_select_files)
        file_row.addWidget(self.label_file_count)
        file_row.addStretch()
        layout.addLayout(file_row)

        # ---- 進度條 ----
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m")
        layout.addWidget(self.progress_bar)

        # ---- 傳送日誌 ----
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(120)
        self.log_area.setStyleSheet("font-size: 8pt; background-color: #263238; color: #e0e0e0; border-radius: 4px;")
        layout.addWidget(self.log_area)

        # ---- 傳送與測試按鈕 ----
        btn_row = QHBoxLayout()
        
        self.btn_echo = QPushButton("📡  C-ECHO 測試")
        self.btn_echo.setFixedHeight(36)
        self.btn_echo.setStyleSheet("""
            QPushButton {
                background-color: #00bcd4; color: white;
                border: none; border-radius: 4px;
                padding: 0 24px; font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background-color: #00acc1; }
            QPushButton:disabled { background-color: #80deea; }
        """)
        
        self.btn_send = QPushButton("📤  開始傳送")
        self.btn_send.setFixedHeight(36)
        self.btn_send.setEnabled(False)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white;
                border: none; border-radius: 4px;
                padding: 0 24px; font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #a5d6a7; }
        """)
        self.btn_close = QPushButton("關閉")
        self.btn_close.setFixedHeight(36)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #757575; color: white;
                border: none; border-radius: 4px;
                padding: 0 24px; font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background-color: #616161; }
        """)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_echo)
        btn_row.addWidget(self.btn_send)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        # ---- 綁定事件 ----
        self.selected_files = []
        self.btn_select_files.clicked.connect(self._select_files)
        self.btn_send.clicked.connect(self._start_send)
        self.btn_echo.clicked.connect(self._start_echo)
        self.btn_close.clicked.connect(self.close)

    # ==================================================================
    # Peer 配置儲存與載入
    # ==================================================================
    def _load_peers_from_settings(self):
        peers_str = self.settings.value("peer_list", "[]")
        try:
            return json.loads(peers_str)
        except Exception:
            return []

    def _save_current_peer(self):
        host = self.input_host.text().strip()
        port = self.input_remote_port.value()
        ae_title = self.input_remote_ae.text().strip()
        
        if not host or not ae_title:
            QMessageBox.warning(self, "錯誤", "Host 與 AE Title 不可為空")
            return
            
        new_peer = {"host": host, "port": port, "ae_title": ae_title}
        
        # 檢查是否已存在
        existing_idx = -1
        for i, p in enumerate(self.saved_peers):
            if p["host"] == host and p["port"] == port and p["ae_title"] == ae_title:
                existing_idx = i
                break
                
        if existing_idx == -1:
            self.saved_peers.append(new_peer)
            self.combo_peers.addItem(f"{ae_title}@{host}:{port}", new_peer)
            self.settings.setValue("peer_list", json.dumps(self.saved_peers))
            QMessageBox.information(self, "成功", "已儲存此 Peer 設定！")
            self.combo_peers.setCurrentIndex(self.combo_peers.count() - 1)
        else:
            QMessageBox.information(self, "提示", "此 Peer 已在儲存清單中。")

    def _on_peer_selected(self, index):
        if index <= 0:
            return
        peer = self.combo_peers.itemData(index)
        if peer:
            self.input_host.setText(peer.get("host", ""))
            self.input_remote_port.setValue(peer.get("port", 11112))
            self.input_remote_ae.setText(peer.get("ae_title", ""))

    # ==================================================================
    # 檔案選擇
    # ==================================================================
    def _select_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "選擇要傳送的 DICOM 檔案", "",
            "DICOM Files (*.dcm *.DCM);;All Files (*)",
        )
        if file_paths:
            self.selected_files = file_paths
            self.label_file_count.setText(f"已選擇 {len(file_paths)} 個檔案")
            self.btn_send.setEnabled(True)
            self.log_area.clear()
            self.progress_bar.setValue(0)

    # ==================================================================
    # 傳送
    # ==================================================================
    def _start_send(self):
        if not self.selected_files:
            return

        host = self.input_host.text().strip()
        port = self.input_remote_port.value()
        ae_title = self.input_remote_ae.text().strip() or "DICOM_SCP"

        if not host:
            QMessageBox.warning(self, "錯誤", "請輸入 Host / IP")
            return

        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setValue(0)
        self.btn_send.setEnabled(False)
        self.btn_select_files.setEnabled(False)
        self.log_area.append(f"連線至 {ae_title}@{host}:{port}...")

        self.scu_worker = DicomScuWorker(
            file_paths=self.selected_files,
            remote_host=host,
            remote_port=port,
            remote_ae_title=ae_title,
        )
        self.scu_worker.progress.connect(self._on_progress)
        self.scu_worker.status_changed.connect(self._on_status)
        self.scu_worker.finished_sending.connect(self._on_finished)
        self.scu_worker.start()

    # ==================================================================
    # Signal Slots
    # ==================================================================
    def _on_progress(self, current: int, total: int, filename: str):
        self.progress_bar.setValue(current)
        self.log_area.append(f"[{current}/{total}] {filename}")

    def _on_status(self, message: str):
        self.log_area.append(message)

    def _on_finished(self, success: int, fail: int):
        self.btn_send.setEnabled(True)
        self.btn_echo.setEnabled(True)
        self.btn_select_files.setEnabled(True)
        self.log_area.append(f"\n完成 — 成功: {success}, 失敗: {fail}")
        logger.info(f"DICOM 傳送結束 — 成功: {success}, 失敗: {fail}")

    # ==================================================================
    # Echo
    # ==================================================================
    def _start_echo(self):
        host = self.input_host.text().strip()
        port = self.input_remote_port.value()
        ae_title = self.input_remote_ae.text().strip() or "DICOM_SCP"

        if not host:
            QMessageBox.warning(self, "錯誤", "請輸入 Host / IP")
            return

        self.btn_echo.setEnabled(False)
        self.btn_send.setEnabled(False)
        self.log_area.append(f"開始 Echo 測試連線至 {ae_title}@{host}:{port}...")

        self.echo_worker = DicomEchoWorker(
            remote_host=host,
            remote_port=port,
            remote_ae_title=ae_title,
        )
        self.echo_worker.status_changed.connect(self._on_status)
        self.echo_worker.finished_echo.connect(self._on_echo_finished)
        self.echo_worker.start()

    def _on_echo_finished(self, success: bool, message: str):
        self.btn_echo.setEnabled(True)
        if self.selected_files:
            self.btn_send.setEnabled(True)
