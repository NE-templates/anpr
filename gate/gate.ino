#include <Servo.h>

// Pin definitions for Wemos D1 Mini
#define TRIGGER_PIN 15    // D8 (GPIO15)
#define ECHO_PIN 13       // D7 (GPIO13)
#define SERVO_PIN 2       // D4 (GPIO2)
#define LED_STATUS_PIN 16 // D0 (GPIO16) - Status LED (optional)

// Gate configuration
#define GATE_CLOSED_ANGLE 0
#define GATE_OPEN_ANGLE 180
#define SERVO_MOVE_DELAY 15    // Delay between servo steps (ms)
#define SAFETY_DISTANCE 20.0   // Minimum safe distance in cm
#define MAX_DISTANCE 400.0     // Maximum valid distance reading
#define AUTO_CLOSE_TIME 5000   // Auto-close after 5 seconds
#define DISTANCE_SAMPLES 5     // Number of distance readings to average

// System states
enum GateState {
  CLOSED,
  OPENING,
  OPEN,
  CLOSING,
  BLOCKED
};

Servo barrierServo;
GateState currentState = CLOSED;
unsigned long lastCommandTime = 0;
unsigned long gateOpenTime = 0;
bool autoCloseEnabled = true;
int currentServoAngle = GATE_CLOSED_ANGLE;

void setup() {
  Serial.begin(115200);
  
  // Initialize pins
  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_STATUS_PIN, OUTPUT);
  
  // Initialize servo
  barrierServo.attach(SERVO_PIN);
  barrierServo.write(GATE_CLOSED_ANGLE);
  currentServoAngle = GATE_CLOSED_ANGLE;
  
  // Initialize status LED
  digitalWrite(LED_STATUS_PIN, LOW);
  
  Serial.println("GATE_CONTROLLER_READY");
  Serial.println("Commands: 1=Open, 0=Close, S=Status, A=Toggle Auto-close");
  Serial.println("Current State: CLOSED");
  
  delay(1000); // Allow servo to settle
}

void loop() {
  // Read distance with error handling
  float distance = getAverageDistance();
  
  // Send distance reading
  if (distance > 0) {
    Serial.print("DISTANCE:");
    Serial.println(distance, 1);
  } else {
    Serial.println("DISTANCE:ERROR");
  }
  
  // Process serial commands
  processSerialCommands();
  
  // Handle gate state machine
  handleGateStateMachine(distance);
  
  // Update status LED
  updateStatusLED();
  
  delay(100); // Main loop delay
}

float getAverageDistance() {
  float distances[DISTANCE_SAMPLES];
  int validReadings = 0;
  
  for (int i = 0; i < DISTANCE_SAMPLES; i++) {
    float dist = readUltrasonicDistance();
    if (dist > 0 && dist <= MAX_DISTANCE) {
      distances[validReadings] = dist;
      validReadings++;
    }
    delay(10); // Small delay between readings
  }
  
  if (validReadings == 0) {
    return -1; // No valid readings
  }
  
  // Calculate average
  float sum = 0;
  for (int i = 0; i < validReadings; i++) {
    sum += distances[i];
  }
  
  return sum / validReadings;
}

float readUltrasonicDistance() {
  // Send ultrasonic pulse
  digitalWrite(TRIGGER_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIGGER_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIGGER_PIN, LOW);
  
  // Read echo with timeout
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout
  
  if (duration == 0) {
    return -1; // Timeout or no echo
  }
  
  // Calculate distance in cm
  float distance = (duration * 0.0343) / 2.0;
  
  // Validate distance range
  if (distance < 2.0 || distance > MAX_DISTANCE) {
    return -1; // Invalid reading
  }
  
  return distance;
}

void processSerialCommands() {
  if (!Serial.available()) return;
  
  char cmd = Serial.read();
  
  // Clear any remaining characters in buffer
  while (Serial.available()) {
    Serial.read();
  }
  
  switch (cmd) {
    case '1':
    case 'O':
    case 'o':
      openGate();
      break;
      
    case '0':
    case 'C':
    case 'c':
      closeGate();
      break;
      
    case 'S':
    case 's':
      printStatus();
      break;
      
    case 'A':
    case 'a':
      toggleAutoClose();
      break;
      
    case 'E':
    case 'e':
      emergencyStop();
      break;
      
    default:
      Serial.println("UNKNOWN_COMMAND");
      Serial.println("Commands: 1/O=Open, 0/C=Close, S=Status, A=Auto-close, E=Emergency");
      break;
  }
  
  lastCommandTime = millis();
}

void handleGateStateMachine(float distance) {
  static unsigned long stateChangeTime = 0;
  
  switch (currentState) {
    case CLOSED:
      // Gate is closed, ready for commands
      break;
      
    case OPENING:
      if (currentServoAngle >= GATE_OPEN_ANGLE) {
        currentState = OPEN;
        gateOpenTime = millis();
        Serial.println("STATE:OPEN");
      }
      break;
      
    case OPEN:
      // Check for auto-close timeout
      if (autoCloseEnabled && (millis() - gateOpenTime > AUTO_CLOSE_TIME)) {
        // Only auto-close if no obstacle detected
        if (distance < 0 || distance > SAFETY_DISTANCE) {
          Serial.println("AUTO_CLOSING");
          closeGate();
        } else {
          // Reset timer if obstacle still present
          gateOpenTime = millis();
          Serial.println("AUTO_CLOSE_DELAYED:OBSTACLE");
        }
      }
      break;
      
    case CLOSING:
      // Check for obstacles while closing
      if (distance > 0 && distance <= SAFETY_DISTANCE) {
        Serial.println("OBSTACLE_DETECTED:STOPPING");
        emergencyStop();
        currentState = BLOCKED;
        stateChangeTime = millis();
      } else if (currentServoAngle <= GATE_CLOSED_ANGLE) {
        currentState = CLOSED;
        Serial.println("STATE:CLOSED");
      }
      break;
      
    case BLOCKED:
      // Wait for obstacle to clear
      if (distance < 0 || distance > SAFETY_DISTANCE) {
        if (millis() - stateChangeTime > 2000) { // 2 second delay
          Serial.println("OBSTACLE_CLEARED:RESUMING");
          closeGate(); // Resume closing
        }
      } else {
        stateChangeTime = millis(); // Reset timer while obstacle present
      }
      break;
  }
}

void openGate() {
  if (currentState == OPEN || currentState == OPENING) {
    Serial.println("GATE_ALREADY_OPEN");
    return;
  }
  
  Serial.println("OPENING_GATE");
  currentState = OPENING;
  
  // Smooth servo movement
  while (currentServoAngle < GATE_OPEN_ANGLE) {
    currentServoAngle += 2;
    if (currentServoAngle > GATE_OPEN_ANGLE) {
      currentServoAngle = GATE_OPEN_ANGLE;
    }
    barrierServo.write(currentServoAngle);
    delay(SERVO_MOVE_DELAY);
  }
}

void closeGate() {
  if (currentState == CLOSED || currentState == CLOSING) {
    Serial.println("GATE_ALREADY_CLOSED");
    return;
  }
  
  Serial.println("CLOSING_GATE");
  currentState = CLOSING;
  
  // Smooth servo movement with obstacle checking
  while (currentServoAngle > GATE_CLOSED_ANGLE && currentState == CLOSING) {
    currentServoAngle -= 2;
    if (currentServoAngle < GATE_CLOSED_ANGLE) {
      currentServoAngle = GATE_CLOSED_ANGLE;
    }
    barrierServo.write(currentServoAngle);
    delay(SERVO_MOVE_DELAY);
    
    // Check for obstacles during closing
    float distance = readUltrasonicDistance();
    if (distance > 0 && distance <= SAFETY_DISTANCE) {
      Serial.println("OBSTACLE_DETECTED:STOPPING");
      emergencyStop();
      currentState = BLOCKED;
      return;
    }
  }
}

void emergencyStop() {
  Serial.println("EMERGENCY_STOP");
  // Stop servo at current position
  barrierServo.write(currentServoAngle);
  
  // Determine new state based on position
  if (currentServoAngle > (GATE_OPEN_ANGLE / 2)) {
    currentState = OPEN;
  } else {
    currentState = CLOSED;
  }
}

void toggleAutoClose() {
  autoCloseEnabled = !autoCloseEnabled;
  Serial.print("AUTO_CLOSE:");
  Serial.println(autoCloseEnabled ? "ENABLED" : "DISABLED");
}

void printStatus() {
  Serial.println("=== GATE STATUS ===");
  Serial.print("STATE:");
  switch (currentState) {
    case CLOSED: Serial.println("CLOSED"); break;
    case OPENING: Serial.println("OPENING"); break;
    case OPEN: Serial.println("OPEN"); break;
    case CLOSING: Serial.println("CLOSING"); break;
    case BLOCKED: Serial.println("BLOCKED"); break;
  }
  Serial.print("SERVO_ANGLE:");
  Serial.println(currentServoAngle);
  Serial.print("AUTO_CLOSE:");
  Serial.println(autoCloseEnabled ? "ENABLED" : "DISABLED");
  if (currentState == OPEN && autoCloseEnabled) {
    unsigned long timeRemaining = AUTO_CLOSE_TIME - (millis() - gateOpenTime);
    if (timeRemaining > 0) {
      Serial.print("AUTO_CLOSE_IN:");
      Serial.print(timeRemaining / 1000);
      Serial.println("s");
    }
  }
  Serial.println("==================");
}

void updateStatusLED() {
  static unsigned long lastBlink = 0;
  static bool ledState = false;
  
  switch (currentState) {
    case CLOSED:
      digitalWrite(LED_STATUS_PIN, LOW); // Off
      break;
      
    case OPEN:
      digitalWrite(LED_STATUS_PIN, HIGH); // On
      break;
      
    case OPENING:
    case CLOSING:
      // Slow blink
      if (millis() - lastBlink > 500) {
        ledState = !ledState;
        digitalWrite(LED_STATUS_PIN, ledState);
        lastBlink = millis();
      }
      break;
      
    case BLOCKED:
      // Fast blink
      if (millis() - lastBlink > 150) {
        ledState = !ledState;
        digitalWrite(LED_STATUS_PIN, ledState);
        lastBlink = millis();
      }
      break;
  }
}