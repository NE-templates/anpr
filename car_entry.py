import cv2
from ultralytics import YOLO
import os
import time
import serial
import serial.tools.list_ports
import csv
from collections import Counter
import pytesseract
import random

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

model = YOLO('best.pt')
save_dir = 'plates'
os.makedirs(save_dir, exist_ok=True)
csv_file = 'plates_log.csv'

if not os.path.exists(csv_file):
    with open(csv_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Plate Number', 'Payment Status', 'Timestamp'])

def detect_arduino_port():
    """Detect Arduino port with better error handling"""
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if "Arduino" in port.description or "USB-SERIAL" in port.description:
            return port.device
    # If no Arduino found, try common COM ports
    for port_name in ['COM3', 'COM4', 'COM5', 'COM6']:
        try:
            test_serial = serial.Serial(port_name, 9600, timeout=1)
            test_serial.close()
            return port_name
        except:
            continue
    return None

def connect_arduino(max_retries=3):
    """Connect to Arduino with retry logic"""
    arduino_port = detect_arduino_port()
    
    if not arduino_port:
        print("[ERROR] No Arduino port detected.")
        return None
    
    for attempt in range(max_retries):
        try:
            print(f"[CONNECTING] Attempting to connect to Arduino on {arduino_port} (attempt {attempt + 1})")
            arduino = serial.Serial(arduino_port, 9600, timeout=1)
            time.sleep(2)  # Wait for Arduino to initialize
            print(f"[CONNECTED] Arduino successfully connected on {arduino_port}")
            return arduino
        except serial.SerialException as e:
            print(f"[ERROR] Connection attempt {attempt + 1} failed: {e}")
            if "Access is denied" in str(e):
                print("[HELP] Port may be in use. Try:")
                print("- Close Arduino IDE")
                print("- Unplug and replug Arduino")
                print("- Check Device Manager for correct COM port")
            time.sleep(1)
    
    print("[ERROR] Failed to connect to Arduino after all attempts.")
    return None

def read_distance(arduino):
    """Read distance from Arduino with proper error handling"""
    if not arduino:
        return 150  # Default safe distance when no Arduino
    
    try:
        if arduino.in_waiting > 0:
            val = arduino.readline().decode('utf-8').strip()
            if val:
                distance = float(val)
                # Validate reasonable distance range
                if 0 <= distance <= 400:  # HC-SR04 max range is ~400cm
                    return distance
                else:
                    print(f"[WARNING] Invalid distance reading: {distance}")
                    return 150
            else:
                return 150  # No data available
        else:
            return 150  # No data waiting
    except (UnicodeDecodeError, ValueError, serial.SerialException) as e:
        print(f"[ERROR] Reading distance: {e}")
        return 150
    except Exception as e:
        print(f"[UNEXPECTED ERROR] {e}")
        return 150

# Connect to Arduino
arduino = connect_arduino()

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[ERROR] Could not open camera")
    exit()

plate_buffer = []
entry_cooldown = 300  # 5 minutes
last_saved_plate = None
last_entry_time = 0

print("[SYSTEM] Ready. Press 'q' to exit.")
print("[INFO] Distance threshold: 50cm")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Could not read frame from camera")
            break
        
        # Read distance from Arduino
        distance = read_distance(arduino)
        print(f"[SENSOR] Distance: {distance} cm")
        
        # Only process if vehicle is close enough
        if distance and distance <= 50:
            results = model(frame)
            
            for result in results:
                for box in result.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    plate_img = frame[y1:y2, x1:x2]
                    
                    # Skip if plate image is too small
                    if plate_img.shape[0] < 20 or plate_img.shape[1] < 50:
                        continue
                    
                    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
                    blur = cv2.GaussianBlur(gray, (5, 5), 0)
                    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
                    
                    plate_text = pytesseract.image_to_string(
                        thresh, config='--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                    ).strip().replace(" ", "")
                    
                    if "RA" in plate_text:
                        start_idx = plate_text.find("RA")
                        plate_candidate = plate_text[start_idx:]
                        if len(plate_candidate) >= 7:
                            plate_candidate = plate_candidate[:7]
                            prefix, digits, suffix = plate_candidate[:3], plate_candidate[3:6], plate_candidate[6]
                            if (prefix.isalpha() and prefix.isupper() and
                                digits.isdigit() and suffix.isalpha() and suffix.isupper()):
                                print(f"[VALID] Plate Detected: {plate_candidate}")
                                plate_buffer.append(plate_candidate)
                                
                                # Save plate image
                                timestamp_str = time.strftime('%Y%m%d_%H%M%S')
                                image_filename = f"{plate_candidate}_{timestamp_str}.jpg"
                                save_path = os.path.join(save_dir, image_filename)
                                cv2.imwrite(save_path, plate_img)
                                print(f"[IMAGE SAVED] {save_path}")
                                
                                # Process when we have enough samples
                                if len(plate_buffer) >= 3:
                                    most_common = Counter(plate_buffer).most_common(1)[0][0]
                                    current_time = time.time()
                                    
                                    if (most_common != last_saved_plate or
                                        (current_time - last_entry_time) > entry_cooldown):
                                        
                                        # Log to CSV
                                        with open(csv_file, 'a', newline='') as f:
                                            writer = csv.writer(f)
                                            writer.writerow([most_common, 0, time.strftime('%Y-%m-%d %H:%M:%S')])
                                        print(f"[SAVED] {most_common} logged to CSV.")
                                        
                                        # Control gate
                                        if arduino:
                                            try:
                                                arduino.write(b'1')
                                                print("[GATE] Opening gate (sent '1')")
                                                time.sleep(15)
                                                arduino.write(b'0')
                                                print("[GATE] Closing gate (sent '0')")
                                            except serial.SerialException as e:
                                                print(f"[ERROR] Gate control failed: {e}")
                                        
                                        last_saved_plate = most_common
                                        last_entry_time = current_time
                                    else:
                                        print("[SKIPPED] Duplicate within 5 min window.")
                                    
                                    plate_buffer.clear()
                    
                    # Display processed images
                    cv2.imshow("Plate", plate_img)
                    cv2.imshow("Processed", thresh)
                    time.sleep(0.1)  # Reduced sleep time
            
            # Show annotated frame when vehicle is detected
            annotated_frame = results[0].plot() if results else frame
        else:
            # Show regular frame when no vehicle nearby
            annotated_frame = frame
        
        cv2.imshow('Webcam Feed', annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print("\n[SYSTEM] Shutting down...")
except Exception as e:
    print(f"[ERROR] Unexpected error: {e}")
finally:
    # Cleanup
    cap.release()
    if arduino:
        try:
            arduino.close()
            print("[SYSTEM] Arduino connection closed.")
        except:
            pass
    cv2.destroyAllWindows()
    print("[SYSTEM] System shutdown complete.")