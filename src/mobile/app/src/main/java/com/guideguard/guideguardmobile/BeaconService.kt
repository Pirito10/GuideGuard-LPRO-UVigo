package com.guideguard.guideguardmobile

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.ParcelUuid
import android.util.Log
import androidx.core.app.NotificationCompat
import java.util.UUID

class BeaconService : Service() {

    private var advertiser: BluetoothLeAdvertiser? = null
    private val CHANNEL_ID = "BeaconServiceChannel"

    private val advertiseCallback = object : AdvertiseCallback() {
        override fun onStartSuccess(settingsInEffect: AdvertiseSettings) {
            Log.i("BeaconService", "Emisión BLE iniciada correctamente")
        }

        override fun onStartFailure(errorCode: Int) {
            Log.e("BeaconService", "Error al iniciar emisión BLE. Código: $errorCode")
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        val notification: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("GuideGuard")
            .setContentText("Emitiendo señal de protección...")
            .setSmallIcon(android.R.drawable.ic_dialog_info) // Cambia por tu icono
            .build()

        // El ID no puede ser 0
        startForeground(1, notification)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val bluetoothManager = getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        val adapter: BluetoothAdapter? = bluetoothManager.adapter

        if (adapter != null && adapter.isEnabled) {
            advertiser = adapter.bluetoothLeAdvertiser
            startAdvertising()
        }
        return START_STICKY
    }

    private fun startAdvertising() {
        if (advertiser == null) return

        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY) // Emisión rápida
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH) // Máxima potencia
            .setConnectable(false)
            .build()

        // Leemos el UUID
        val prefs = getSharedPreferences("GuideGuardPrefs", Context.MODE_PRIVATE)
        val sufijo = prefs.getString("DEVICE_SUFFIX", "000000000000")
        val fullUuid = "550e8400-e29b-41d4-a716-$sufijo"

        val pUuid = ParcelUuid(UUID.fromString(fullUuid))

        val data = AdvertiseData.Builder()
            .setIncludeDeviceName(false)
            .addServiceUuid(pUuid)
            .build()

        try {
            advertiser?.startAdvertising(settings, data, advertiseCallback)
        } catch (e: SecurityException) {
            Log.e("BeaconService", "Permiso denegado para emitir")
        }
    }

    override fun onDestroy() {
        try {
            advertiser?.stopAdvertising(advertiseCallback)
        } catch (e: SecurityException) {
            Log.e("BeaconService", "Permiso denegado para detener emisión")
        }
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? {
        return null
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val serviceChannel = NotificationChannel(
                CHANNEL_ID,
                "Canal Servicio Beacon",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(serviceChannel)
        }
    }
}