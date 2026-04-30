import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QMessageBox, QLabel, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt
from pydicom import dcmread
from pydicom.tag import Tag

from logger_config import setup_logger

logger = setup_logger("dicom_app")

# 定義一鍵匿名化的可選標籤：(Group, Element, 介面名稱, 預設是否勾選, 替換的匿名值, VR)
ANONYMIZE_TARGETS = [
    (0x0010, 0x0010, "Patient Name (病患姓名)", True, "ANONYMOUS", "PN"),
    (0x0010, 0x0020, "Patient ID (病歷號/編碼)", True, "ANON_ID", "LO"),
    (0x0010, 0x0030, "Patient Birth Date (生日)", True, "", "DA"),
    (0x0010, 0x0040, "Patient Sex (性別)", True, "", "CS"),
    (0x0010, 0x1010, "Patient Age (年齡)", False, "", "AS"),
    (0x0010, 0x1030, "Patient Weight (體重)", False, "", "DS"),
    (0x0008, 0x0080, "Institution Name (機構名稱)", False, "ANONYMOUS_INST", "LO"),
    (0x0008, 0x0090, "Referring Physician (轉診醫師)", False, "ANONYMOUS_DOC", "PN"),
    (0x0008, 0x0050, "Accession Number (檢查次號)", False, "", "SH"),
]

class DicomAnonymizeDialog(QDialog):
    """
    DICOM 匿名化設定介面
    """
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"一鍵匿名化 DICOM - {os.path.basename(file_path)}")
        self.resize(350, 400)
        self.changes_saved = False

        try:
            self.ds = dcmread(file_path)
            self.original_patient_id = str(getattr(self.ds, "PatientID", ""))
        except Exception as e:
            logger.error(f"無法載入以進行匿名化：{file_path} - {e}")
            self.ds = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 頂部提示
        warning_label = QLabel(
            "請勾選您想要去識別化(匿名化)的欄位：\n"
            "※注意：若勾選修改 Patient ID，系統將認定為一名新患者。"
        )
        warning_label.setStyleSheet("color: #d32f2f; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(warning_label)

        # 快速選取按鈕
        sel_layout = QHBoxLayout()
        btn_sel_all = QPushButton("全部勾選")
        btn_sel_none = QPushButton("全部取消")
        btn_sel_all.clicked.connect(self._select_all)
        btn_sel_none.clicked.connect(self._select_none)
        
        btn_sel_all.setStyleSheet("padding: 4px 8px;")
        btn_sel_none.setStyleSheet("padding: 4px 8px;")

        sel_layout.addWidget(btn_sel_all)
        sel_layout.addWidget(btn_sel_none)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        # 選項群組
        group_box = QGroupBox("可匿名化屬性清單")
        grid_layout = QGridLayout()
        self.checkboxes = []

        for idx, item in enumerate(ANONYMIZE_TARGETS):
            group, elem, label_text, default_checked, val, vr = item
            cb = QCheckBox(label_text)
            cb.setChecked(default_checked)
            # 將變數存入 property，後續讀取修改
            cb.setProperty("target_tag", Tag((group, elem)))
            cb.setProperty("target_val", val)
            cb.setProperty("target_vr", vr)
            
            self.checkboxes.append(cb)
            grid_layout.addWidget(cb, idx, 0)

        group_box.setLayout(grid_layout)
        layout.addWidget(group_box)

        layout.addStretch()

        # 底部按鈕
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setStyleSheet("padding: 6px 16px; border-radius: 4px; background-color: #e0e0e0; font-weight: bold;")
        
        btn_apply = QPushButton("🛡️ 執行匿名化")
        btn_apply.clicked.connect(self._apply_anonymization)
        btn_apply.setStyleSheet("background-color: #3f51b5; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_apply)
        layout.addLayout(btn_layout)

    def _select_all(self):
        for cb in self.checkboxes:
            cb.setChecked(True)

    def _select_none(self):
        for cb in self.checkboxes:
            cb.setChecked(False)

    def _apply_anonymization(self):
        if self.ds is None:
            return

        modified_count = 0
        has_id_change = False

        for cb in self.checkboxes:
            if cb.isChecked():
                tag = cb.property("target_tag")
                target_val = cb.property("target_val")
                
                # 如果 Tag 存在 ds 內，就執行覆寫
                if tag in self.ds:
                    current_val_str = str(self.ds[tag].value)
                    # 比對是否真的需要改
                    if current_val_str != target_val:
                        self.ds[tag].value = target_val
                        modified_count += 1
                        
                        # 特殊偵測：若是 Patient ID
                        if tag == Tag((0x0010, 0x0020)):
                            has_id_change = True

        if modified_count == 0:
            QMessageBox.information(self, "提示", "依據您的勾選項目，檔案內原本即為匿名狀態或無該屬性，無須修改。")
            self.reject()
            return

        if has_id_change:
             reply = QMessageBox.question(
                 self, "Patient ID 變更確認", 
                 f"您勾選了匿名化 Patient ID。\n\n"
                 f"提醒您，儲存後系統將把此影像視為另一名【匿名患者】的全新紀錄。\n是否確定執行？",
                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                 QMessageBox.StandardButton.No
             )
             if reply == QMessageBox.StandardButton.No:
                 return

        try:
            self.ds.save_as(self.file_path)
            self.changes_saved = True
            logger.info(f"成功將 {self.file_path} 匿名化，移除了 {modified_count} 個機敏欄位")
            QMessageBox.information(self, "成功", f"匿名化成功！共清除了 {modified_count} 個機敏屬性！")
            self.accept()
        except Exception as e:
            logger.error(f"儲存匿名化 DICOM 時發生錯誤：{e}", exc_info=True)
            QMessageBox.critical(self, "存檔錯誤", f"無法儲存檔案：\n{e}")
