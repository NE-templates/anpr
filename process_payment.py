import serial
import csv
import time
import os
from datetime import datetime
from web.db import update_payment_status_db, get_latest_unpaid_entry

# Configuration
CSV_FILE = 'plates_log.csv'
RATE_PER_HOUR = 500
SERIAL_PORT = 'COM6'  # Change this to your Arduino port
BAUD_RATE = 9600
SERIAL_TIMEOUT = 5

class ParkingPaymentSystem:
    def __init__(self):
        self.ser = None
        self.initialize_csv()
        self.connect_arduino()
    
    def initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Plate Number', 'Payment Status', 'Timestamp', 'Amount Paid'])
            print(f"[INIT] Created new CSV file: {CSV_FILE}")
        else:
            print(f"[INIT] Using existing CSV file: {CSV_FILE}")
    
    def connect_arduino(self):
        """Connect to Arduino with error handling"""
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=SERIAL_TIMEOUT)
            time.sleep(3)  # Wait for Arduino to initialize
            print(f"[CONNECTED] Arduino connected on {SERIAL_PORT}")
            
            # Wait for Arduino ready signal
            start_time = time.time()
            while time.time() - start_time < 10:  # 10 second timeout
                if self.ser.in_waiting:
                    line = self.ser.readline().decode().strip()
                    if line == "READY":
                        print("[READY] Arduino is ready for payments")
                        break
                time.sleep(0.1)
            else:
                print("[WARNING] Arduino ready signal not received")
                
        except serial.SerialException as e:
            print(f"[ERROR] Failed to connect to Arduino: {e}")
            print("Please check:")
            print("1. Arduino is connected to the correct port")
            print("2. No other programs are using the serial port")
            print("3. Arduino is running the payment processing code")
            exit(1)
    
    def read_serial_line(self, timeout=10):
        """Read a line from serial with timeout"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode().strip()
                    if line:
                        return line
                except UnicodeDecodeError:
                    continue
            time.sleep(0.01)
        return None
    
    def parse_card_data(self, line):
        """Parse card data from Arduino"""
        try:
            print(f"[PARSE] Parsing card data: {line}")
            if not line.startswith("PLATE:") or ";BALANCE:" not in line:
                return None, None
            
            parts = line.split(';')
            plate = parts[0].split(':')[1].strip()
            balance_str = parts[1].split(':')[1].strip()
            balance = float(balance_str)
            
            # Validate plate format (should start with RA and be 7 chars)
            if not plate.startswith('RA') or len(plate) != 7:
                print(f"[ERROR] Invalid plate format: {plate}")
                return None, None
                
            return plate, balance
        except (ValueError, IndexError) as e:
            print(f"[ERROR] Failed to parse card data '{line}': {e}")
            return None, None
    
    def lookup_unpaid_entry(self, plate):
          """Look up the latest unpaid entry from DB (not CSV)"""
          return get_latest_unpaid_entry(plate)

    
    def calculate_parking_fee(self, entry_time):
        """Calculate parking fee based on duration"""
        duration_seconds = (datetime.now() - entry_time).total_seconds()
        duration_hours = max(1, int(duration_seconds / 3600))  # Minimum 1 hour
        amount_due = duration_hours * RATE_PER_HOUR
        return duration_hours, amount_due
    
    def update_payment_status(self, plate, amount_paid):
        """Update DB and log to CSV"""
        try:
            # Update DB
            update_payment_status_db(plate, amount_paid)
    
            # Append payment log to CSV for backup
            with open(CSV_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([plate, '1', time.strftime("%Y-%m-%d %H:%M:%S"), amount_paid])
            print(f"[LOGGED] Backup written to CSV for {plate}")
            return True
    
        except Exception as e:
            print(f"[ERROR] Failed to update DB or log payment: {e}")
            return False

    
    def process_payment(self, plate, balance, entry_time):
        """Process payment for a specific plate"""
        duration_hours, amount_due = self.calculate_parking_fee(entry_time)
        
        print(f"\n[PAYMENT INFO]")
        print(f"Plate Number: {plate}")
        print(f"Card Balance: {balance:.2f} RWF")
        print(f"Parking Duration: {duration_hours} hours")
        print(f"Amount Due: {amount_due:.2f} RWF")
        
        # Check if card has sufficient balance
        if balance < amount_due:
            print(f"[ERROR] Insufficient balance. Need {amount_due:.2f} RWF, have {balance:.2f} RWF")
            self.ser.write("INSUFFICIENT_PYTHON\n".encode())
            return False
        
        # Send amount to Arduino
        try:
            self.ser.write(f"{amount_due:.2f}\n".encode())
            print(f"[SENT] Payment amount {amount_due:.2f} RWF to Arduino")
            
            # Keep reading responses until we get DONE, INSUFFICIENT, or an ERROR
            start_time = time.time()
            timeout = 15  # Increased timeout to allow for Arduino processing
            
            while time.time() - start_time < timeout:
                response = self.read_serial_line(timeout=2)
                if not response:
                    continue
                
                print(f"[RECEIVED] {response}")
                
                # Check for final responses
                if response.startswith("DONE:"):
                    # Parse response: DONE:amount_paid:new_balance
                    parts = response.split(':')
                    if len(parts) >= 3:
                        try:
                            amount_paid = float(parts[1])
                            new_balance = float(parts[2])
                            
                            # Update payment status in DB
                            if self.update_payment_status(plate, amount_paid):
                                print(f"\n[SUCCESS] Payment processed successfully!")
                                print(f"Amount Paid: {amount_paid:.2f} RWF")
                                print(f"Remaining Balance: {new_balance:.2f} RWF")
                                return True
                            else:
                                print("[WARNING] Payment deducted but DB update failed")
                                return False
                        except (ValueError, IndexError) as e:
                            print(f"[ERROR] Failed to parse DONE response: {e}")
                            return False
                    else:
                        print("[ERROR] Invalid DONE response format from Arduino")
                        return False
                
                elif response == "INSUFFICIENT":
                    print("[ERROR] Arduino reports insufficient balance")
                    return False
                
                elif response.startswith("ERROR:"):
                    print(f"[ERROR] Arduino error: {response}")
                    return False
                
                elif response == "ABORTED":
                    print("[INFO] Payment aborted by Arduino")
                    return False
                
                # Handle info/debug messages (don't return, just log)
                elif (response.startswith("Debug:") or 
                      response.startswith("🔓") or 
                      response.startswith("✅") or 
                      response.startswith("❌") or
                      "Authentication success" in response or
                      "Data written successfully" in response or
                      "New balance written" in response):
                    print(f"[INFO] {response}")
                    # Continue reading for the final response
                
                else:
                    print(f"[INFO] {response}")
                    # Continue reading for other messages
            
            # If we reach here, we timed out
            print("[ERROR] Timeout waiting for Arduino response")
            return False
                    
        except Exception as e:
            print(f"[ERROR] Communication error with Arduino: {e}")
            return False
    
    def run(self):
        """Main payment processing loop"""
        print("🚗 Welcome to Parking Payment System 🚗")
        print("=" * 50)
        print("Place RFID card on reader to process payment...")
        print("Press Ctrl+C to exit")
        
        try:
            while True:
                line = self.read_serial_line(timeout=1)
                
                if not line:
                    continue
                
                print(f"[RECEIVED] {line}")
                
                # Handle different types of messages from Arduino
                if line.startswith("PLATE:"):
                    plate, balance = self.parse_card_data(line)
                    
                    if not plate or balance is None:
                        self.ser.write("NO_ENTRY\n".encode())
                        continue
                    
                    # Look up unpaid entry
                    entry_time = self.lookup_unpaid_entry(plate)
                    
                    if not entry_time:
                        print(f"[ERROR] No unpaid parking record found for {plate}")
                        self.ser.write("NO_ENTRY\n".encode())
                        continue
                    
                    # Process payment
                    self.process_payment(plate, balance, entry_time)
                
                elif line.startswith("ERROR:"):
                    print(f"[ARDUINO ERROR] {line}")
                
                elif line in ["READY", "Remove card and place next card..."]:
                    # Arduino status messages
                    pass
                
                else:
                    # Other Arduino messages
                    print(f"[INFO] {line}")
        
        except KeyboardInterrupt:
            print("\n[EXIT] Payment system stopped by user")
        except Exception as e:
            print(f"[FATAL ERROR] {e}")
        finally:
            if self.ser:
                self.ser.close()
                print("[DISCONNECTED] Serial connection closed")

if __name__ == "__main__":
    system = ParkingPaymentSystem()
    system.run()