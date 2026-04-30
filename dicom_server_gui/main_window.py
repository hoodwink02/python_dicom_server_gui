import sys
import os

from logger_config import setup_logger

logger = setup_logger("dicom_app")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel, QStatusBar,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog,
    QLineEdit, QSpinBox, QSlider, QScrollArea, QDialog, QTextEdit
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPixmap

from database_manager import DatabaseManager
from dicom_scp_worker import DicomScpWorker
from dicom_image_utils import load_dicom_as_pixmap, get_frame_count, is_pdf_dicom, extract_pdf_dicom, clear_dicom_cache
from ecg_utils import load_ecg_as_pixmap, is_ecg_dicom
from send_dicom_dialog import SendDicomDialog
from dicom_editor_dialog import DicomEditorDialog
from dicom_anonymize_dialog import DicomAnonymizeDialog


class MainWindow(QMainWindow):
    """
    DICOM 接收與管理系統的主視窗。

    佈局：
      - 頂部：啟動 / 停止 DICOM Server 按鈕
      - 左側：QTableWidget 顯示病患清單
      - 右側：QLabel 預留顯示 DICOM 影像
    """

    def __init__(self):
        super().__init__()

        # ---- 初始化核心元件 ----
        self.db_manager = DatabaseManager("dicom_local.db")
        self.scp_worker = None  # DicomScpWorker 實例 (啟動時建立)

        # ---- 建立 UI ----
        self._init_ui()

        # ---- 載入現有資料庫紀錄 ----
        self._refresh_patient_table()

    # ==================================================================
    # UI 初始化
    # ==================================================================
    def _init_ui(self):
        """建構並佈局所有 UI 元件"""
        self.setWindowTitle("DICOM 接收與管理系統")
        self.resize(1100, 650)

        # ---- 中央 Widget ----
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ---- 頂部控制列 ----
        control_layout = QHBoxLayout()

        input_style = """
            QLabel { font-weight: bold; font-size: 9pt; color: #212121; }
            QLineEdit, QSpinBox {
                border: 1px solid #bdbdbd; border-radius: 4px;
                padding: 4px 8px; font-size: 9pt;
                background-color: #ffffff; color: #212121;
            }
        """

        # -- AE Title 輸入 --
        ae_label = QLabel("AE Title:")
        ae_label.setStyleSheet(input_style)
        self.input_ae_title = QLineEdit("DICOM_SCP")
        self.input_ae_title.setFixedWidth(120)
        self.input_ae_title.setFixedHeight(30)
        self.input_ae_title.setStyleSheet(input_style)
        control_layout.addWidget(ae_label)
        control_layout.addWidget(self.input_ae_title)

        # -- Port 輸入 --
        port_label = QLabel("Port:")
        port_label.setStyleSheet(input_style)
        self.input_port = QSpinBox()
        self.input_port.setRange(1, 65535)
        self.input_port.setValue(11112)
        self.input_port.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.input_port.setFixedWidth(80)
        self.input_port.setFixedHeight(30)
        self.input_port.setStyleSheet(input_style)
        control_layout.addWidget(port_label)
        control_layout.addWidget(self.input_port)

        # -- 啟動按鈕 --
        self.btn_start = QPushButton("▶  啟動")
        self.btn_start.setFixedHeight(36)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white;
                border: none; border-radius: 4px;
                padding: 0 20px; font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #a5d6a7; }
        """)

        self.btn_stop = QPushButton("■  停止")
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white;
                border: none; border-radius: 4px;
                padding: 0 20px; font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background-color: #e53935; }
            QPushButton:disabled { background-color: #ef9a9a; }
        """)

        control_layout.addWidget(self.btn_start)
        control_layout.addWidget(self.btn_stop)
        control_layout.addStretch()

        # -- 開啟本地 DICOM 檔案按鈕 --
        self.btn_open = QPushButton("📂  開啟 DICOM 檔案")
        self.btn_open.setFixedHeight(36)
        self.btn_open.setStyleSheet("""
            QPushButton {
                background-color: #1976d2; color: white;
                border: none; border-radius: 4px;
                padding: 0 20px; font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background-color: #1565c0; }
        """)
        control_layout.addWidget(self.btn_open)

        # -- 刪除紀錄按鈕 --
        self.btn_delete = QPushButton("🗑  刪除紀錄")
        self.btn_delete.setFixedHeight(36)
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #757575; color: white;
                border: none; border-radius: 4px;
                padding: 0 20px; font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background-color: #616161; }
        """)
        control_layout.addWidget(self.btn_delete)

        # -- 傳送 DICOM 檔案按鈕 --
        self.btn_send = QPushButton("📤  傳送 DICOM")
        self.btn_send.setFixedHeight(36)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: #ff9800; color: white;
                border: none; border-radius: 4px;
                padding: 0 20px; font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background-color: #fb8c00; }
        """)
        control_layout.addWidget(self.btn_send)

        main_layout.addLayout(control_layout)

        # ---- 主內容區 (左右分割) ----
        content_layout = QHBoxLayout()

        # -- 左側：病患與檢查清單表格 --
        left_layout = QVBoxLayout()
        left_label = QLabel("檢查清單")
        left_label.setFont(QFont("Microsoft JhengHei", 12, QFont.Weight.Bold))
        left_layout.addWidget(left_label)

        self.table_patients = QTableWidget()
        self.table_patients.setColumnCount(3)
        self.table_patients.setHorizontalHeaderLabels(["Patient ID", "Name", "Receive Date"])
        self.table_patients.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_patients.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_patients.setAlternatingRowColors(True)
        self.table_patients.verticalHeader().setVisible(False)

        # 讓欄位自動撐滿
        header = self.table_patients.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.table_patients.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd; border-radius: 4px;
                gridline-color: #eee; font-size: 9pt;
                background-color: #ffffff; color: #212121;
                alternate-background-color: #f5f5f5;
            }
            QTableWidget::item {
                color: #212121; padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #1976d2; color: #ffffff;
            }
            QHeaderView::section {
                background-color: #37474f; color: white;
                padding: 6px; border: none; font-weight: bold;
            }
        """)

        left_layout.addWidget(self.table_patients)
        content_layout.addLayout(left_layout, stretch=3)

        # -- 右側：影像預覽區 (加入 QScrollArea 以支援大圖捲動) --
        right_layout = QVBoxLayout()
        right_header_layout = QHBoxLayout()
        
        right_label = QLabel("影像預覽")
        right_label.setFont(QFont("Microsoft JhengHei", 12, QFont.Weight.Bold))
        right_header_layout.addWidget(right_label)
        right_header_layout.addStretch()
        
        self.btn_view_tags = QPushButton("📋 DICOM 標籤")
        self.btn_view_tags.setFixedHeight(28)
        self.btn_view_tags.setStyleSheet("""
            QPushButton {
                background-color: #607d8b; color: white;
                border: none; border-radius: 4px;
                padding: 0 12px; font-weight: bold; font-size: 9pt;
            }
            QPushButton:hover { background-color: #546e7a; }
            QPushButton:disabled { background-color: #b0bec5; }
        """)
        self.btn_view_tags.setEnabled(False)
        self.btn_view_tags.clicked.connect(self._show_dicom_tags)
        right_header_layout.addWidget(self.btn_view_tags)
        
        self.btn_edit_tags = QPushButton("✏️ 編輯 DICOM")
        self.btn_edit_tags.setFixedHeight(28)
        self.btn_edit_tags.setStyleSheet("""
            QPushButton {
                background-color: #ff9800; color: white;
                border: none; border-radius: 4px;
                padding: 0 12px; font-weight: bold; font-size: 9pt;
            }
            QPushButton:hover { background-color: #fb8c00; }
            QPushButton:disabled { background-color: #ffcc80; }
        """)
        self.btn_edit_tags.setEnabled(False)
        self.btn_edit_tags.clicked.connect(self._open_dicom_editor)
        right_header_layout.addWidget(self.btn_edit_tags)
        
        self.btn_anonymize = QPushButton("👤 匿名化")
        self.btn_anonymize.setFixedHeight(28)
        self.btn_anonymize.setStyleSheet("""
            QPushButton {
                background-color: #3f51b5; color: white;
                border: none; border-radius: 4px;
                padding: 0 12px; font-weight: bold; font-size: 9pt;
            }
            QPushButton:hover { background-color: #3949ab; }
            QPushButton:disabled { background-color: #9fa8da; }
        """)
        self.btn_anonymize.setEnabled(False)
        self.btn_anonymize.clicked.connect(self._open_anonymizer)
        right_header_layout.addWidget(self.btn_anonymize)

        self.btn_delete_current = QPushButton("🗑 刪除單張")
        self.btn_delete_current.setFixedHeight(28)
        self.btn_delete_current.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white;
                border: none; border-radius: 4px;
                padding: 0 12px; font-weight: bold; font-size: 9pt;
            }
            QPushButton:hover { background-color: #e53935; }
            QPushButton:disabled { background-color: #ef9a9a; }
        """)
        self.btn_delete_current.setEnabled(False)
        self.btn_delete_current.clicked.connect(self._delete_current_image)
        right_header_layout.addWidget(self.btn_delete_current)
        
        right_layout.addLayout(right_header_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 2px dashed #546e7a; border-radius: 8px;
                background-color: #263238;
            }
        """)

        self.image_label = QLabel("尚未選擇影像")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.image_label.setOpenExternalLinks(False)
        self.image_label.linkActivated.connect(self._on_image_link_activated)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: transparent; color: #90a4ae;
                font-size: 11pt;
            }
        """)
        self.scroll_area.setWidget(self.image_label)
        right_layout.addWidget(self.scroll_area)

        # -- 幀導航控制列 (多幀影像時顯示) --
        self.frame_nav_widget = QWidget()
        frame_nav_layout = QHBoxLayout(self.frame_nav_widget)
        frame_nav_layout.setContentsMargins(0, 4, 0, 0)

        nav_btn_style = """
            QPushButton {
                background-color: #455a64; color: white;
                border: none; border-radius: 4px;
                padding: 4px 12px; font-weight: bold; font-size: 10pt;
            }
            QPushButton:hover { background-color: #37474f; }
        """

        self.btn_prev_frame = QPushButton("◀")
        self.btn_prev_frame.setFixedSize(36, 28)
        self.btn_prev_frame.setStyleSheet(nav_btn_style)

        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setValue(0)
        self.frame_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px; background: #546e7a; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #1976d2; width: 14px; margin: -4px 0;
                border-radius: 7px;
            }
        """)

        self.btn_next_frame = QPushButton("▶")
        self.btn_next_frame.setFixedSize(36, 28)
        self.btn_next_frame.setStyleSheet(nav_btn_style)

        self.label_frame_info = QLabel("1 / 1")
        self.label_frame_info.setFixedWidth(60)
        self.label_frame_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_frame_info.setStyleSheet("font-size: 9pt; color: #212121;")

        frame_nav_layout.addWidget(self.btn_prev_frame)
        frame_nav_layout.addWidget(self.frame_slider)
        frame_nav_layout.addWidget(self.btn_next_frame)
        frame_nav_layout.addWidget(self.label_frame_info)

        self.frame_nav_widget.setVisible(False)  # 預設隱藏
        right_layout.addWidget(self.frame_nav_widget)

        content_layout.addLayout(right_layout, stretch=4)
        main_layout.addLayout(content_layout)

        # ---- 狀態列 ----
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就緒 — DICOM Server 尚未啟動")

        # ---- 綁定按鈕事件 ----
        self.btn_start.clicked.connect(self._start_server)
        self.btn_stop.clicked.connect(self._stop_server)
        self.btn_open.clicked.connect(self._open_dicom_file)
        self.btn_delete.clicked.connect(self._delete_selected_patient)
        self.btn_send.clicked.connect(self._open_send_dialog)
        self.table_patients.cellClicked.connect(self._on_patient_clicked)

        # 幀導航事件
        self.btn_prev_frame.clicked.connect(self._prev_frame)
        self.btn_next_frame.clicked.connect(self._next_frame)
        self.frame_slider.valueChanged.connect(self._on_frame_slider_changed)

        # 記錄當前顯示的檔案路徑與幀資訊
        self._current_file_path = ""
        self._current_frame_count = 1

    # ==================================================================
    # 傳送 DICOM
    # ==================================================================
    def _open_send_dialog(self):
        """開啟 DICOM 傳送對話框"""
        logger.info("使用者開啟 DICOM 傳送對話框")
        dialog = SendDicomDialog(self)
        dialog.exec()

    # ==================================================================
    # Server 控制
    # ==================================================================
    def _start_server(self):
        """啟動 DICOM SCP Worker 執行緒"""
        if self.scp_worker is not None and self.scp_worker.isRunning():
            return

        logger.info("使用者點擊啟動 DICOM Server")

        port = self.input_port.value()
        ae_title = self.input_ae_title.text().strip() or "DICOM_SCP"

        self.scp_worker = DicomScpWorker(port=port, ae_title=ae_title)
        # 連接 Signal
        self.scp_worker.dicom_received.connect(self._on_dicom_received)
        self.scp_worker.status_changed.connect(self._on_status_changed)
        self.scp_worker.start()

        # 更新按鈕狀態 (啟動後鎖定輸入欄位)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.input_port.setEnabled(False)
        self.input_ae_title.setEnabled(False)

    def _stop_server(self):
        """停止 DICOM SCP Worker 執行緒"""
        logger.info("使用者點擊停止 DICOM Server")
        if self.scp_worker is not None:
            self.scp_worker.stop()
            self.scp_worker.wait()  # 等待執行緒結束
            self.scp_worker = None

        # 更新按鈕狀態 (停止後解鎖輸入欄位)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.input_port.setEnabled(True)
        self.input_ae_title.setEnabled(True)

    def _open_dicom_file(self):
        """
        開啟檔案對話框，讓使用者選取本地的 DICOM 檔案。
        選取後讀取 metadata、寫入 DB、更新表格並顯示影像。
        """
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "選取 DICOM 檔案", "",
            "DICOM Files (*.dcm *.DCM);;All Files (*)",
        )
        if not file_paths:
            return

        logger.info(f"使用者開啟 {len(file_paths)} 個本地 DICOM 檔案")

        from datetime import datetime
        from pydicom import dcmread

        for fp in file_paths:
            try:
                ds = dcmread(fp)
                metadata = {
                    "patient_id": str(getattr(ds, "PatientID", "")),
                    "patient_name": str(getattr(ds, "PatientName", "")),
                    "study_uid": str(getattr(ds, "StudyInstanceUID", "")),
                    "series_uid": str(getattr(ds, "SeriesInstanceUID", "")),
                    "instance_uid": str(getattr(ds, "SOPInstanceUID", "")),
                    "receive_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "file_path": os.path.abspath(fp),
                }
                # 寫入資料庫
                self.db_manager.insert_record(**metadata)
                logger.info(f"已匯入本地檔案: {fp}")
            except Exception as e:
                logger.error(f"讀取本地 DICOM 失敗: {fp} — {e}", exc_info=True)

        # 刷新表格
        self._refresh_patient_table()

        # 顯示最後一個檔案的影像
        last_path = os.path.abspath(file_paths[-1])
        try:
            frames = get_frame_count(last_path)
            self._study_frames = [(last_path, i) for i in range(frames)]
        except Exception:
            self._study_frames = [(last_path, 0)]

        self._current_frame_count = len(self._study_frames)
        self._update_frame_nav(0)
        self._load_frame(0)
        self.btn_view_tags.setEnabled(True)
        self.btn_edit_tags.setEnabled(True)
        self.btn_anonymize.setEnabled(True)
        self.btn_delete_current.setEnabled(True)
        self.status_bar.showMessage(f"已開啟 {len(file_paths)} 個檔案 — 顯示: {last_path}")

    def _delete_selected_patient(self):
        """
        刪除目前在表格中選取的檢查紀錄。
        會彈出確認對話框，防止誤刪。
        """
        selected_rows = self.table_patients.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "提示", "請先在左側表格中選取要刪除的檢查。")
            return

        row = selected_rows[0].row()
        patient_id = self.table_patients.item(row, 0).text()
        patient_name = self.table_patients.item(row, 1).text()
        study_uid = self.table_patients.item(row, 0).data(Qt.ItemDataRole.UserRole)

        # 確認對話框
        reply = QMessageBox.question(
            self, "確認刪除",
            f"確定要刪除病患「{patient_name}」(ID: {patient_id}) 的此筆檢查所有紀錄嗎？\n此操作無法復原。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        dicom_files_dir = os.path.abspath("dicom_files")

        file_paths = self.db_manager.get_file_paths_for_study(study_uid)
        for path in file_paths:
            if os.path.exists(path):
                # 判斷是否為內部 (SCP 接收) 檔案。外部匯入的檔案不刪除實體檔案
                try:
                    is_internal = os.path.commonpath([dicom_files_dir, os.path.abspath(path)]) == dicom_files_dir
                except ValueError:
                    is_internal = False

                if is_internal:
                    try:
                        os.remove(path)
                        logger.info(f"已刪除實體檔案: {path}")
                    except Exception as e:
                        logger.error(f"刪除檔案失敗 {path}: {e}")
                else:
                    logger.info(f"保留外部實體檔案: {path}")

        deleted = self.db_manager.delete_by_study_uid(study_uid)
        logger.info(f"使用者刪除檢查 {study_uid} — 共 {deleted} 筆紀錄")

        # 刷新表格與影像區
        self._refresh_patient_table()
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("尚未選擇影像")
        self.btn_view_tags.setEnabled(False)
        self.btn_edit_tags.setEnabled(False)
        self.btn_anonymize.setEnabled(False)
        self.btn_delete_current.setEnabled(False)
        self.frame_nav_widget.setVisible(False)
        self._current_file_path = ""
        self.status_bar.showMessage(f"已刪除檢查的 {deleted} 筆紀錄及實體檔案")

    # ==================================================================
    # Signal 處理 (Slot)
    # ==================================================================
    def _on_dicom_received(self, metadata: dict):
        """
        當 SCP Worker 成功接收並解析一筆 DICOM 檔案時觸發。
        1. 寫入 SQLite 資料庫
        2. 刷新病患清單表格
        """
        # 寫入資料庫
        self.db_manager.insert_record(
            patient_id=metadata["patient_id"],
            patient_name=metadata["patient_name"],
            study_uid=metadata["study_uid"],
            series_uid=metadata["series_uid"],
            instance_uid=metadata["instance_uid"],
            receive_date=metadata["receive_date"],
            file_path=metadata["file_path"],
        )

        # 刷新表格
        self._refresh_patient_table()

        self.status_bar.showMessage(
            f"已接收: {metadata['patient_name']} ({metadata['patient_id']})"
        )

    def _on_status_changed(self, message: str):
        """更新狀態列文字"""
        logger.info(f"SCP 狀態變更: {message}")
        self.status_bar.showMessage(message)

    def _on_patient_clicked(self, row: int, column: int):
        """
        當使用者點擊病患清單中的某一列時觸發。
        從資料庫查詢該筆檢查所有影像的檔案路徑，
        解析幀數後讀取 DICOM 影像並顯示在右側。
        """
        patient_id_item = self.table_patients.item(row, 0)
        if patient_id_item is None:
            return

        patient_id = patient_id_item.text()
        study_uid = patient_id_item.data(Qt.ItemDataRole.UserRole)

        # 查詢該檢查的所有檔案路徑
        file_paths = self.db_manager.get_file_paths_for_study(study_uid)
        if not file_paths:
            logger.warning(f"選取檢查: {study_uid}, 尚無對應檔案")
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText(f"病患: {patient_id}\n\n尚無對應檔案")
            self.frame_nav_widget.setVisible(False)
            return

        logger.info(f"選取檢查: {study_uid}, 共展開 {len(file_paths)} 個檔案")

        # 建立此檢查所有幀的清單
        self._study_frames = []
        for fp in file_paths:
            try:
                if is_pdf_dicom(fp) or is_ecg_dicom(fp):
                    self._study_frames.append((fp, 0))
                else:
                    frames = get_frame_count(fp)
                    for i in range(frames):
                        self._study_frames.append((fp, i))
            except Exception as e:
                logger.error(f"讀取檔案幀數失敗: {fp} — {e}")
                self._study_frames.append((fp, 0))

        if not self._study_frames:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("無法解析此檢查的所有檔案")
            self.frame_nav_widget.setVisible(False)
            return

        self._current_frame_count = len(self._study_frames)

        # 更新幀導航 UI
        self._update_frame_nav(0)

        # 載入第一幀
        self._load_frame(0)
        self.btn_view_tags.setEnabled(True)
        self.btn_edit_tags.setEnabled(True)
        self.btn_anonymize.setEnabled(True)
        self.btn_delete_current.setEnabled(True)

    def _delete_current_image(self):
        """刪除當下顯示的 DICOM 單一實體檔案與資料庫紀錄"""
        if not getattr(self, "_current_file_path", ""):
            return

        file_path = self._current_file_path
        
        reply = QMessageBox.question(
            self, "確認刪除單張",
            f"確定要永久刪除這張影像嗎？\n(若為多幀動態片段，整個動畫檔皆將被移除)\n檔案: {os.path.basename(file_path)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # 1. 刪除實體檔案 (僅限內部檔案)
        dicom_files_dir = os.path.abspath("dicom_files")
        if os.path.exists(file_path):
            try:
                is_internal = os.path.commonpath([dicom_files_dir, os.path.abspath(file_path)]) == dicom_files_dir
            except ValueError:
                is_internal = False

            if is_internal:
                try:
                    os.remove(file_path)
                    logger.info(f"已刪除實體檔案: {file_path}")
                except Exception as e:
                    logger.error(f"刪除實體檔案失敗 {file_path}: {e}")
                    QMessageBox.warning(self, "錯誤", f"無法刪除實體檔案: {e}")
                    return
            else:
                logger.info(f"保留外部實體檔案: {file_path}")

        # 2. 刪除資料庫紀錄
        self.db_manager.delete_by_file_path(file_path)
        
        # 3. 重新載入或刷新介面
        self.status_bar.showMessage(f"已刪除單張影像: {os.path.basename(file_path)}")
        
        study_uid = ""
        selected_rows = self.table_patients.selectionModel().selectedRows()
        if selected_rows:
            study_uid = self.table_patients.item(selected_rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            
        self._refresh_patient_table()
        
        row_to_select = -1
        for row in range(self.table_patients.rowCount()):
            if self.table_patients.item(row, 0).data(Qt.ItemDataRole.UserRole) == study_uid:
                row_to_select = row
                break
                
        if row_to_select >= 0:
            self.table_patients.selectRow(row_to_select)
            self._on_patient_clicked(row_to_select, 0)
        else:
            # 整個檢查都被刪掉了 (代表剛剛刪除的是該檢查的最後一張)
            self.image_label.clear()
            self.image_label.setText("尚未選擇影像")
            self.frame_nav_widget.setVisible(False)
            self.btn_view_tags.setEnabled(False)
            self.btn_edit_tags.setEnabled(False)
            self.btn_anonymize.setEnabled(False)
            self.btn_delete_current.setEnabled(False)

    def _load_frame(self, frame_index: int):
        """載入指定幀並顯示"""
        if not hasattr(self, "_study_frames") or not self._study_frames:
            return
        if frame_index < 0 or frame_index >= len(self._study_frames):
            return

        file_path, file_frame = self._study_frames[frame_index]
        self._current_file_path = file_path

        try:
            # 偵測 PDF 類型
            if is_pdf_dicom(file_path):
                self._is_ecg_current = False
                self._current_pixmap = QPixmap()
                self.image_label.clear()
                self.image_label.setText(
                    f'<div style="text-align:center;">'
                    f'<h2 style="color: #b0bec5; font-size: 14pt;">此為封裝 PDF 文件</h2>'
                    f'<br><a href="open_pdf" style="color: #64b5f6; font-size: 12pt; font-weight: bold; text-decoration: none;">📄 點擊外部開啟 PDF</a>'
                    f'</div>'
                )
                self.status_bar.showMessage(f"顯示文件: {file_path}")
                return

            # 偵測 ECG 類型
            if is_ecg_dicom(file_path):
                pixmap = load_ecg_as_pixmap(file_path)
                self._is_ecg_current = True
                self._display_pixmap(pixmap)
                self.status_bar.showMessage(f"顯示 ECG 波形: {file_path}")
                return

            self._is_ecg_current = False
            pixmap = load_dicom_as_pixmap(file_path, file_frame)
            self._display_pixmap(pixmap)
            self.status_bar.showMessage(
                f"顯示影像: {file_path}"
                + (f" (幀 {frame_index + 1}/{self._current_frame_count})"
                   if self._current_frame_count > 1 else "")
            )
        except Exception as e:
            logger.error(f"無法載入影像: {file_path} — {e}", exc_info=True)
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText(f"無法載入影像\n\n{e}")

    def _update_frame_nav(self, frame_index: int):
        """更新幀導航控制列的狀態"""
        if self._current_frame_count > 1:
            self.frame_nav_widget.setVisible(True)
            self.frame_slider.blockSignals(True)
            self.frame_slider.setMaximum(self._current_frame_count - 1)
            self.frame_slider.setValue(frame_index)
            self.frame_slider.blockSignals(False)
            self.label_frame_info.setText(f"{frame_index + 1} / {self._current_frame_count}")
        else:
            self.frame_nav_widget.setVisible(False)

    def _prev_frame(self):
        """切換到上一幀"""
        current = self.frame_slider.value()
        if current > 0:
            self.frame_slider.setValue(current - 1)

    def _next_frame(self):
        """切換到下一幀"""
        current = self.frame_slider.value()
        if current < self._current_frame_count - 1:
            self.frame_slider.setValue(current + 1)

    def _on_frame_slider_changed(self, value: int):
        """滑桿數值改變時載入對應幀"""
        self.label_frame_info.setText(f"{value + 1} / {self._current_frame_count}")
        self._load_frame(value)

    def _on_image_link_activated(self, link: str):
        """處理 Label 中的超連結點擊，例如開啟 PDF"""
        if link == "open_pdf" and getattr(self, "_current_file_path", ""):
            import tempfile, hashlib
            temp_dir = tempfile.gettempdir()
            file_hash = hashlib.md5(self._current_file_path.encode()).hexdigest()
            pdf_path = os.path.join(temp_dir, f"dicom_doc_{file_hash}.pdf")
            try:
                extract_pdf_dicom(self._current_file_path, pdf_path)
                os.startfile(pdf_path)
                self.status_bar.showMessage(f"已從外部開啟 PDF: {pdf_path}")
                logger.info(f"開啟外部 PDF: {pdf_path}")
            except Exception as e:
                logger.error(f"無法開啟 PDF: {e}")
                QMessageBox.warning(self, "錯誤", f"無法開啟 PDF:\\n{e}")

    def _show_dicom_tags(self):
        """開啟浮動視窗顯示當前 DICOM 檔案的完整 Tag 資訊"""
        if getattr(self, "_current_file_path", ""):
            from pydicom import dcmread
            try:
                ds = dcmread(self._current_file_path)
                
                dialog = QDialog(self)
                dialog.setWindowTitle(f"DICOM Tags - {os.path.basename(self._current_file_path)}")
                dialog.resize(700, 600)
                
                layout = QVBoxLayout(dialog)
                text_edit = QTextEdit()
                text_edit.setReadOnly(True)
                
                # pydicom 自帶良好的 __str__ 序列化輸出
                text_edit.setPlainText(str(ds))
                
                # 設定等寬字型 (Consolas 等) 以對齊
                font = QFont("Consolas", 10)
                font.setStyleHint(QFont.StyleHint.Monospace)
                text_edit.setFont(font)
                text_edit.setStyleSheet("background-color: #fafafa; color: #111; line-height: 1.2;")
                
                layout.addWidget(text_edit)
                dialog.exec()
            except Exception as e:
                logger.error(f"無法讀取 DICOM 標籤: {e}")
                QMessageBox.warning(self, "讀取錯誤", f"無法讀取 DICOM 標籤：\\n{e}")

    def _open_dicom_editor(self):
        """開啟 DICOM 編輯器，若有儲存則清除快取與更新"""
        if getattr(self, "_current_file_path", ""):
            dialog = DicomEditorDialog(self._current_file_path, self)
            if dialog.exec():
                # 編輯完成後，因為檔案內容被修改，需要清除這份快取
                clear_dicom_cache()
                
                # 若 Patient ID 有變動或有新資料，將 metadata 重新寫入 DB
                try:
                    from pydicom import dcmread
                    from datetime import datetime
                    ds = dcmread(self._current_file_path)
                    metadata = {
                        "patient_id": str(getattr(ds, "PatientID", "")),
                        "patient_name": str(getattr(ds, "PatientName", "")),
                        "study_uid": str(getattr(ds, "StudyInstanceUID", "")),
                        "series_uid": str(getattr(ds, "SeriesInstanceUID", "")),
                        "instance_uid": str(getattr(ds, "SOPInstanceUID", "")),
                        "receive_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "file_path": self._current_file_path,
                    }
                    self.db_manager.insert_record(**metadata)
                except Exception as e:
                    logger.error(f"編輯後更新 DB 失敗: {e}")

                # 重新整理畫面
                self._refresh_patient_table()
                self._load_frame(self.frame_slider.value())

    def _open_anonymizer(self):
        """開啟 DICOM 匿名化工具，若有儲存則清除快取與更新"""
        if getattr(self, "_current_file_path", ""):
            dialog = DicomAnonymizeDialog(self._current_file_path, self)
            if dialog.exec():
                clear_dicom_cache()
                
                try:
                    from pydicom import dcmread
                    from datetime import datetime
                    ds = dcmread(self._current_file_path)
                    metadata = {
                        "patient_id": str(getattr(ds, "PatientID", "")),
                        "patient_name": str(getattr(ds, "PatientName", "")),
                        "study_uid": str(getattr(ds, "StudyInstanceUID", "")),
                        "series_uid": str(getattr(ds, "SeriesInstanceUID", "")),
                        "instance_uid": str(getattr(ds, "SOPInstanceUID", "")),
                        "receive_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "file_path": self._current_file_path,
                    }
                    self.db_manager.insert_record(**metadata)
                except Exception as e:
                    logger.error(f"匿名化後更新 DB 失敗: {e}")

                self._refresh_patient_table()
                self._load_frame(self.frame_slider.value())

    # ==================================================================
    # 影像顯示
    # ==================================================================
    def _display_pixmap(self, pixmap: QPixmap):
        """
        將原始 QPixmap 儲存，並觸發縮放顯示。
        """
        self._current_pixmap = pixmap
        self._scale_and_set_pixmap()

    def _scale_and_set_pixmap(self):
        """
        根據 image_label 的當前大小，將 _current_pixmap 等比縮放後顯示。
        若是 ECG 波形圖，則不強制縮放，讓 ScrollArea 發揮作用。
        """
        if getattr(self, "_current_pixmap", None) is None or self._current_pixmap.isNull():
             return

        # ECG 不強制縮放至小視窗
        if getattr(self, "_is_ecg_current", False):
             self.image_label.setPixmap(self._current_pixmap)
             self.image_label.setFixedSize(self._current_pixmap.size())
             return

        # 一般影像：根據 ScrollArea 可視大小縮放，而非 image_label 目前大小
        area_size = self.scroll_area.viewport().size()
        target_size = QSize(area_size.width() - 4, area_size.height() - 4)

        if target_size.width() <= 0 or target_size.height() <= 0:
             return

        scaled = self._current_pixmap.scaled(
             target_size,
             Qt.AspectRatioMode.KeepAspectRatio,
             Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setFixedSize(scaled.size())
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        """視窗大小改變時，重新縮放顯示中的影像"""
        super().resizeEvent(event)
        self._scale_and_set_pixmap()

    # ==================================================================
    # 資料操作
    # ==================================================================
    def _refresh_patient_table(self):
        """從資料庫重新載入檢查清單並更新表格"""
        studies = self.db_manager.get_all_studies()

        self.table_patients.setRowCount(len(studies))
        for row, study in enumerate(studies):
            item_id = QTableWidgetItem(study.get("patient_id", ""))
            item_id.setData(Qt.ItemDataRole.UserRole, study.get("study_uid", ""))
            self.table_patients.setItem(row, 0, item_id)
            self.table_patients.setItem(row, 1, QTableWidgetItem(study.get("patient_name", "")))
            self.table_patients.setItem(row, 2, QTableWidgetItem(study.get("receive_date", "")))



    # ==================================================================
    # 視窗關閉
    # ==================================================================
    def closeEvent(self, event):
        """關閉視窗時確保 SCP Worker 也一併停止"""
        if self.scp_worker is not None and self.scp_worker.isRunning():
            self.scp_worker.stop()
            self.scp_worker.wait()
        event.accept()


# ==========================================
# 程式進入點
# ==========================================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 全域字型設定
    app.setFont(QFont("Microsoft JhengHei", 10))

    # 全域深色主題樣式
    app.setStyleSheet("""
        QMainWindow {
            background-color: #fafafa;
        }
        QStatusBar {
            background-color: #37474f;
            color: white;
            font-size: 9pt;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
