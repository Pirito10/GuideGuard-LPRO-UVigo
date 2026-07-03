const http = require('http');
const { Server } = require('socket.io');
const mqtt = require('mqtt');
const fs = require('fs');
const path = require('path');
const net = require('net');

// --- 1. CONFIGURACIÓN Y RUTAS ---
const SOCKET_PORT = 4000;
const TCP_PORT = 5000;
const DB_PATH = path.join(__dirname, 'devices.json');

// --- PARÁMETROS DE ALARMA ---
const UMBRAL_ALARMA = 1.5;          // Metros para disparar la alerta
const TIMEOUT_DESAPARECIDO = 3000;  // 3 segundos sin señal = apagar alarma (Watchdog)

// Mapas para rastrear el estado de las alarmas en tiempo real
const alarmasActivas = new Map();   // Guarda si la guía está pitando { uuid: true/false }
const timersAlarma = new Map();     // Guarda los temporizadores de desconexión

// --- 2. VARIABLES DE ESTADO GLOBALES ---
const clientesTCP = new Map();       // Sockets para control directo (Móviles)
const estadosEmision = new Map();     // Guarda si el móvil está en ON u OFF
const ultimaTelemetria = new Map();   // Guarda el último dato de señal recibido
const rssiHistory = {};              // { uuid: [{ rssi, timestamp }] }

// --- 3. INICIALIZACIÓN DE SERVIDORES Y CLIENTES ---
const httpServer = http.createServer();
const io = new Server(httpServer, { cors: { origin: "*" } });

// 🟢 MQTT: Declarado aquí arriba para evitar el error de "Cannot access before initialization"
const mqttClient = mqtt.connect('mqtt://127.0.0.1:1883');

const DASHBOARD_PASSWORD = "lprodays26";


// --- 4. GESTIÓN DE LA BASE DE DATOS (JSON) ---
if (!fs.existsSync(DB_PATH)) {
    fs.writeFileSync(DB_PATH, JSON.stringify([], null, 2));
}

const leerDB = () => {
    try {
        const data = fs.readFileSync(DB_PATH, 'utf8');
        return JSON.parse(data);
    } catch (e) {
        console.error("Error leyendo DB:", e);
        return [];
    }
};

const guardarDB = (data) => {
    try {
        fs.writeFileSync(DB_PATH, JSON.stringify(data, null, 2));
    } catch (e) {
        console.error("Error guardando DB:", e);
    }
};

const obtenerOAutoRegistrar = (uuid) => {
    let db = leerDB();
    const uuidLower = uuid.toLowerCase();
    let dispositivo = db.find(d => d.uuid.toLowerCase() === uuidLower);

    if (!dispositivo) {
        const numeroSiguiente = db.length + 1;
        const idGenerado = `GUIA_${numeroSiguiente.toString().padStart(2, '0')}`;
        dispositivo = { id: idGenerado, sala: "Autoasignado", uuid: uuidLower };
        db.push(dispositivo);
        guardarDB(db);
        console.log(`✨ Auto-registro: ${idGenerado} (${uuidLower})`);
        io.emit('init_db', db);
    }
    return dispositivo;
};

const enviarComandoTCP = (uuid, command) => {
    const socket = clientesTCP.get(uuid.toLowerCase());
    if (socket) {
        try {
            socket.write(JSON.stringify({ command }) + "\n");
            console.log(`🚨 [TCP -> MÓVIL] Orden ${command} enviada a ${uuid}`);
            return true;
        } catch (e) {
            console.error(`❌ Error enviando TCP a ${uuid}:`, e.message);
        }
    }
    return false;
};

// --- 5. SERVIDOR TCP (CONTROL DIRECTO A ANDROID) ---
const tcpServer = net.createServer((socket) => {
    let buffer = '';
    let currentUuid = null;

    console.log("🟢 [TCP] Intento de conexión desde dispositivo móvil");

    socket.on('data', (data) => {
        buffer += data.toString();
        let mensajes = buffer.split('\n');
        buffer = mensajes.pop();

        for (let msg of mensajes) {
            if (!msg.trim()) continue;
            try {
                const obj = JSON.parse(msg);
                const uuid = obj.uuid ? obj.uuid.toLowerCase() : currentUuid;

                if (obj.type === "register") {
                    currentUuid = uuid;
                    clientesTCP.set(currentUuid, socket);
                    console.log(`🔌 [TCP] Móvil vinculado: ${currentUuid}`);
                    io.emit('device_connection_status', { uuid: currentUuid, connected: true });
                } 
                // --- DENTRO DE tcpServer -> socket.on('data') -> for (let msg of mensajes) ---
                else if (obj.type === "status") {
                    const uuid = obj.uuid ? obj.uuid.toLowerCase() : currentUuid;
                    
                    // 1. Guardamos el estado del interruptor
                    estadosEmision.set(uuid, obj.isEmitting);

                    // 2. Sincronizamos telemetría con TODOS los campos de hardware
                    const datosPrevios = ultimaTelemetria.get(uuid) || {};
                    const nuevaTelemetria = {
                        ...datosPrevios,
                        battery: obj.battery,
                        // 🟢 NUEVOS DATOS DE HARDWARE
                        model: obj.model || datosPrevios.model || 'Desconocido',
                        android: obj.android || datosPrevios.android || '?',
                        storage: obj.storage || datosPrevios.storage || 0,
                        ip: obj.ip || datosPrevios.ip || '0.0.0.0',
                        temp: obj.temp || datosPrevios.temp || '--',
                        t: new Date().toLocaleTimeString()
                    };
                    ultimaTelemetria.set(uuid, nuevaTelemetria);

                    // 3. Actualización del Historial (Mantenemos RSSI y Batería para gráficas)
                    if (!rssiHistory[uuid]) rssiHistory[uuid] = [];
                    rssiHistory[uuid].push({ 
                        rssi: datosPrevios.rssi || null,
                        battery: obj.battery, 
                        timestamp: Date.now() 
                    });
                    if (rssiHistory[uuid].length > 100) rssiHistory[uuid].shift();

                    console.log(`📡 [TCP] Info ${uuid}: Bat=${obj.battery}% | Mod=${nuevaTelemetria.model} | Temp=${nuevaTelemetria.temp}°C`);

                    // 4. Enviamos la actualización completa al Dashboard
                    io.emit('device_status_update', { 
                        uuid, 
                        isEmitting: obj.isEmitting,
                        battery: obj.battery,
                        // 🟢 Pasamos los nuevos datos a React
                        model: nuevaTelemetria.model,
                        storage: nuevaTelemetria.storage,
                        temp: nuevaTelemetria.temp,
                        ip: nuevaTelemetria.ip,
                        android: nuevaTelemetria.android
                    });
                }
            } catch (e) { console.error("⚠️ Error JSON TCP:", e.message); }
        }
    });

    socket.on('close', () => {
        if (currentUuid) {
            clientesTCP.delete(currentUuid);
            console.log(`❌ [TCP] Móvil desconectado: ${currentUuid}`);
            io.emit('device_connection_status', { uuid: currentUuid, connected: false });
        }
    });

    socket.on('error', (err) => console.error("⚠️ TCP Error:", err.message));
});

// --- 6. LÓGICA MQTT (RECIBE DEL ESCÁNER DE PYTHON) ---
mqttClient.on('connect', () => {
    console.log("🟢 Conectado al broker MQTT");
    mqttClient.subscribe('museo/audioguias');
});

mqttClient.on('message', (topic, message) => {
    try {
        const data = JSON.parse(message.toString());
        const uuid = data.uuid.toLowerCase();
        const dist = data.dist; // Distancia calculada que viene de Python

        // --- 🚨 INICIO LÓGICA DE ALARMA ---
        
        // A. Resetear el Watchdog (Si recibimos señal, el móvil NO ha desaparecido)
        if (timersAlarma.has(uuid)) {
            clearTimeout(timersAlarma.get(uuid));
        }

        

        // B. Crear temporizador: Si en 3s no llega nada más, apagamos la alarma por seguridad
        const timeout = setTimeout(() => {
            if (alarmasActivas.get(uuid)) {
                console.log(`⏱️ [Watchdog] ${uuid} fuera de rango. Deteniendo alarma.`);
                enviarComandoTCP(uuid, "STOP_ALARM");
                alarmasActivas.set(uuid, false);
                io.emit('alarm_status', { uuid, active: false });
            }
        }, TIMEOUT_DESAPARECIDO);
        timersAlarma.set(uuid, timeout);

        // El servidor ya no calcula distancias, solo obedece a Python
        const ordenDeAlarmaDesdePython = data.alarma; 
        const yaEstabaSonando = alarmasActivas.get(uuid) || false;

        if (ordenDeAlarmaDesdePython && !yaEstabaSonando) {
            // Solo suena si Python dice que 'alarma' es true
            if (enviarComandoTCP(uuid, "ALARM")) {
                alarmasActivas.set(uuid, true);
                io.emit('alarm_status', { uuid, active: true });
            }
        }

        // --- 🚨 FIN LÓGICA DE ALARMA ---

        // (Tu lógica de telemetría y base de datos continúa aquí...)
        const registro = obtenerOAutoRegistrar(uuid);
        
        // Enviamos al Dashboard incluyendo el estado de la alarma
        io.emit('update_audioguia', {
            uuid: uuid,
            id: obtenerOAutoRegistrar(uuid).id,
            distance: data.dist,
            status: data.status, // Aquí llega 'seguro', 'cerca_salida' o 'saliendo'
            rssi: data.rssi,
            alarm: ordenDeAlarmaDesdePython,
            t: new Date().toLocaleTimeString()
        });

    } catch (e) { console.error("Error procesando MQTT:", e.message); }
});

// --- 7. LÓGICA SOCKET.IO (CONEXIÓN CON DASHBOARD REACT) ---
io.on('connection', (socket) => {
    console.log("💻 Dashboard React conectado");

    // Añade esta línea al principio de la conexión de socket.io
    socket.emit('initial_alarms', Object.fromEntries(alarmasActivas));

    // 🔄 Sincronización inicial (Para que al refrescar no salga vacío)
    socket.emit('init_db', leerDB());
    socket.emit('initial_tcp_connections', Array.from(clientesTCP.keys()));
    socket.emit('initial_emitting_states', Object.fromEntries(estadosEmision));
    socket.emit('initial_telemetry', Object.fromEntries(ultimaTelemetria));

    // Evento para pedir historial de un dispositivo (Gráficas)
    socket.on('get_device_history', (uuid) => {
    try {
        // Validación radical: si no es un string, abortamos antes de que pete
        if (!uuid || typeof uuid !== 'string') {
            console.log("⚠️ Intento de historial con UUID inválido recibido");
            return;
        }

        const uuidLower = uuid.toLowerCase();
        // Nos aseguramos de enviar SIEMPRE un array, aunque sea vacío
        const history = rssiHistory[uuidLower] || [];
        
        socket.emit('device_history', {
            uuid: uuidLower,
            history: history
        });
    } catch (e) {
        console.error("❌ Error en get_device_history:", e.message);
    }
});

    // 🟢 CONTROL REMOTO (TCP Directo al móvil)
    socket.on('send_tcp_command', (data) => {
        const { uuid, command } = data;
        const clientSocket = clientesTCP.get(uuid.toLowerCase());
        if (clientSocket) {
            clientSocket.write(JSON.stringify({ command }) + "\n");
            console.log(`🚀 Orden ${command} enviada vía TCP a ${uuid}`);
        } else {
            console.log(`⚠️ No se puede enviar comando: ${uuid} está offline en TCP`);
        }
    });

    // 🟡 CONTROL REMOTO (Vía MQTT - Por si lo sigues usando)
    socket.on('toggle_remote_device', (data) => {
        const { uuid, command } = data;
        const topic = `museo/control/${uuid}`;
        mqttClient.publish(topic, command, { qos: 1 });
        console.log(`📡 Orden ${command} enviada vía MQTT a ${uuid}`);
    });

    // Gestión de Dispositivos (CRUD)
    socket.on('add_device', (newDevice) => {
        let db = leerDB();
        if (!db.find(d => d.uuid.toLowerCase() === newDevice.uuid.toLowerCase())) {
            db.push({ ...newDevice, uuid: newDevice.uuid.toLowerCase() });
            guardarDB(db);
            io.emit('init_db', db);
        }
    });

    socket.on('delete_device', (id) => {
        let db = leerDB().filter(d => d.id !== id);
        guardarDB(db);
        io.emit('init_db', db);
    });

    socket.on('update_device_info', (updated) => {
        let db = leerDB().map(d => 
            d.uuid.toLowerCase() === updated.uuid.toLowerCase() 
            ? { ...d, id: updated.id, sala: updated.sala } : d
        );
        guardarDB(db);
        io.emit('init_db', db);
    });

    socket.on('disconnect', () => console.log("❌ Dashboard desconectado"));

    socket.on('login_dashboard', (password) => {
        if (password === DASHBOARD_PASSWORD) {
            socket.emit('login_response', { success: true });
        } else {
            socket.emit('login_response', { success: false, message: "Contraseña incorrecta" });
        }
    });

    socket.on('batch_tcp_command', (data) => {
    const { ids, cmd } = data; // ids es el array de selectedIds
    const db = leerDB();
    
    ids.forEach(id => {
        const dev = db.find(d => d.id === id);
        if (dev) {
            const clientSocket = clientesTCP.get(dev.uuid.toLowerCase());
            if (clientSocket) {
                clientSocket.write(JSON.stringify({ command: cmd }) + "\n");
            }
        }
    });
    });

    // --- ACCIÓN: ELIMINAR VARIOS ---
    socket.on('batch_delete_devices', (ids) => {
        let db = leerDB().filter(d => !ids.includes(d.id));
        guardarDB(db);
        io.emit('init_db', db);
    });

    socket.on('batch_update_rooms', (data) => {
        const { ids, nuevaSala } = data;
        let db = leerDB();

        // Actualizamos la sala de todos los que coincidan con los IDs enviados
        db = db.map(dispositivo => {
            if (ids.includes(dispositivo.id)) {
                return { ...dispositivo, sala: nuevaSala };
            }
            return dispositivo;
        });

        guardarDB(db);
        io.emit('init_db', db); // Avisamos a todos los dashboards del cambio
        console.log(`✅ Actualización masiva: ${ids.length} guías movidas a ${nuevaSala}`);
    });

    // --- ACCIÓN: AÑADIR VARIOS (Importación masiva) ---
    socket.on('batch_add_devices', (newDevices) => {
        let db = leerDB();
        newDevices.forEach(dev => {
            if (!db.find(d => d.uuid.toLowerCase() === dev.uuid.toLowerCase())) {
                db.push({ ...dev, uuid: dev.uuid.toLowerCase() });
            }
        });
        guardarDB(db);
        io.emit('init_db', db);
    });

    

});


// --- 8. ARRANQUE DE SERVIDORES ---
tcpServer.listen(TCP_PORT, '0.0.0.0', () => {
    console.log(`🚀 Servidor TCP (Control Móvil) en puerto ${TCP_PORT}`);
});

httpServer.listen(SOCKET_PORT, () => {
    console.log(`🚀 Servidor WebSockets (React) en puerto ${SOCKET_PORT}`);
});