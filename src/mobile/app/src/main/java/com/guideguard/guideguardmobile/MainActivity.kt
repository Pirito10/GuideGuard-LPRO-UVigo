package com.guideguard.guideguardmobile

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.Intent
import android.media.Ringtone
import android.media.RingtoneManager
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.guideguard.guideguardmobile.ui.theme.GuideGuardMobileTheme
import kotlinx.coroutines.delay
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.Socket
import java.util.UUID
import android.os.BatteryManager
import java.net.NetworkInterface
import java.net.Inet4Address


class MainActivity : ComponentActivity() {

    private val bluetoothAdapter: BluetoothAdapter? by lazy {
        (getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager).adapter
    }

    // 🔥 PON AQUÍ LA IP DE TU ORDENADOR (La misma que usas en el script de Python)
    private val TCP_SERVER_IP = "172.20.10.2"
    private val TCP_SERVER_PORT = 5000

    // Estado global de emisión
    private var isEmittingState = mutableStateOf(false)

    // 🟢 Guardamos el canal de salida TCP para avisar de nuestro estado
    private var tcpOut: PrintWriter? = null

    // 🟢 Variables para la Alarma (Sonido y Vibración)
    private var ringtone: Ringtone? = null
    private var vibrator: Vibrator? = null
    private var isAlarmActive = false

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        checkPermissions()

        // Iniciamos el motor TCP en segundo plano
        connectToTcpServer()

        setContent {
            GuideGuardMobileTheme {
                var isBluetoothEnabled by remember {
                    mutableStateOf(bluetoothAdapter?.isEnabled ?: false)
                }

                LaunchedEffect(Unit) {
                    while(true) {
                        isBluetoothEnabled = bluetoothAdapter?.isEnabled ?: false
                        delay(1000)
                    }
                }

                Surface(modifier = Modifier.fillMaxSize()) {
                    BeaconControlScreen(
                        isBluetoothEnabled = isBluetoothEnabled,
                        isEmitting = isEmittingState.value,
                        onToggleBeacon = { toggleEmitting() }
                    )
                }
            }
        }
    }

    // --- CONTROLES DE EMISIÓN ---
    private fun toggleEmitting() {
        if (isEmittingState.value) {
            handleStopAction()
            isEmittingState.value = false
        } else {
            if (handleStartAction()) {
                isEmittingState.value = true
            }
        }

        // Avisamos al servidor de que nuestro estado ha cambiado
        sendStatusToServer()
    }

    private fun handleStartAction(): Boolean {
        if (bluetoothAdapter == null || !bluetoothAdapter!!.isEnabled) {
            runOnUiThread { Toast.makeText(this, "⚠️ Activa el Bluetooth", Toast.LENGTH_LONG).show() }
            return false
        }
        val intent = Intent(this, BeaconService::class.java)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
            return true
        } catch (e: Exception) {
            return false
        }
    }

    private fun handleStopAction() {
        stopService(Intent(this, BeaconService::class.java))
    }


    private fun getBatteryLevel(): Int {
        val bm = getSystemService(BATTERY_SERVICE) as BatteryManager
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }

    private fun getLocalIpAddress(): String {
        try {
            val interfaces = java.net.NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val networkInterface = interfaces.nextElement()
                val addresses = networkInterface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    // Buscamos una dirección IPv4 que no sea la de bucle local (127.0.0.1)
                    if (!addr.isLoopbackAddress && addr is java.net.Inet4Address) {
                        return addr.hostAddress ?: "0.0.0.0"
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return "Desconocida"
    }

    private fun getBatteryTemperature(): Float {
        val intent = registerReceiver(null, android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED))
        val temp = intent?.getIntExtra(android.os.BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0
        return temp / 10f // Android devuelve la temperatura en décimas (ej: 355 es 35.5°C)
    }

    private fun getDeviceInfo(): Map<String, Any> {
        val stat = android.os.StatFs(android.os.Environment.getDataDirectory().path)
        val bytesAvailable = stat.blockSizeLong * stat.availableBlocksLong
        val totalBytes = stat.blockSizeLong * stat.blockCountLong
        val storagePercent = 100 - (bytesAvailable * 100 / totalBytes)

        return mapOf(
            "model" to "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}",
            "android" to android.os.Build.VERSION.RELEASE,
            "storage" to storagePercent.toInt(),
            "ip" to getLocalIpAddress(),
            "temp" to getBatteryTemperature() // 🌡️ ¡Añadido!
        )
    }

    // --- 🚨 LÓGICA DE ALARMA Y VIBRACIÓN ---
    private fun triggerAlarm() {
        if (isAlarmActive) return
        isAlarmActive = true
        runOnUiThread {
            // 1. Activaer Sonido
            try {
                val uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                ringtone = RingtoneManager.getRingtone(applicationContext, uri)
                ringtone?.play()
            } catch (e: Exception) { Log.e("ALARM", "Error de sonido") }

            // 2. Activar Vibración repetitiva
            try {
                vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
                val pattern = longArrayOf(0, 500, 500) // 0 pausa inicial, 500ms vibra, 500ms pausa...
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator?.vibrate(VibrationEffect.createWaveform(pattern, 0)) // El '0' hace que se repita infinito
                } else {
                    @Suppress("DEPRECATION")
                    vibrator?.vibrate(pattern, 0)
                }
            } catch (e: Exception) { Log.e("ALARM", "Error de vibración") }

            Toast.makeText(this, "🚨 ¡ALERTA DE SALIDA! 🚨", Toast.LENGTH_LONG).show()
        }
    }

    private fun stopAlarm() {
        if (!isAlarmActive) return
        isAlarmActive = false
        runOnUiThread {
            try {
                ringtone?.stop()
                vibrator?.cancel()
                Toast.makeText(this, "✅ Alarma desactivada", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {}
        }
    }

    // --- 📡 COMUNICACIÓN TCP CON EL SERVIDOR ---
    private fun sendStatusToServer() {
        val myUuid = getOrCreateDeviceUUID()
        val isEmitting = isEmittingState.value
        val batteryPct = getBatteryLevel()

        // 🟢 LLAMAMOS A LA FUNCIÓN QUE RECOGE TODO EL HARDWARE
        val infoHardware = getDeviceInfo()

        val json = org.json.JSONObject().apply {
            put("type", "status")
            put("uuid", myUuid)
            put("isEmitting", isEmitting)
            put("battery", batteryPct)

            // 🟢 AÑADIMOS LOS NUEVOS DATOS AL JSON
            put("model", infoHardware["model"])
            put("android", infoHardware["android"])
            put("storage", infoHardware["storage"])
            put("ip", infoHardware["ip"])
            put("temp", infoHardware["temp"])
        }

        val statusMsg = json.toString()

        Thread {
            try {
                tcpOut?.let { writer ->
                    writer.println(statusMsg)
                    Log.d("TCP", "Enviado con éxito: $statusMsg")
                }
            } catch (e: Exception) {
                Log.e("TCP", "Error enviando estado: ${e.message}")
            }
        }.start()
    }

    private fun connectToTcpServer() {
        val myUuid = getOrCreateDeviceUUID()

        Thread {
            while (true) {
                var socket: Socket? = null
                try {
                    Log.i("TCP", "Buscando servidor en $TCP_SERVER_IP:$TCP_SERVER_PORT...")
                    socket = Socket(TCP_SERVER_IP, TCP_SERVER_PORT)

                    tcpOut = PrintWriter(socket.getOutputStream(), true)
                    val input = BufferedReader(InputStreamReader(socket.getInputStream()))

                    // 1. Nos registramos
                    tcpOut?.println("""{"type":"register","uuid":"$myUuid"}""")

                    // 2. Enviamos el estado inicial al conectar
                    sendStatusToServer()
                    Log.i("TCP", "✅ Conectado y sincronizado con el servidor TCP")

                    // 3. Bucle de escucha infinita de comandos
                    var line: String?
                    while (input.readLine().also { line = it } != null) {
                        Log.i("TCP", "Orden recibida: $line")
                        try {
                            val json = JSONObject(line!!)
                            if (json.has("command")) {
                                val comando = json.getString("command").trim().uppercase()

                                runOnUiThread {
                                    if (comando == "ON") {
                                        if (!isEmittingState.value) {
                                            toggleEmitting() // Esto ya llama a sendStatusToServer() por dentro
                                            Toast.makeText(applicationContext, "⚡ Encendido remoto", Toast.LENGTH_SHORT).show()
                                        } else {
                                            // 🟢 ¡LA CLAVE! Si ya está encendido, forzamos el aviso al servidor para desatascar el Dashboard
                                            sendStatusToServer()
                                        }
                                    } else if (comando == "OFF") {
                                        if (isEmittingState.value) {
                                            toggleEmitting()
                                            Toast.makeText(applicationContext, "🛑 Apagado remoto", Toast.LENGTH_SHORT).show()
                                        } else {
                                            // 🟢 ¡LA CLAVE! Avisamos aunque ya esté apagado
                                            sendStatusToServer()
                                        }
                                    } else if (comando == "ALARM") {
                                        triggerAlarm()
                                    } else if (comando == "STOP_ALARM") {
                                        stopAlarm()
                                    }
                                }
                            }
                        } catch (e: Exception) {
                            Log.e("TCP", "JSON inválido: ${e.message}")
                        }
                    }
                } catch (e: Exception) {
                    Log.e("TCP", "Conexión perdida. Reconectando en 3s...")
                } finally {
                    tcpOut = null
                    try { socket?.close() } catch (e: Exception) {}
                }

                Thread.sleep(3000)
            }
        }.start()
    }

    private fun getOrCreateDeviceUUID(): String {
        val PREFIJO_GUIDEGUARD = "550e8400-e29b-41d4-a716-"
        val preferencias = getSharedPreferences("GuideGuardPrefs", Context.MODE_PRIVATE)
        var sufijo = preferencias.getString("DEVICE_SUFFIX", null)

        if (sufijo == null) {
            sufijo = UUID.randomUUID().toString().takeLast(12)
            preferencias.edit().putString("DEVICE_SUFFIX", sufijo).apply()
        }
        return PREFIJO_GUIDEGUARD + sufijo
    }

    private fun checkPermissions() {
        val permissions = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_ADVERTISE)
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            permissions.add(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        requestPermissionLauncher.launch(permissions.toTypedArray())
    }
}

// --- INTERFAZ GRÁFICA (UI) ---
@Composable
fun BeaconControlScreen(
    isBluetoothEnabled: Boolean,
    isEmitting: Boolean,
    onToggleBeacon: () -> Unit
) {
    val context = LocalContext.current
    val prefs = context.getSharedPreferences("GuideGuardPrefs", Context.MODE_PRIVATE)
    val myUuid = "550e8400-e29b-41d4-a716-" + (prefs.getString("DEVICE_SUFFIX", "DESCONOCIDO") ?: "")

    Box(modifier = Modifier.fillMaxSize()) {
        Image(
            painter = painterResource(id = R.drawable.fp_ggm),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop
        )

        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        colors = listOf(Color.Transparent, Color.Black.copy(alpha = 0.8f)),
                        startY = 800f
                    )
                )
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            verticalArrangement = Arrangement.Bottom,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = when {
                    !isBluetoothEnabled -> "BLUETOOTH DESACTIVADO"
                    isEmitting -> "PROTECCIÓN ACTIVADA"
                    else -> "SISTEMA PREPARADO"
                },
                style = TextStyle(
                    fontSize = 24.sp,
                    fontWeight = FontWeight.ExtraBold,
                    color = if (isEmitting && isBluetoothEnabled) Color(0xFF00FFEA) else Color.White,
                    shadow = Shadow(color = Color.Black, offset = Offset(2f, 2f), blurRadius = 4f)
                )
            )

            Spacer(modifier = Modifier.height(32.dp))

            Button(
                onClick = { onToggleBeacon() },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(65.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = when {
                        !isBluetoothEnabled && !isEmitting -> Color.DarkGray.copy(alpha = 0.9f)
                        isEmitting -> Color(0xFFE53935)
                        else -> Color(0xFF002D5A)
                    },
                    contentColor = Color.White
                ),
                elevation = ButtonDefaults.buttonElevation(defaultElevation = 8.dp)
            ) {
                Text(
                    text = if (isEmitting) "DETENER EMISIÓN" else "INICIAR PROTECCIÓN",
                    style = TextStyle(fontWeight = FontWeight.Bold, fontSize = 18.sp)
                )
            }

            Spacer(modifier = Modifier.height(30.dp))

            Text(
                text = "UUID: $myUuid",
                style = TextStyle(color = Color.Gray, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
            )
            Spacer(modifier = Modifier.height(20.dp))
        }
    }
}