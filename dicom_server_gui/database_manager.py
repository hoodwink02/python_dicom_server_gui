import sqlite3
import os
from datetime import datetime

from logger_config import setup_logger

logger = setup_logger("dicom_app")

class DatabaseManager:
    """
    用來管理 DICOM 本地資料庫的類別。
    負責建立資料庫、資料表，以及處理新增紀錄與查詢病患清單的功能。
    """
    def __init__(self, db_path: str = "dicom_local.db"):
        self.db_path = db_path
        logger.info(f"初始化資料庫管理器, DB 路徑: {self.db_path}")
        self._create_table()

    def _get_connection(self):
        """建立並回傳一個資料庫連線"""
        return sqlite3.connect(self.db_path)

    def _create_table(self):
        """
        初始化資料表。如果資料表不存在則建立。
        欄位包含: id, patient_id, patient_name, study_uid, series_uid, instance_uid, receive_date, file_path
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS dicom_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            patient_name TEXT,
            study_uid TEXT NOT NULL,
            series_uid TEXT NOT NULL,
            instance_uid TEXT NOT NULL,
            receive_date TEXT,
            file_path TEXT NOT NULL
        );
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            logger.debug("資料表 dicom_records 已確認建立")

    def insert_record(self, patient_id: str, patient_name: str, study_uid: str, 
                      series_uid: str, instance_uid: str, receive_date: str, file_path: str) -> int:
        """
        新增一筆 DICOM 檔案紀錄到資料庫中。
        
        :param patient_id: 病患 ID
        :param patient_name: 病患姓名
        :param study_uid: 檢查 (Study) 的 UID
        :param series_uid: 系列 (Series) 的 UID
        :param instance_uid: 影像 (Instance) 的 UID
        :param receive_date: 接收日期與時間 (建議格式如 ISO 8601，例："2023-10-27 10:00:00")
        :param file_path: 檔案在本地硬碟的絕對路徑
        :return: 新增紀錄的主鍵 (id)
        """
        insert_sql = """
        INSERT INTO dicom_records (
            patient_id, patient_name, study_uid, series_uid, 
            instance_uid, receive_date, file_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(insert_sql, (
                patient_id, patient_name, study_uid, series_uid, 
                instance_uid, receive_date, file_path
            ))
            conn.commit()
            record_id = cursor.lastrowid
            logger.info(f"INSERT 成功 — ID: {record_id}, PatientID: {patient_id}, File: {file_path}")
            return record_id

    def get_all_studies(self) -> list:
        """
        查詢所有不重複的檢查清單 (含最近一次接收時間)。
        
        :return: 包含檢查資料的字典清單，例如:
                 [{'patient_id': 'P001', 'patient_name': 'John Doe', 'study_uid': '1.2.3', 'receive_date': '2025-01-01 10:00:00'}, ...]
        """
        query_sql = """
        SELECT patient_id, patient_name, study_uid, MAX(receive_date) AS receive_date
        FROM dicom_records 
        GROUP BY patient_id, patient_name, study_uid
        ORDER BY receive_date DESC;
        """
        with self._get_connection() as conn:
            # 讓游標回傳字典格式的結果，方便後續讀取欄位名稱
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query_sql)
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            logger.debug(f"查詢檢查清單, 共 {len(result)} 筆")
            return result

    def get_file_paths_for_study(self, study_uid: str) -> list:
        """
        取得該檢查底下所有 DICOM 檔案路徑。
        """
        query_sql = """
        SELECT DISTINCT file_path FROM dicom_records
        WHERE study_uid = ?
        ORDER BY receive_date ASC;
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query_sql, (study_uid,))
            return [row[0] for row in cursor.fetchall()]

    def delete_by_patient_id(self, patient_id: str) -> int:
        """
        刪除指定病患 ID 的所有 DICOM 紀錄。

        :param patient_id: 要刪除的病患 ID
        :return: 被刪除的紀錄筆數
        """
        delete_sql = "DELETE FROM dicom_records WHERE patient_id = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(delete_sql, (patient_id,))
            conn.commit()
            deleted_count = cursor.rowcount
            logger.info(f"DELETE 完成 — PatientID: {patient_id}, 刪除 {deleted_count} 筆")
            return deleted_count

    def delete_by_study_uid(self, study_uid: str) -> int:
        """
        刪除指定 Study UID 的所有 DICOM 紀錄。

        :param study_uid: 要刪除的 Study UID
        :return: 被刪除的紀錄筆數
        """
        delete_sql = "DELETE FROM dicom_records WHERE study_uid = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(delete_sql, (study_uid,))
            conn.commit()
            deleted_count = cursor.rowcount
            logger.info(f"DELETE 完成 — StudyUID: {study_uid}, 刪除 {deleted_count} 筆")
            return deleted_count

    def delete_by_file_path(self, file_path: str) -> int:
        """
        刪除指定檔案路徑的所有 DICOM 紀錄 (通常只會有一筆)。
        
        :param file_path: 檔案絕對路徑
        :return: 被刪除的紀錄筆數
        """
        delete_sql = "DELETE FROM dicom_records WHERE file_path = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(delete_sql, (file_path,))
            conn.commit()
            deleted_count = cursor.rowcount
            logger.info(f"DELETE 完成 — FilePath: {file_path}, 刪除 {deleted_count} 筆")
            return deleted_count

# ==========================================
# 簡單的測試程式碼 (可直接執行此檔案來測試功能)
# ==========================================
if __name__ == "__main__":
    # 建立管理器實例 (會在當前目錄產生 dicom_local.db)
    db = DatabaseManager('dicom_local.db')
    
    # 測試資料
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_data = [
        ("P12345", "Test Patient A", "1.2.3.1", "1.2.3.1.1", "1.2.3.1.1.1", now_str, "C:/dicom/P12345/img1.dcm"),
        ("P12345", "Test Patient A", "1.2.3.1", "1.2.3.1.1", "1.2.3.1.1.2", now_str, "C:/dicom/P12345/img2.dcm"),
        ("P98765", "Test Patient B", "1.2.3.2", "1.2.3.2.1", "1.2.3.2.1.1", now_str, "C:/dicom/P98765/img1.dcm")
    ]
    
    # 新增紀錄測試
    print("開始新增測試資料...")
    for data in test_data:
        record_id = db.insert_record(*data)
        print(f"  成功新增紀錄，自動產生 ID: {record_id}")
    
    # 查詢病患清單測試
    print("\n查詢病患清單:")
    patients = db.get_all_patients()
    for p in patients:
        print(f"  病患 ID: {p['patient_id']}, 姓名: {p['patient_name']}")
