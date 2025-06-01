#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN 9
#define SS_PIN 10

MFRC522 mfrc522(SS_PIN, RST_PIN);
MFRC522::MIFARE_Key key;

const int PLATE_BLOCK = 1;
const int BALANCE_BLOCK = 2;
const unsigned long CARD_TIMEOUT = 5000; // 5 seconds timeout for card operations

void setup() {
  Serial.begin(9600);
  SPI.begin();
  mfrc522.PCD_Init();

  // Initialize authentication key
  for (byte i = 0; i < 6; i++) {
    key.keyByte[i] = 0xFF;
  }

  Serial.println("READY"); // Signal to Python that Arduino is ready
  Serial.println("Place your RFID card for payment...");
}

void loop() {
  // Check for new card
  if (!mfrc522.PICC_IsNewCardPresent()) {
    delay(50);
    return;
  }
  
  if (!mfrc522.PICC_ReadCardSerial()) {
    delay(50);
    return;
  }

  // Card detected - process payment
  bool success = processPayment();
  
  // Always halt the card and stop crypto
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  
  if (success) {
    Serial.println("Remove card and place next card...");
    delay(2000); // Give time to remove card
  }
  
  delay(100);
}

bool processPayment() {
  byte buffer[18];
  byte size = sizeof(buffer);
  MFRC522::StatusCode status;

  // Read Plate Number
  String plateNumber = readPlateNumber();
  if (plateNumber == "") {
    Serial.println("ERROR:PLATE_READ_FAILED");
    return false;
  }

  // Read Current Balance
  float currentBalance = readBalance();
  if (currentBalance < 0) {
    Serial.println("ERROR:BALANCE_READ_FAILED");
    return false;
  }

  // Send card info to Python
  Serial.print("PLATE:");
  Serial.print(plateNumber);
  Serial.print(";BALANCE:");
  Serial.println(currentBalance, 2);

  // Wait for payment amount from Python with timeout
  unsigned long startTime = millis();
  String input = "";
  
  while (!Serial.available()) {
    if (millis() - startTime > CARD_TIMEOUT) {
      Serial.println("ERROR:TIMEOUT");
      return false;
    }
    delay(10);
  }
  
  input = Serial.readStringUntil('\n');
  input.trim();
  
  // Check if Python sent an error or insufficient funds message
  if (input == "NO_ENTRY" || input == "INSUFFICIENT_PYTHON") {
    Serial.println("ABORTED");
    return false;
  }
  
  float amountDue = input.toFloat();
  
  // Validate amount
  if (amountDue <= 0) {
    Serial.println("ERROR:INVALID_AMOUNT");
    return false;
  }

  // Check if card has sufficient balance
  if (amountDue > currentBalance) {
    Serial.println("INSUFFICIENT");
    return false;
  }

  // Process payment - deduct amount from balance
  float newBalance = currentBalance - amountDue;
  
  if (writeBalance(newBalance)) {
    Serial.print("DONE:");
    Serial.print(amountDue, 2);
    Serial.print(":");
    Serial.println(newBalance, 2);
    return true;
  } else {
    Serial.println("ERROR:WRITE_FAILED");
    return false;
  }
}

String readPlateNumber() {
  byte buffer[18];
  byte size = sizeof(buffer);
  
  MFRC522::StatusCode status = mfrc522.PCD_Authenticate(
    MFRC522::PICC_CMD_MF_AUTH_KEY_A, PLATE_BLOCK, &key, &(mfrc522.uid)
  );
  
  if (status != MFRC522::STATUS_OK) {
    return "";
  }

  status = mfrc522.MIFARE_Read(PLATE_BLOCK, buffer, &size);
  if (status != MFRC522::STATUS_OK) {
    return "";
  }

  String plateNumber = "";
  for (int i = 0; i < 8; i++) { // Read up to 8 characters
    if (buffer[i] != 0 && isPrintable(buffer[i]) && buffer[i] != ' ') {
      plateNumber += (char)buffer[i];
    }
  }
  
  plateNumber.trim();
  return plateNumber;
}

float readBalance() {
  byte buffer[18];
  byte size = sizeof(buffer);
  
  MFRC522::StatusCode status = mfrc522.PCD_Authenticate(
    MFRC522::PICC_CMD_MF_AUTH_KEY_A, BALANCE_BLOCK, &key, &(mfrc522.uid)
  );
  
  if (status != MFRC522::STATUS_OK) {
    return -1;
  }

  status = mfrc522.MIFARE_Read(BALANCE_BLOCK, buffer, &size);
  if (status != MFRC522::STATUS_OK) {
    return -1;
  }

  float balance;
  memcpy(&balance, buffer, sizeof(float));
  
  // Validate balance (should be positive and reasonable)
  if (balance < 0 || balance > 99999999.99) {
    return -1;
  }
  
  return balance;
}

bool writeBalance(float newBalance) {
  byte writeBuffer[16];
  memset(writeBuffer, 0, sizeof(writeBuffer));
  memcpy(writeBuffer, &newBalance, sizeof(float));

  MFRC522::StatusCode status = mfrc522.PCD_Authenticate(
    MFRC522::PICC_CMD_MF_AUTH_KEY_A, BALANCE_BLOCK, &key, &(mfrc522.uid)
  );
  
  if (status != MFRC522::STATUS_OK) {
    return false;
  }

  status = mfrc522.MIFARE_Write(BALANCE_BLOCK, writeBuffer, 16);
  return (status == MFRC522::STATUS_OK);
}