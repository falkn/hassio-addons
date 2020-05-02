/****
 * Serial MQTT Bridge Test Bed.
 * 
 * Sends a status message on the serial port every 10s.
 * Echos any incoming message.
 */

#include <ESP8266WiFi.h>

const int SERIAL_BAUD = 74880;
const int STATUS_PERIOD_MS = 10000;

ADC_MODE(ADC_VCC);

String readSerialUntil(char terminator='\n', int max_len=1024, int timeout_ms=1000) {
  char received_chars[max_len + 1];
  int32 len = 0;

  if (!Serial.available()) {
    return "";
  }

  while (true) {
    int timeout = millis() + timeout_ms;
    while (Serial.available() == 0) {
      if (millis() > timeout) {
        break;
      }
      delay(4);
    }

    int32 new_byte = Serial.read();
    if (new_byte == -1) {
      // Serial timeout
      break;
    }
    char new_char = char(new_byte);
    if (new_char == terminator) {
      break;
    }

    received_chars[len] = new_char;
    len++;

    if (len >= max_len) {
      break;
    }

    if (millis() > timeout) {
      break;
    }
  }

  received_chars[len] = '\0';
  return String(received_chars);
}

uint64_t uptime_millis64() {
  static uint32_t low32, high32;
  uint32_t new_low32 = millis();
  if (new_low32 < low32) high32++;
  low32 = new_low32;
  return (uint64_t) high32 << 32 | low32;
}

void loopStatus() {
  static uint64_t next_uptime_ms = 0;
  uint64_t uptime_ms = uptime_millis64();
  
  if (uptime_ms >= next_uptime_ms) {
    #ifdef ESP8266
      float vcc = ((float)ESP.getVcc() / 1024);
      int mem_free_bytes = ESP.getFreeHeap();
      int cpu_mhz = ESP.getCpuFreqMHz();
      int chip_id = ESP.getChipId();
      Serial.printf(
        "{\"topic\": \"status\", \"msg\": {\"uptime_ms\": %d, \"vcc\": %f, \"free_heap_bytes\": %d, \"cpu_mhz\": %d, \"chip_id\": %d}}\n",
        next_uptime_ms, vcc, mem_free_bytes, cpu_mhz, chip_id);
    #else
      Serial.printf("{\"topic\": \"status\", \"msg\": {\"uptime_ms\": %d}}\n", next_uptime_ms);
    #endif

    next_uptime_ms += STATUS_PERIOD_MS;
  }
}

void loopEcho() {
  if(Serial.available()){
    // Read serial
    String input = readSerialUntil('\n', 1024);
    if (input == "") {
      return;
    }
    // Escape for json string.
    input.replace("\"", "\\\"");

    Serial.printf("{\"topic\": \"echo\", \"msg\": \"%s\"}\n", input.c_str());
  }
}

void setup() {
  // put your setup code here, to run once:
  Serial.begin(SERIAL_BAUD);
  while (!Serial) continue;

  Serial.println("Serial Testbed starting");

  randomSeed(micros());

  //Turn off WiFi to save power
  WiFi.mode(WIFI_OFF);

  Serial.println("Serial Testbed started");
}

void loop() {
  // Echo input commands
  loopEcho();
  // Output status once in a while.
  loopStatus();
  delay(10);
}
