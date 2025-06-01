import serial
import csv
import time
import os
from datetime import datetime

# Configuration
CSV_FILE = 'plates_log.csv'
RATE_PER_HOUR = 200
SERIAL_PORT = 'COM16'  # Change this to your Arduino port
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
        """Find the most recent unpaid entry for a plate"""
        try:
            with open(CSV_FILE, 'r') as f:
                reader = csv.DictReader(f)
                unpaid_entries = [
                    row for row in reader
                    if row['Plate Number'].strip() == plate and row['Payment Status'].strip() == '0'
                ]
            
            if not unpaid_entries:
                return None
            
            # Sort by timestamp (most recent first)
            unpaid_entries.sort(
                key=lambda x: datetime.strptime(x['Timestamp'], "%Y-%m-%d %H:%M:%S"), 
                reverse=True
            )
            
            entry_time = datetime.strptime(unpaid_entries[0]['Timestamp'], "%Y-%m-%d %H:%M:%S")
            return entry_time
            
        except Exception as e:
            print(f"[ERROR] Failed to lookup plate {plate}: {e}")
            return None
    
    def calculate_parking_fee(self, entry_time):
        """Calculate parking fee based on duration"""
        duration_seconds = (datetime.now() - entry_time).total_seconds()
        duration_hours = max(1, int(duration_seconds / 3600))  # Minimum 1 hour
        amount_due = duration_hours * RATE_PER_HOUR
        return duration_hours, amount_due
    
    def update_payment_status(self, plate, amount_paid):
        """Update payment status in CSV"""
        try:
            rows = []
            with open(CSV_FILE, 'r') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if not rows:
                print("[ERROR] CSV file is empty")
                return False
            
            header = rows[0]
            updated = False
            
            # Find the most recent unpaid entry for this plate
            unpaid_entries = []
            for i, row in enumerate(rows[1:], start=1):
                if (len(row) >= 3 and row[0].strip() == plate and 
                    row[1].strip() == '0'):
                    unpaid_entries.append((i, row))
            
            if unpaid_entries:
                # Sort by timestamp and update the most recent
                timestamp_index = 2  # Timestamp is at index 2
                unpaid_entries.sort(
                    key=lambda x: datetime.strptime(x[1][timestamp_index], "%Y-%m-%d %H:%M:%S"), 
                    reverse=True
                )
                
                latest_index = unpaid_entries[0][0]
                rows[latest_index][1] = '1'  # Mark as paid
                
                # Add amount paid if column doesn't exist or is empty
                if len(rows[latest_index]) < 4:
                    rows[latest_index].append(str(amount_paid))
                else:
                    rows[latest_index][3] = str(amount_paid)
                
                updated = True
            
            if updated:
                with open(CSV_FILE, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                print(f"[UPDATED] Payment status marked as paid for {plate}")
                return True
            else:
                print(f"[ERROR] No unpaid record found to update for {plate}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to update payment status: {e}")
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
            
            # Wait for Arduino response
            response = self.read_serial_line(timeout=10)
            if not response:
                print("[ERROR] No response from Arduino")
                return False
            
            print(f"[ARDUINO] {response}")
            
            if response.startswith("DONE:"):
                # Parse response: DONE:amount_paid:new_balance
                parts = response.split(':')
                if len(parts) >= 3:
                    amount_paid = float(parts[1])
                    new_balance = float(parts[2])
                    
                    # Update payment status in CSV
                    if self.update_payment_status(plate, amount_paid):
                        print(f"\n[SUCCESS] Payment processed successfully!")
                        print(f"Amount Paid: {amount_paid:.2f} RWF")
                        print(f"Remaining Balance: {new_balance:.2f} RWF")
                        return True
                    else:
                        print("[WARNING] Payment deducted but CSV update failed")
                        return False
                else:
                    print("[ERROR] Invalid response format from Arduino")
                    return False
            
            elif response == "INSUFFICIENT":
                print("[ERROR] Arduino reports insufficient balance")
                return False
            else:
                print(f"[ERROR] Unexpected Arduino response: {response}")
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