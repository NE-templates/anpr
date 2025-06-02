#include <Servo.h>

// Pin Definitions
#define TRIGGER_PIN 2
#define ECHO_PIN 3
#define RED_LED_PIN 4
#define BLUE_LED_PIN 5
#define SERVO_PIN 6
#define GND_PIN_1 7
#define GND_PIN_2 8
#define BUZZER_PIN 12

// System State
bool gateOpen = false;
unsigned long lastBuzzTime = 0;
unsigned long lastDistanceTime = 0;
const unsigned long buzzInterval = 300;
const unsigned long distanceInterval = 100; // Send distance every 100ms
bool buzzerState = false;
bool alertActive = false;
unsigned long alertStartTime = 0;
const unsigned long alertDuration = 4000; // 4 seconds alert duration

Servo barrierServo;

// ================== INITIALIZATION ==================
void initializeSerial()
{
  Serial.begin(9600);
  while (!Serial) {
    ; // Wait for serial port to connect
  }
}

void initializeUltrasonic()
{
  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
}

void initializeLEDs()
{
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(BLUE_LED_PIN, OUTPUT);
}

void initializeBuzzer()
{
  pinMode(BUZZER_PIN, OUTPUT);
}

void initializeHardcodedGrounds()
{
  pinMode(GND_PIN_1, OUTPUT);
  pinMode(GND_PIN_2, OUTPUT);
  digitalWrite(GND_PIN_1, LOW);
  digitalWrite(GND_PIN_2, LOW);
}

void initializeServo()
{
  barrierServo.attach(SERVO_PIN);
  setGatePosition(6); // Start with closed gate
}

// ================== CORE FUNCTIONS ==================
float measureDistance()
{
  digitalWrite(TRIGGER_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIGGER_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIGGER_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout
  if (duration == 0) {
    return 400; // Return max distance if no echo received
  }
  
  float distance = (duration * 0.0343) / 2.0;
  
  // Validate distance range (HC-SR04 specs: 2cm to 400cm)
  if (distance < 2) distance = 2;
  if (distance > 400) distance = 400;
  
  return distance;
}

void setGatePosition(int angle)
{
  barrierServo.write(angle);
}

// ================== GATE CONTROL ==================
void openGate()
{
  if (alertActive)
    return; // Prevent opening during alerts
    
  setGatePosition(90);
  gateOpen = true;
  digitalWrite(BLUE_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, LOW);
  Serial.println("[GATE] Opened");
}

void closeGate()
{
  setGatePosition(6);
  gateOpen = false;
  digitalWrite(BLUE_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, HIGH);
  Serial.println("[GATE] Closed");
}

// ================== ALERT SYSTEM ==================
void triggerAlert()
{
  alertActive = true;
  alertStartTime = millis();
  digitalWrite(RED_LED_PIN, HIGH);
  digitalWrite(BUZZER_PIN, HIGH);
  Serial.println("[ALERT] Unpaid vehicle detected!");
}

void stopAlert()
{
  alertActive = false;
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.println("[ALERT] Cleared");
}

void handleAlertTimeout()
{
  if (alertActive)
  {
    unsigned long currentMillis = millis();
    if (currentMillis - alertStartTime >= alertDuration)
    {
      stopAlert();
      Serial.println("[ALERT] Auto-stopped after 4 seconds");
    }
  }
}

// ================== DISTANCE REPORTING ==================
void sendDistanceReading()
{
  unsigned long currentMillis = millis();
  if (currentMillis - lastDistanceTime >= distanceInterval)
  {
    float distance = measureDistance();
    // Send just the distance value as expected by Python scripts
    Serial.println(distance);
    lastDistanceTime = currentMillis;
  }
}

// ================== COMMAND HANDLER ==================
void handleSerialCommands()
{
  if (Serial.available())
  {
    char cmd = Serial.read();
    
    // Clear any remaining characters in buffer
    while (Serial.available()) {
      Serial.read();
    }
    
    switch (cmd)
    {
    case '1': // Open gate
      openGate();
      break;
    case '0': // Close gate
      closeGate();
      break;
    case '2': // Trigger alert
      triggerAlert();
      break;
    case '3': // Stop alert (manual override)
      stopAlert();
      break;
    default:
      // Ignore unknown commands silently to avoid cluttering serial output
      break;
    }
  }
}

// ================== BUZZER CONTROL ==================
void handleBuzzer()
{
  if (gateOpen && !alertActive)
  {
    unsigned long currentMillis = millis();
    if (currentMillis - lastBuzzTime >= buzzInterval)
    {
      buzzerState = !buzzerState;
      digitalWrite(BUZZER_PIN, buzzerState);
      lastBuzzTime = currentMillis;
    }
  }
  else if (!gateOpen && !alertActive)
  {
    // Ensure buzzer is off when gate is closed and no alert
    digitalWrite(BUZZER_PIN, LOW);
    buzzerState = false;
  }
}

// ================== MAIN LOOP ==================
void setup()
{
  initializeSerial();
  initializeUltrasonic();
  initializeLEDs();
  initializeBuzzer();
  initializeHardcodedGrounds();
  initializeServo();
  
  // Initial state
  digitalWrite(RED_LED_PIN, HIGH); // Closed gate indicator
  Serial.println("[SYSTEM] Arduino Gate Controller Ready");
  delay(100);
}

void loop()
{
  // 1. Send distance readings to Python (most important for your system)
  sendDistanceReading();
  
  // 2. Handle commands from Python
  handleSerialCommands();
  
  // 3. Handle alert timeout
  handleAlertTimeout();
  
  // 4. Handle buzzer for gate open indication
  handleBuzzer();
  
  delay(10); // Short delay to prevent overwhelming the serial port
}