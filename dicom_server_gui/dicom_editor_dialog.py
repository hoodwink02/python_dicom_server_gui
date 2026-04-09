import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt
from pydicom import dcmread
from pydicom.tag import Tag
import pydicom

from logger_config import setup_logger

logger = setup_logger("dicom_app")

# 排除複雜且不適合純文字編輯的 VR 與特定標籤 (如 PixelData 影像資料)
EXCEPTION_VRS = {"OB", "OW", "OF", "OD", "SQ", "UN"}
EXCEPTION_TAGS = {(0x7fe0, 0x0010)} 

class DicomEditorDialog(QDialog):
    """
    DICOM 標籤編輯器介面
    """
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"編輯 DICOM - {os.path.basename(file_path)}")
        self.resize(800, 600)
        
        self.changes_saved = False
        self.original_patient_id = ""

        try:
            self.ds = dcmread(file_path)
            self.original_patient_id = str(getattr(self.ds, "PatientID", ""))
        except Exception as e:
            logger.error(f"無法載入以進行編輯：{file_path} - {e}")
            self.ds = None

        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # 標題及警告字眼
        warning_label = QLabel(
            "提示：僅支援編輯文字或單純數值型別標籤 (VR)。\n"
            "※注意：若修改 Patient ID 並儲存後，系統將認定為一名新病患。"
        )
        warning_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
        layout.addWidget(warning_label)

        # 標籤表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["標籤 (Tag)", "名稱 (Name)", "資料型態 (VR)", "數值 (Value)"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f5f5f5;
                font-family: Consolas, monospace;
                font-size: 10pt;
                background-color: #ffffff; color: #212121;
            }
            QTableWidget::item { padding: 4px; }
        """)
        layout.addWidget(self.table)

        # 底部操作按鈕
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #e0e0e0; color: #424242; border-radius: 4px; padding: 6px 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #d5d5d5; }
        """)

        btn_save = QPushButton("💾 儲存修改")
        btn_save.clicked.connect(self._save_changes)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white; border-radius: 4px; padding: 6px 16px; font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _load_data(self):
        if self.ds is None:
            return

        self.table.setRowCount(0)
        row = 0
        
        for elem in self.ds:
            tag_tuple = (elem.tag.group, elem.tag.elem)
            
            # 過濾不要顯示與不能編輯的項目
            if tag_tuple in EXCEPTION_TAGS:
                continue
            if elem.VR in EXCEPTION_VRS:
                continue
            if elem.tag.group == 0x0002: # Meta Header (Group 2 elements) typically shouldn't be edited normally
                continue

            self.table.insertRow(row)

            # (0010, 0010)
            tag_box = QTableWidgetItem(f"({elem.tag.group:04x}, {elem.tag.elem:04x})")
            tag_box.setFlags(tag_box.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tag_box.setData(Qt.ItemDataRole.UserRole, tag_tuple) # 隱藏存放原始 tuple 供之後存檔用
            self.table.setItem(row, 0, tag_box)

            name_box = QTableWidgetItem(str(elem.name))
            name_box.setFlags(name_box.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, name_box)

            vr_box = QTableWidgetItem(str(elem.VR))
            vr_box.setFlags(vr_box.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, vr_box)

            # 字串化目前的 value
            val_str = ""
            if elem.value is not None:
                if isinstance(elem.value, pydicom.multival.MultiValue):
                    val_str = "\\".join(str(v) for v in elem.value)
                else:
                    val_str = str(elem.value)
            
            val_box = QTableWidgetItem(val_str)
            val_box.setData(Qt.ItemDataRole.UserRole, val_str) # 記住最初的值做 diff 確認是否有改過
            self.table.setItem(row, 3, val_box)

            row += 1

    def _save_changes(self):
        """處理從 QTableWidget 把值覆寫回 Pydicom DataElement，並存檔"""
        if self.ds is None:
            return

        modified_count = 0
        
        for row in range(self.table.rowCount()):
            tag_item = self.table.item(row, 0)
            vr_item = self.table.item(row, 2)
            val_item = self.table.item(row, 3)

            original_val_str = val_item.data(Qt.ItemDataRole.UserRole)
            new_val_str = val_item.text().strip()

            if original_val_str != new_val_str:
                tag_tuple = tag_item.data(Qt.ItemDataRole.UserRole)
                tag = Tag(tag_tuple)
                vr = vr_item.text()
                
                try:
                    # Multi-value 分割機制 (以反斜線分割)
                    if "\\" in new_val_str:
                        parts = new_val_str.split("\\")
                        if vr in ['US', 'UL', 'SS', 'SL']:
                            new_val = [int(p) for p in parts]
                        elif vr in ['FL', 'FD']:
                            new_val = [float(p) for p in parts]
                        else:
                            new_val = parts
                    else:
                        if new_val_str == "":
                            new_val = ""
                        else:
                            if vr in ['US', 'UL', 'SS', 'SL']:
                                new_val = int(new_val_str)
                            elif vr in ['FL', 'FD']:
                                new_val = float(new_val_str)
                            else:
                                new_val = new_val_str

                    if tag in self.ds:
                        self.ds[tag].value = new_val
                    else:
                        # 原本沒有的理論上不會出現，但如果存在則新增
                        self.ds.add_new(tag, vr, new_val)
                    
                    modified_count += 1
                except ValueError as e:
                    logger.error(f"Cannot cast '{new_val_str}' for VR {vr}")
                    QMessageBox.warning(self, "資料格式錯誤", f"標籤 {tag_item.text()} 無法轉換為正確型態：\n請確保型態 (VR = {vr}) 與數值匹配。")
                    return

        if modified_count == 0:
            self.reject()
            return

        # 若是 Patient ID 改了，需跳出強烈警告
        new_patient_id = str(getattr(self.ds, "PatientID", ""))
        if new_patient_id != self.original_patient_id:
             reply = QMessageBox.question(
                 self, "Patient ID 變更確認", 
                 f"您將 Patient ID 由 \n'{self.original_patient_id}' \n更改為 \n'{new_patient_id}'。\n\n"
                 f"若儲存，系統將視此影像屬於另一個全新病患！\n是否確定儲存？",
                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                 QMessageBox.StandardButton.No
             )
             if reply == QMessageBox.StandardButton.No:
                 return

        try:
            self.ds.save_as(self.file_path)
            self.changes_saved = True
            logger.info(f"成功儲存修改的 DICOM 標籤 ({modified_count} attributes changed) 至：{self.file_path}")
            QMessageBox.information(self, "成功", f"成功更新 {modified_count} 個項目並儲存檔案！")
            self.accept()
        except Exception as e:
            logger.error(f"儲存 DICOM 時發生錯誤：{e}", exc_info=True)
            QMessageBox.critical(self, "存檔錯誤", f"無法儲存檔案：\n{e}")
