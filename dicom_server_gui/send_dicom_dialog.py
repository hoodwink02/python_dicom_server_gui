import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QPushButton, QProgressBar, QFileDialog, QMessageBox,
    QTextEdit, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QHeaderView
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QFont

from dicom_scu_worker import DicomScuWorker, DicomEchoWorker
from logger_config import setup_logger

logger = setup_logger("dicom_app")

class DbSelectionDialog(QDialog):
    """從資料庫選擇檢查紀錄的對話框"""
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.selected_files = []
        self.setWindowTitle("從資料庫選擇檢查")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Patient ID", "Name", "Study UID", "Receive Date"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("確認選擇")
        self.btn_ok.setFixedHeight(30)
        self.btn_ok.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; border-radius: 4px; padding: 0 16px;")
        self.btn_ok.clicked.connect(self._on_ok)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setFixedHeight(30)
        self.btn_cancel.setStyleSheet("background-color: #757575; color: white; font-weight: bold; border-radius: 4px; padding: 0 16px;")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self._load_data()
        
    def _load_data(self):
        studies = self.db_manager.get_all_studies()
        self.table.setRowCount(len(studies))
        for row, study in enumerate(studies):
            self.table.setItem(row, 0, QTableWidgetItem(study.get('patient_id', '')))
            self.table.setItem(row, 1, QTableWidgetItem(study.get('patient_name', '')))
            
            uid_item = QTableWidgetItem(study.get('study_uid', ''))
            uid_item.setData(Qt.ItemDataRole.UserRole, study.get('study_uid', ''))
            self.table.setItem(row, 2, uid_item)
            
            self.table.setItem(row, 3, QTableWidgetItem(study.get('receive_date', '')))
            
    def _on_ok(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "提示", "請先選擇至少一筆檢查")
            return
            
        for idx in selected_rows:
            uid_item = self.table.item(idx.row(), 2)
            study_uid = uid_item.data(Qt.ItemDataRole.UserRole)
            paths = self.db_manager.get_file_paths_for_study(study_uid)
            self.selected_files.extend(paths)
            
        self.accept()



class SendDicomDialog(QDialog):
    """
    DICOM 傳送對話框。
    讓使用者設定遠端 SCP 資訊、選擇檔案並傳送。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scu_worker = None
        self.echo_worker = None
        
        # 取得資料庫管理器以載入 Peers
        self.db_manager = getattr(parent, "db_manager", None)
        if self.db_manager:
            self.saved_peers = self.db_manager.get_all_peers()
        else:
            self.saved_peers = []
            
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
        
        self.btn_delete_peer = QPushButton("🗑️ 刪除目前配置")
        self.btn_delete_peer.setFixedHeight(28)
        self.btn_delete_peer.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white;
                border: none; border-radius: 4px;
                padding: 0 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)
        self.btn_delete_peer.clicked.connect(self._delete_current_peer)
        row_peers.addWidget(self.btn_delete_peer)
        
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
        self.btn_select_files = QPushButton("📂  從本機選擇檔案")
        self.btn_select_files.setFixedHeight(32)
        self.btn_select_files.setStyleSheet("""
            QPushButton {
                background-color: #1976d2; color: white;
                border: none; border-radius: 4px;
                padding: 0 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        
        self.btn_select_db = QPushButton("🗄️  從資料庫選擇檔案")
        self.btn_select_db.setFixedHeight(32)
        self.btn_select_db.setStyleSheet("""
            QPushButton {
                background-color: #607d8b; color: white;
                border: none; border-radius: 4px;
                padding: 0 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #546e7a; }
        """)
        
        self.label_file_count = QLabel("尚未選擇檔案")
        file_row.addWidget(self.btn_select_files)
        file_row.addWidget(self.btn_select_db)
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
        self.btn_select_db.clicked.connect(self._select_from_db)
        self.btn_send.clicked.connect(self._start_send)
        self.btn_echo.clicked.connect(self._start_echo)
        self.btn_close.clicked.connect(self.close)

    # ==================================================================
    # Peer 配置儲存與載入
    # ==================================================================
    def _refresh_combo_peers(self):
        """重新從資料庫載入 Peers 並更新下拉選單"""
        if not self.db_manager:
            return
            
        self.saved_peers = self.db_manager.get_all_peers()
        self.combo_peers.blockSignals(True)
        self.combo_peers.clear()
        self.combo_peers.addItem("--- 請選擇或輸入新配置 ---")
        for p in self.saved_peers:
            self.combo_peers.addItem(f"{p['ae_title']}@{p['host']}:{p['port']}", p)
        self.combo_peers.blockSignals(False)

    def _save_current_peer(self):
        if not self.db_manager:
            QMessageBox.warning(self, "錯誤", "無法連接資料庫")
            return
            
        host = self.input_host.text().strip()
        port = self.input_remote_port.value()
        ae_title = self.input_remote_ae.text().strip()
        
        if not host or not ae_title:
            QMessageBox.warning(self, "錯誤", "Host 與 AE Title 不可為空")
            return
            
        success = self.db_manager.insert_peer(host, port, ae_title)
        
        if success:
            logger.info("已新增並儲存 DICOM Server 配置至資料庫")
            QMessageBox.information(self, "成功", "已儲存此 Peer 設定！")
            self._refresh_combo_peers()
            self.combo_peers.setCurrentIndex(self.combo_peers.count() - 1)
        else:
            QMessageBox.information(self, "提示", "此 Peer 已在儲存清單中。")

    def _delete_current_peer(self):
        if not self.db_manager:
            QMessageBox.warning(self, "錯誤", "無法連接資料庫")
            return
            
        index = self.combo_peers.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "請先選擇一個已儲存的配置")
            return
            
        peer_idx = index - 1
        if peer_idx < 0 or peer_idx >= len(self.saved_peers):
            QMessageBox.warning(self, "錯誤", "無法找到對應的配置紀錄")
            return
            
        peer = self.saved_peers[peer_idx]
        
        reply = QMessageBox.question(
            self, "確認刪除", 
            f"確定要刪除配置「{peer.get('ae_title')}@{peer.get('host')}:{peer.get('port')}」嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 從資料庫刪除
            deleted = self.db_manager.delete_peer(peer.get('host'), peer.get('port'), peer.get('ae_title'))
            if deleted > 0:
                self._refresh_combo_peers()
                self.combo_peers.setCurrentIndex(0)
                
                # 清空輸入框
                self.input_host.setText("127.0.0.1")
                self.input_remote_port.setValue(11112)
                self.input_remote_ae.setText("DICOM_SCP")
                QMessageBox.information(self, "成功", "已從資料庫刪除該配置")
            else:
                QMessageBox.warning(self, "錯誤", "刪除失敗，找不到該配置紀錄")

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
            self.label_file_count.setText(f"已從本機選擇 {len(file_paths)} 個檔案")
            self.btn_send.setEnabled(True)
            self.log_area.clear()
            self.progress_bar.setValue(0)

    def _select_from_db(self):
        parent_window = self.parent()
        if parent_window and hasattr(parent_window, "db_manager"):
            db_manager = parent_window.db_manager
        else:
            QMessageBox.warning(self, "錯誤", "無法取得資料庫連線")
            return
            
        dialog = DbSelectionDialog(db_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.selected_files:
                # 可以選擇附加或覆蓋。目前以覆蓋為例
                self.selected_files = dialog.selected_files
                self.label_file_count.setText(f"已從資料庫選擇 {len(self.selected_files)} 個檔案")
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
