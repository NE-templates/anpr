#include <Servo.h>

// Pin Definitions (from your second code)
#define TRIGGER_PIN 2
#define ECHO_PIN 3
#define RED_LED_PIN 4
#define BLUE_LED_PIN 5
#define SERVO_PIN 6
#define GND_PIN_1 7
#define GND_PIN_2 8
#define BUZZER_PIN 12

// Gate Configuration
#define GATE_CLOSED_ANGLE 6
#define GATE_OPEN_ANGLE 90
#define SERVO_MOVE_DELAY 15       // Delay between servo steps (ms)
#define OBSTACLE_DISTANCE 50.0    // Obstacle detection threshold in cm
#define MAX_DISTANCE 400.0        // Maximum valid distance reading
#define AUTO_CLOSE_TIME 5000      // Auto-close after 5 seconds
#define DISTANCE_SAMPLES 3        // Number of distance readings to average
#define BUZZ_INTERVAL 300         // Buzzer interval in ms

// System States
enum GateState {
  CLOSED,
  OPENING,
  OPEN,
  CLOSING,
  BLOCKED
};

Servo barrierServo;
GateState currentState = CLOSED;
unsigned long gateOpenTime = 0;
unsigned long lastBuzzTime = 0;
int currentServoAngle = GATE_CLOSED_ANGLE;
bool buzzerState = false;
bool obstaclePresent = false;

// ============================
// Initialization Functions
// ============================
void initializeSerial() {
  Serial.begin(9600);
}

void initializeUltrasonic() {
  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
}

void initializeLEDs() {
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(BLUE_LED_PIN, OUTPUT);
}

void initializeBuzzer() {
  pinMode(BUZZER_PIN, OUTPUT);
}

void initializeHardcodedGrounds() {
  pinMode(GND_PIN_1, OUTPUT);
  pinMode(GND_PIN_2, OUTPUT);
  digitalWrite(GND_PIN_1, LOW);
  digitalWrite(GND_PIN_2, LOW);
}

void initializeServo() {
  barrierServo.attach(SERVO_PIN);
  barrierServo.write(GATE_CLOSED_ANGLE);
  currentServoAngle = GATE_CLOSED_ANGLE;
}

void testIndicators() {
  digitalWrite(BLUE_LED_PIN, HIGH);
  digitalWrite(BUZZER_PIN, HIGH);
  delay(500);
  digitalWrite(BLUE_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(RED_LED_PIN, HIGH);
}

// ============================
// Distance Measurement
// ============================
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

// ============================
// Gate Control Functions
// ============================
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
  
  currentState = OPEN;
  gateOpenTime = millis();
  digitalWrite(BLUE_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, LOW);
  Serial.println("STATE:OPEN");
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
    if (distance > 0 && distance <= OBSTACLE_DISTANCE) {
      Serial.println("OBSTACLE_DETECTED:STOPPING");
      emergencyStop();
      currentState = BLOCKED;
      return;
    }
  }
  
  if (currentState == CLOSING) {
    currentState = CLOSED;
    digitalWrite(BLUE_LED_PIN, LOW);
    digitalWrite(RED_LED_PIN, HIGH);
    digitalWrite(BUZZER_PIN, LOW); // Stop buzzing
    Serial.println("STATE:CLOSED");
  }
}

void emergencyStop() {
  Serial.println("EMERGENCY_STOP");
  // Stop servo at current position
  barrierServo.write(currentServoAngle);
  
  // Determine new state based on position
  if (currentServoAngle > (GATE_OPEN_ANGLE / 2)) {
    currentState = OPEN;
    gateOpenTime = millis(); // Reset auto-close timer
  } else {
    currentState = CLOSED;
  }
}

// ============================
// Serial Command Handling
// ============================
void handleSerialCommands() {
  if (Serial.available()) {
    char cmd = Serial.read();
    
    // Clear any remaining characters in buffer
    while (Serial.available()) {
      Serial.read();
    }
    
    switch (cmd) {
      case '1':
        openGate();
        break;
        
      case '0':
        closeGate();
        break;
        
      case 'S':
      case 's':
        printStatus();
        break;
        
      default:
        Serial.println("UNKNOWN_COMMAND");
        Serial.println("Commands: 1=Open (from Python), 0=Close, S=Status");
        break;
    }
  }
}

// ============================
// Buzzer Control
// ============================
void handleBuzzer() {
  if (obstaclePresent) {
    unsigned long currentMillis = millis();
    if (currentMillis - lastBuzzTime >= BUZZ_INTERVAL) {
      buzzerState = !buzzerState;
      digitalWrite(BUZZER_PIN, buzzerState);
      lastBuzzTime = currentMillis;
    }
  } else {
    digitalWrite(BUZZER_PIN, LOW);
    buzzerState = false;
  }
}

// ============================
// State Machine
// ============================
void handleGateStateMachine(float distance) {
  static unsigned long stateChangeTime = 0;
  
  // Update obstacle status
  obstaclePresent = (distance > 0 && distance <= OBSTACLE_DISTANCE);
  
  switch (currentState) {
    case CLOSED:
      // Gate is closed, ready for Python commands
      break;
      
    case OPENING:
      // Opening completed in openGate() function
      break;
      
    case OPEN:
      // Check for auto-close timeout
      if (millis() - gateOpenTime > AUTO_CLOSE_TIME) {
        // Only auto-close if no obstacle detected
        if (!obstaclePresent) {
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
      // Obstacle detection handled in closeGate() function
      break;
      
    case BLOCKED:
      // Wait for obstacle to clear
      if (!obstaclePresent) {
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

// ============================
// Status Functions
// ============================
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
  Serial.print("OBSTACLE_PRESENT:");
  Serial.println(obstaclePresent ? "YES" : "NO");
  
  if (currentState == OPEN) {
    unsigned long timeRemaining = AUTO_CLOSE_TIME - (millis() - gateOpenTime);
    if (timeRemaining > 0) {
      Serial.print("AUTO_CLOSE_IN:");
      Serial.print(timeRemaining / 1000);
      Serial.println("s");
    }
  }
  Serial.println("==================");
}

// ============================
// Setup and Main Loop
// ============================
void setup() {
  initializeSerial();
  initializeUltrasonic();
  initializeLEDs();
  initializeBuzzer();
  initializeHardcodedGrounds();
  initializeServo();
  testIndicators();
  
  Serial.println("GATE_CONTROLLER_READY");
  Serial.println("Waiting for Python license plate detection...");
  Serial.println("Commands: 1=Open (from Python), 0=Close, S=Status");
  Serial.println("Current State: CLOSED");
  
  delay(1000); // Allow servo to settle
}

void loop() {
  // Read distance with error handling
  float distance = getAverageDistance();
  
  // Send distance reading to Python
  if (distance > 0) {
    Serial.print("DISTANCE:");
    Serial.println(distance, 1);
  } else {
    Serial.println("DISTANCE:ERROR");
  }
  
  // Process serial commands from Python
  handleSerialCommands();
  
  // Handle gate state machine
  handleGateStateMachine(distance);
  
  // Handle buzzer for obstacle alerts
  handleBuzzer();
  
  delay(100); // Main loop delay
}