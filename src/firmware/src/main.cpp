#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>

// --- CONFIGURACIÓN DE RED ---
const char *WIFI_SSID = "GuideGuard";
const char *WIFI_PASSWORD = "LPRO11";
const char *MQTT_BROKER = "192.168.X.Y";
const int MQTT_PORT = 1883;

// --- CONFIGURACIÓN DE TÓPICOS Y FILTROS ---
const char *MQTT_TOPIC_RAW = "museo/audioguias/raw";
const char *UUID_PREFIX = "550e8400-e29b-41d4-a716-";

// --- OBJETOS GLOBALES ---
WiFiClient espClient;
PubSubClient mqttClient(espClient);
BLEScan *pBLEScan;
String espID; // ID único basado en la MAC
unsigned long lastMqttRetry = 0;

// --- GESTIÓN DE CONEXIÓN WIFI ---
// Implementa la lógica de espera parcial para no bloquear el procesador
void verificarWiFi()
{
  if (WiFi.status() != WL_CONNECTED)
  {
    Serial.println("\n[WIFI] Conexión perdida. Reintentando...");
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int intentos = 0;
    while (WiFi.status() != WL_CONNECTED && intentos < 20)
    {
      delay(500);
      Serial.print(".");
      intentos++;
    }

    if (WiFi.status() == WL_CONNECTED)
    {
      Serial.println("\n[WIFI] Conectado. IP: " + WiFi.localIP().toString());
    }
  }
}

// --- GESTIÓN DE CONEXIÓN MQTT (NO BLOQUEANTE) ---
// Utiliza un temporizador para intentar conectar sin detener el escaneo BLE
void verificarMQTT()
{
  if (WiFi.status() != WL_CONNECTED)
    return;

  if (!mqttClient.connected())
  {
    unsigned long ahora = millis();
    if (ahora - lastMqttRetry > 5000)
    {
      lastMqttRetry = ahora;
      Serial.print("[MQTT] Intentando conectar como " + espID + "...");

      if (mqttClient.connect(espID.c_str()))
      {
        Serial.println(" ¡Conectado!");
      }
      else
      {
        Serial.print(" Error, rc=");
        Serial.print(mqttClient.state());
        Serial.println(" Reintento en 5s");
      }
    }
  }
}

// --- CALLBACK AL DETECTAR BEACON ---
class MyAdvertisedDeviceCallbacks : public BLEAdvertisedDeviceCallbacks
{
  void onResult(BLEAdvertisedDevice advertisedDevice)
  {
    // 1. Filtro básico de seguridad
    if (!advertisedDevice.haveServiceUUID())
      return;

    std::string uuid = advertisedDevice.getServiceUUID().toString();

    // 2. Filtrado por prefijo de audioguía
    if (uuid.rfind(UUID_PREFIX, 0) != 0)
      return;

    // 3. Envío de datos si hay conexión con el Broker
    if (mqttClient.connected())
    {
      int rssi = advertisedDevice.getRSSI();

      // Construcción del JSON con el ID del ESP emisor para el script de Python
      String payload = "{";
      payload += "\"esp\":\"" + espID + "\",";
      payload += "\"uuid\":\"" + String(uuid.c_str()) + "\",";
      payload += "\"rssi\":" + String(rssi);
      payload += "}";

      mqttClient.publish(MQTT_TOPIC_RAW, payload.c_str());
      Serial.println("[ENVÍO] " + payload);
    }
  }
};

// --- SETUP ---
void setup()
{
  Serial.begin(115200);

  // Identificación única: Crucial para la lógica de dos antenas
  espID = "ESP32-" + WiFi.macAddress();
  Serial.println("\n--- GUIDEGUARD NODE ---");
  Serial.println("ID ÚNICO: " + espID);

  verificarWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);

  // Configuración del motor BLE
  BLEDevice::init("");
  pBLEScan = BLEDevice::getScan();
  pBLEScan->setAdvertisedDeviceCallbacks(new MyAdvertisedDeviceCallbacks(), true);
  pBLEScan->setActiveScan(true);

  // Tiempos optimizados para coexistencia BLE/WiFi
  // Intervalo 160 (100ms) y Ventana 80 (50ms) permite procesar WiFi mientras el BLE descansa
  pBLEScan->setInterval(160);
  pBLEScan->setWindow(80);
}

// --- LOOP PRINCIPAL ---
void loop()
{
  // Mantener conectividad
  verificarWiFi();
  verificarMQTT();

  if (mqttClient.connected())
  {
    mqttClient.loop();
  }

  // Escaneo en ráfagas de 2 segundos para liberar memoria periódicamente
  pBLEScan->start(2, false);

  // Limpieza de resultados del escaneo para evitar fugas de memoria (Memory Leaks)
  pBLEScan->clearResults();

  delay(10);
}