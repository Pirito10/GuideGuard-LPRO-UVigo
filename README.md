# GuideGuard
_GuideGuard_ is a **Museum Audioguide Theft-Prevention System** developed as part of the course "[Laboratorio de Proyectos](https://secretaria.uvigo.gal/docnet-nuevo/guia_docent/?ensenyament=V05G301V01&assignatura=V05G301V01427&any_academic=2026_27)" in the Telecommunications Engineering Degree at the Universidad de Vigo (2025 - 2026).

## About The Project
This project implements a distributed BLE-based detection system that identifies when an Android terminal lent as an audioguide crosses the exit of a museum or other cultural venue, without requiring any hardware modification to the device. The system integrates concepts such as BLE beacon advertising, RSSI-based proximity and direction estimation, real-time signal filtering with a Kalman filter, MQTT-based distributed messaging, and a full-stack web dashboard for real-time monitoring.

The project features:
- Dual ESP32 BLE nodes per exit for direction-aware detection via RSSI comparison.
- Kalman-filtered RSSI processing for robust, low-latency distance estimation.
- ESP32 firmware with passive BLE scanning, UUID filtering, and MQTT publishing.
- Android app broadcasting BLE beacons with a unique per-terminal identifier.
- Remote alarm triggering with audible and vibration feedback on the terminal.
- Node.js web dashboard for real-time monitoring, incident history, and batch device management.
- MQTT and TCP-based communication between the ESP32 nodes, coordinator, and mobile app.

## How To Run
### Firmware
#### Hardware
This project was developed using the following hardware:
- [ESP32-DevKitC-32UE](https://www.espressif.com/en/products/devkits/esp32-devkitc)
- [5dBi omnidirectional dipole antenna](https://www.amphenolrf.com/en-us/assets/file/4070651115)

#### Requirements
Make sure you have [PlatformIO](https://platformio.org) installed on your system.

#### MQTT Broker
Make sure you have an MQTT broker (e.g. [Mosquitto](https://mosquitto.org)) installed and running, reachable by both ESP32 nodes and the coordinator.

#### Configuration
Open [`src/firmware/src/main.cpp`](src/firmware/src/main.cpp) to set your WiFi and MQTT broker credentials.

#### Compilation
Flash the firmware to two ESP32 boards with:
```bash
cd src/firmware
pio run --target upload
```

#### Coordinator
On the coordinator machine, run the receiver bridge with:
```bash
python src/firmware/receiver.py
```
*Some Python modules may need to be installed.*

### Mobile App
#### Requirements
Make sure you have [Android Studio](https://developer.android.com/studio) installed on your system.

#### Usage
Open or clone the [`src/mobile`](src/mobile) directory on Android Studio, and wait for the project to build. Then, select a target device and run the app by pressing `Shift + F10` or by clicking the `Run 'app'` button.

Alternatively, you can download and install the precompiled version from the [releases page](https://github.com/Pirito10/GuideGuard-LPRO-UVigo/releases/tag/1.0).

### Dashboard
#### Backend
##### Requirements
Make sure you have [Node.js](https://nodejs.org/en/download) installed on your system. Then install the required dependencies with:
```bash
cd src/dashboard/backend
npm install
```

##### Usage
Once the dependencies are installed, you can run the server with:
```bash
npm start
```

#### Frontend
##### Requirements
Make sure you have [Node.js](https://nodejs.org/en/download) installed on your system. Then install the required dependencies with:
```bash
cd src/dashboard/frontend
npm install
```

##### Usage
Once the dependencies are installed, you can run the server with:
```bash
npm run dev
```
Then, open your web browser and navigate to `http://localhost:5173`.

## About The Code
Refer to [`Memoria.pdf`](docs/Memoria.pdf) and [`Propuesta-de-Solución.pdf`](docs/Propuesta-de-Solución.pdf) for a full in-depth explanation of the project, the system architecture, the battery, signal filter, and antenna studies, and the test results.

Refer to [`docs/`](docs) for the full project documentation, including the state-of-the-art research, hardware selection process, meeting minutes, and presentation materials.