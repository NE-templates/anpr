import mysql.connector
from mysql.connector import Error
import time
from datetime import datetime

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'port': 3306,
    'password': 'remy1234',
    'database': 'pms',
    'use_pure': True
}

def connect_db():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"[DB ERROR] Could not connect: {e}")
        return None

def create_table_if_not_exists():
    try:
        conn = connect_db()
        if conn is None:
            print("[DB ERROR] Connection is None.")
            return

        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS parking_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            plate_number VARCHAR(10),
            payment_status TINYINT,
            amount DECIMAL(10, 2) DEFAULT 0.00,
            timestamp DATETIME,
            gate VARCHAR(20)
        )''')
        conn.commit()
        print("[DB] Table 'parking_sessions' ensured.")
    except Error as e:
        print(f"[DB ERROR] Table creation failed: {e}")
    except Exception as ex:
        print(f"[ERROR] Unexpected error during table creation: {ex}")
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass


def log_plate_to_db(plate_number, payment_status=0, amount=0.00, gate="entry"):
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO parking_sessions (plate_number, payment_status, amount, timestamp, gate)
                VALUES (%s, %s, %s, %s, %s)
            ''', (plate_number, payment_status, amount, time.strftime('%Y-%m-%d %H:%M:%S'), gate))
            conn.commit()
            print(f"[DB] Logged to DB: {plate_number}, {payment_status}, {amount}, {gate}")
        except Error as e:
            print(f"[DB ERROR] Insert failed: {e}")
        finally:
            cursor.close()
            conn.close()

def plate_exists_unpaid(plate_number):
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM parking_sessions
                WHERE plate_number = %s AND payment_status = 0
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (plate_number,))
            return cursor.fetchone() is not None
        except Error as e:
            print(f"[DB ERROR] Query failed: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

def is_payment_complete_db(plate_number):
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT payment_status FROM parking_sessions
                WHERE plate_number = %s
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (plate_number,))
            result = cursor.fetchone()
            return result and result["payment_status"] == 1
        except Error as e:
            print(f"[DB ERROR] is_payment_complete: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def is_already_exited(plate_number):
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT payment_status FROM parking_sessions
                WHERE plate_number = %s
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (plate_number,))
            result = cursor.fetchone()
            return result and result["payment_status"] == 2
        except Error as e:
            print(f"[DB ERROR] is_payment_complete: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
    return False

def update_exit_status_db(plate_number):
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE parking_sessions
                SET payment_status = 2, gate = 'exit'
                WHERE plate_number = %s AND payment_status = 1
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (plate_number,))
            conn.commit()
            print(f"[DB] Exit status updated for {plate_number}")
        except Error as e:
            print(f"[DB ERROR] Exit status update failed: {e}")
        finally:
            cursor.close()
            conn.close()

def get_latest_unpaid_entry(plate_number):
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT timestamp FROM parking_sessions
                WHERE plate_number = %s AND payment_status = 0
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (plate_number,))
            result = cursor.fetchone()
            if result:
                return datetime.strptime(str(result['timestamp']), "%Y-%m-%d %H:%M:%S")
            return None
        except Error as e:
            print(f"[DB ERROR] Failed to fetch unpaid entry: {e}")
            return None
        finally:
            cursor.close()
            conn.close()


def update_payment_status_db(plate_number, amount_paid):
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE parking_sessions
                SET payment_status = 1, amount = %s
                WHERE plate_number = %s AND payment_status = 0
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (amount_paid, plate_number))
            conn.commit()
            print(f"[DB] Payment updated for {plate_number} with {amount_paid} RWF")
        except Error as e:
            print(f"[DB ERROR] Failed to update payment: {e}")
        finally:
            cursor.close()
            conn.close()


def log_unauthorized_exit(plate_number):
    """Log a gate tampering or unpaid exit event"""
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE parking_sessions SET gate = 'unauthorized'
                WHERE plate_number = %s AND payment_status = 0
                ''', (plate_number,))
            conn.commit()
            print(f"[DB] Logged to DB tampering: {plate_number}")
        except Error as e:
            print(f"[DB ERROR] UPDATE failed: {e}")
        finally:
            cursor.close()
            conn.close()


def get_total_revenue():
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(amount) FROM parking_sessions WHERE payment_status = 1 OR payment_status = 2")
            result = cursor.fetchone()
            return result[0] if result[0] else 0.0
        except Error as e:
            print(f"[DB ERROR] Revenue query failed: {e}")
            return 0.0
        finally:
            cursor.close()
            conn.close()

def get_daily_stats():
    conn = connect_db()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT DATE(timestamp) AS date,
                       COUNT(*) AS total_vehicles,
                       SUM(CASE WHEN payment_status = 1 OR payment_status = 2 THEN amount ELSE 0 END) AS revenue,
                       SUM(CASE WHEN payment_status = 0 THEN 1 ELSE 0 END) AS unpaid_count,
                       SUM(CASE WHEN gate = 'unauthorized' THEN 1 ELSE 0 END) AS alerts
                FROM parking_sessions
                GROUP BY DATE(timestamp)
                ORDER BY DATE(timestamp) DESC
                LIMIT 7
            ''')
            return cursor.fetchall()
        except Error as e:
            print(f"[DB ERROR] Daily stats query failed: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
