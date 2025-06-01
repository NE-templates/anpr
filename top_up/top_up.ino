#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 10
#define RST_PIN 9
MFRC522 rfid(SS_PIN, RST_PIN);
MFRC522::MIFARE_Key key;

void setup() {
  Serial.begin(9600);
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("RFID Card Writer Ready!");
  Serial.println("Place your RFID card...");
}

void loop() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    return;
  }

  Serial.print("Card UID:");
  for (byte i = 0; i < rfid.uid.size; i++) {
    Serial.print(rfid.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(rfid.uid.uidByte[i], HEX);
  }
  Serial.println();

  byte plateBlock = 1;
  byte balanceBlock = 2;
  byte data[16];
  memset(data, 0, 16);

  // --- Plate Number Input and Validation ---
  String plate = "";
  bool validPlate = false;
  
  while (!validPlate) {
    Serial.println("Enter plate number (must start with 'RA' and be exactly 7 characters):");
    while (!Serial.available());
    plate = Serial.readStringUntil('\n');
    plate.trim();
    plate.toUpperCase(); // Convert to uppercase for consistency

    // Validate plate format: starts with RA and exactly 7 characters
    if (plate.length() != 7) {
      Serial.println("[ERROR] Plate must be exactly 7 characters long.");
      continue;
    }
    
    if (!plate.startsWith("RA")) {
      Serial.println("[ERROR] Plate must start with 'RA'.");
      continue;
    }

    // Validate that all characters are alphanumeric
    bool isAlphaNum = true;
    for (int i = 0; i < plate.length(); i++) {
      if (!isAlphaNumeric(plate.charAt(i))) {
        isAlphaNum = false;
        break;
      }
    }
    
    if (!isAlphaNum) {
      Serial.println("[ERROR] Plate must contain only alphanumeric characters.");
      continue;
    }

    validPlate = true;
  }

  // Pad plate to 8 characters for storage (add one space at the end)
  plate += ' ';
  plate.getBytes(data, 16);

  // Authenticate and Write Plate
  for (byte i = 0; i < 6; i++) key.keyByte[i] = 0xFF;
  MFRC522::StatusCode status = rfid.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, plateBlock, &key, &(rfid.uid));
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Plate auth failed: "); Serial.println(rfid.GetStatusCodeName(status));
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  }

  status = rfid.MIFARE_Write(plateBlock, data, 16);
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Plate write failed: "); Serial.println(rfid.GetStatusCodeName(status));
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  } else {
    Serial.println("Plate number written successfully!");
  }

  delay(1000);

  // --- Balance Input and Validation ---
  float balance = 0.0;
  bool validBalance = false;
  
  while (!validBalance) {
    Serial.println("Enter balance amount (minimum 100.00 RWF, maximum 99,999,999.99 RWF):");
    while (!Serial.available());
    String balanceStr = Serial.readStringUntil('\n');
    balanceStr.trim();

    // Check if input is a valid number
    if (balanceStr.length() == 0) {
      Serial.println("[ERROR] Please enter a valid number.");
      continue;
    }

    // Convert to float
    balance = balanceStr.toFloat();
    
    // Check if conversion was successful (toFloat returns 0 for invalid strings)
    if (balance == 0.0 && balanceStr != "0" && balanceStr != "0.0" && balanceStr != "0.00") {
      Serial.println("[ERROR] Invalid number format.");
      continue;
    }

    // Validate minimum balance
    if (balance < 100.0) {
      Serial.println("[ERROR] Balance must be at least 100.00 RWF.");
      continue;
    }
    
    // Validate maximum balance (8 digits: 99,999,999.99)
    if (balance > 99999999.99) {
      Serial.println("[ERROR] Balance cannot exceed 99,999,999.99 RWF (8 digits maximum).");
      continue;
    }
    
    // Check for negative values
    if (balance < 0) {
      Serial.println("[ERROR] Balance must be positive.");
      continue;
    }

    validBalance = true;
  }

  // Display summary and confirm
  Serial.println("\n--- SUMMARY ---");
  Serial.print("Plate Number: "); Serial.println(plate.substring(0, 7)); // Show only 7 chars
  Serial.print("Balance: "); Serial.print(balance, 2); Serial.println(" RWF");
  Serial.println("Proceed with writing to card? (y/n)");
  
  while (!Serial.available());
  char confirm = Serial.read();
  // Clear any remaining characters in buffer
  while (Serial.available()) Serial.read();
  
  if (confirm != 'y' && confirm != 'Y') {
    Serial.println("Operation cancelled by user.");
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  }

  // Write balance to card
  byte balanceData[16];
  memset(balanceData, 0, 16);
  memcpy(balanceData, &balance, sizeof(balance));

  status = rfid.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, balanceBlock, &key, &(rfid.uid));
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Balance auth failed: "); Serial.println(rfid.GetStatusCodeName(status));
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  }

  status = rfid.MIFARE_Write(balanceBlock, balanceData, 16);
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Balance write failed: "); Serial.println(rfid.GetStatusCodeName(status));
  } else {
    Serial.println("Balance written successfully!");
  }

  delay(1000);

  // --- Verification: Read and Display Stored Data ---
  Serial.println("\n--- VERIFICATION ---");
  
  byte readBuffer[18];
  byte size = sizeof(readBuffer);

  // Read plate number
  status = rfid.MIFARE_Read(plateBlock, readBuffer, &size);
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Plate read failed: "); Serial.println(rfid.GetStatusCodeName(status));
  } else {
    Serial.print("Stored plate number: ");
    for (int i = 0; i < 7; i++) { // Only display first 7 characters
      Serial.print((char)readBuffer[i]);
    }
    Serial.println();
  }

  // Read balance
  size = sizeof(readBuffer); // Reset size
  status = rfid.MIFARE_Read(balanceBlock, readBuffer, &size);
  if (status != MFRC522::STATUS_OK) {
    Serial.print("Balance read failed: "); Serial.println(rfid.GetStatusCodeName(status));
  } else {
    float storedBalance;
    memcpy(&storedBalance, readBuffer, sizeof(float));
    Serial.print("Stored balance: ");
    Serial.print(storedBalance, 2);
    Serial.println(" RWF");
  }

  Serial.println("\nCard programming completed successfully!");
  Serial.println("Remove card and place a new one to continue...\n");

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  
  delay(3000); // Wait before next card
}