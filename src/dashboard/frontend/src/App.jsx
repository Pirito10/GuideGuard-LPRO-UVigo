import React, { useEffect, useState } from 'react';
import io from 'socket.io-client';

// IMPORTANTE: Asegúrate de tener tu logo en esta ruta
import logo from './assets/logo.png';

import {
  Chart as ChartJS,
  registerables // 🟢 Registra todo: escalas, elementos, plugins, etc.
} from 'chart.js';

import { Line } from 'react-chartjs-2';

// Esto registra automáticamente CategoryScale, LinearScale, PointElement, etc.
ChartJS.register(...registerables);





const socket = io('http://localhost:4000');



// --- 1. PALETA DE COLORES (Estética SaaS Moderno) ---
const COLORS = {
  bg: '#16192B',
  sidebar: '#1E2136',
  card: '#1E2136',
  text: '#FFFFFF',
  textMuted: '#8F9BBA',
  magentaGrad: 'linear-gradient(135deg, #E052FF 0%, #9D44FF 100%)',
  cyanGrad: 'linear-gradient(135deg, #00F2FE 0%, #4FACFE 100%)',
  danger: '#FF4B8C',
  warn: '#FFB800',
  safe: '#00E5FF',
  inactive: '#4A5568',
  menuActive: '#22B573',
  menuHover: '#2A2E43'
};


const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    y: {
      grid: { color: 'rgba(255, 255, 255, 0.05)' },
      ticks: { color: '#8F9BBA' }
    },
    x: {
      grid: { display: false },
      ticks: { color: '#8F9BBA' }
    }
  },
  plugins: {
    legend: {
      display: false // Ocultamos la leyenda para que no estorbe
    }
  }
};


// --- 2. ANIMACIONES Y CSS GLOBAL ---
const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    body { 
      margin: 0; 
      background-color: ${COLORS.bg}; 
      font-family: 'Inter', sans-serif; 
      overflow: hidden; 
      color: ${COLORS.text};
    }
    
    /* --- ANIMACIONES --- */
    @keyframes pulseAlert {
      0% { box-shadow: inset 0 0 0px rgba(255, 75, 140, 0); background-color: rgba(255, 75, 140, 0.05); }
      50% { box-shadow: inset 0 0 15px rgba(255, 75, 140, 0.2); background-color: rgba(255, 75, 140, 0.15); }
      100% { box-shadow: inset 0 0 0px rgba(255, 75, 140, 0); background-color: rgba(255, 75, 140, 0.05); }
    }

    @keyframes slideDown {
      from { opacity: 0; transform: translateY(-10px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* --- SCROLLBAR --- */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-thumb { background: #3A3F58; border-radius: 10px; }
    
    .cat-hover:hover { filter: brightness(1.15); }
    .stat-hover:hover { transform: translateY(-5px); }
    .menu-item:hover { background-color: ${COLORS.menuHover}; }

    /* --- ESTILO DE INPUTS (Tu nuevo diseño) --- */
    input {
      background: #0d0f1a;
      border: 1px solid #00E5FF;
      border-radius: 4px;
      color: #00E5FF;
      padding: 15px;
      font-family: 'Courier New', monospace; /* Fuente de código */
      font-size: 1.2rem;
      outline: none;
      transition: all 0.3s;
      box-shadow: inset 0 0 5px rgba(0, 229, 255, 0.2);
      width: 100%;
      box-sizing: border-box;
    }

    input:focus { 
      border-color: #E052FF; 
      box-shadow: 0 0 15px rgba(224, 82, 255, 0.4);
    }

    /* --- BOTÓN CERRAR SESIÓN --- */
    .sign-out-btn {
      width: 100%;
      background: rgba(255, 75, 140, 0.1);
      border: 1px solid rgba(255, 75, 140, 0.3);
      padding: 18px;
      border-radius: 12px;
      color: ${COLORS.danger};
      font-size: 1.1rem;
      font-weight: 800;
      cursor: pointer;
      letter-spacing: 2px;
      transition: all 0.3s;
    }

    .sign-out-btn:hover {
      background: ${COLORS.danger};
      color: #FFF;
      box-shadow: 0 4px 15px rgba(255, 75, 140, 0.4);
    }
  `}</style>
);










// --- 3. COMPONENTE PRINCIPAL ---



function App() {

  const memoriaEstados = React.useRef({});

  const [isNotifOpen, setIsNotifOpen] = useState(true); // Controla si se ve o no
  const [notifications, setNotifications] = useState([]); // Lista de incidencias

  const [showBatchEditModal, setShowBatchEditModal] = useState(false);
  const [batchSala, setBatchSala] = useState(""); // La nueva sala para todos

  const [isBatchMenuOpen, setIsBatchMenuOpen] = useState(false);
  const [showBulkAddModal, setShowBulkAddModal] = useState(false);
  const [bulkData, setBulkData] = useState(""); // Para el texto de "Añadir en batch"
  const [selectedIds, setSelectedIds] = useState([]); // Guarda los IDs seleccionados

  const toggleSelection = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  // Estado para la navegación
  const [activeTab, setActiveTab] = useState('dashboard');
  const [editingDevice, setEditingDevice] = useState(null); // Para saber qué guía editamos



  // Estados originales
  const [guias, setGuias] = useState({});
  const [conectado, setConectado] = useState(false);
  const [accesoConcedido, setAccesoConcedido] = useState(false);
  const [showActivas, setShowActivas] = useState(true);
  const [showInactivas, setShowInactivas] = useState(true);
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');


  // --- NUEVOS ESTADOS: BASE DE DATOS (LOCAL STORAGE) ---
  const [dbGuias, setDbGuias] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [newDevice, setNewDevice] = useState({ id: '', sala: '', uuid: '' });



  const [selectedDevice, setSelectedDevice] = useState(null);
  const [deviceHistory, setDeviceHistory] = useState([]);



  const [rssiHistory, setRssiHistory] = useState([]);



  // --- LOGICA CRUD ---
  // 🟢 REGISTRAR: Envía al servidor para que lo guarde en el JSON
  const handleAddDevice = () => {
    if (!newDevice.id || !newDevice.uuid) return alert("ID y UUID son obrigatorios");

    socket.emit('add_device', newDevice);

    setNewDevice({ id: '', sala: '', uuid: '' });
    setShowModal(false);
  };



  // 🟢 BORRAR: Avisa al servidor para que lo quite del JSON
  const handleDeleteDevice = (id) => {
    if (window.confirm("¿Eliminar permanentemente do servidor?")) {
      socket.emit('delete_device', id);
    }
  };



  const handleUpdateDevice = () => {
    if (!editingDevice.id || !editingDevice.uuid) return alert("Datos obrigatorios");

    // Enviamos al servidor el ID original (para buscarlo) y los nuevos datos
    socket.emit('update_device_info', editingDevice);

    setEditingDevice(null); // Cerramos el modo edición
    setShowModal(false);
  };



  const handleRemotePower = (uuid, currentStatus) => {
    // Si el status es 'saliendo' o 'seguro', asumimos que está ON, enviamos OFF y viceversa
    // O puedes usar una lógica basada en si aparece en guiasActivas
    const command = currentStatus === 'inactivo' ? 'ON' : 'OFF';

    socket.emit('toggle_remote_device', {
      uuid: uuid,
      command: command
    });
  };

  const handleBatchUpdateSala = () => {
    if (!batchSala) return alert("Escribe o nome da nova sala");

    // Enviamos al servidor los IDs seleccionados y la nueva sala
    socket.emit('batch_update_rooms', {
      ids: selectedIds,
      nuevaSala: batchSala
    });

    // Limpiamos y cerramos
    setShowBatchEditModal(false);
    setBatchSala("");
    setSelectedIds([]); // Opcional: deseleccionar tras editar
  };

  const [tcpConnections, setTcpConnections] = useState({}); // { 'uuid': true/false }
  const [deviceEmittingState, setDeviceEmittingState] = useState({}); // { 'uuid': true/false }








  useEffect(() => {
    // 1. Conexión básica
    socket.on('connect', () => setConectado(true));
    socket.on('disconnect', () => setConectado(false));

    // 2. Base de datos e historiales
    socket.on('init_db', (data) => setDbGuias(data));

    socket.on('device_history', (data) => {
      // Solo actualizamos el historial, NO el dispositivo seleccionado
      if (data && Array.isArray(data.history)) {
        setRssiHistory(data.history);
      } else {
        setRssiHistory([]);
      }
    });

    // 3. Conexiones TCP y estado de los móviles
    socket.on('initial_tcp_connections', (uuids) => {
      const connectionState = {};
      uuids.forEach(uuid => {
        connectionState[uuid.toLowerCase()] = true;
      });
      setTcpConnections(connectionState);
    });

    socket.on('device_connection_status', (data) => {
      setTcpConnections(prev => ({ ...prev, [data.uuid.toLowerCase()]: data.connected }));
    });

    socket.on('device_status_update', (data) => {
      const uuid = data.uuid.toLowerCase();

      // 1. 🔘 Actualizamos el estado del interruptor
      setDeviceEmittingState(prev => ({
        ...prev,
        [uuid]: data.isEmitting
      }));

      // 2. 🔋 Actualizamos la información de la guía (Ajustado para guardar TODO el hardware)
      setGuias(prev => {
        const guiaExistente = prev[uuid] || {
          uuid: uuid,
          activa: true,
          distancia: '--',
          rssi: '--',
          t: new Date().toLocaleTimeString()
        };

        return {
          ...prev,
          [uuid]: {
            ...guiaExistente,
            battery: data.battery,
            temp: data.temp,       // 🌡️ ¡Importante guardar para el Modal!
            model: data.model,     // 📱 Guardamos el modelo
            storage: data.storage, // 💾 Guardamos el almacenamiento
            ip: data.ip,           // 🌐 Guardamos la IP
          }
        };
      });

      // 3. 🔥 Lógica de Temperatura (Anti-spam perfecta)
      const tempAnterior = lastTempAlertRef.current[uuid] || 0;
      if (data.temp > 40 && tempAnterior <= 40) {
        const notifTemp = {
          id: `temp-${uuid}-${Date.now()}`,
          title: "🔥 SOBREQUECEMENTO",
          msg: `Guía ${uuid.slice(-4)} a ${data.temp}°C.`,
          type: 'danger',
          time: new Date().toLocaleTimeString()
        };
        setNotifications(prev => [notifTemp, ...prev].slice(0, 20));
      }
      lastTempAlertRef.current[uuid] = data.temp;

      // 4. 🪫 Lógica de Batería (Anti-spam perfecta)
      const batAnterior = lastBatteryRef.current[uuid] || 100;
      const UMTRAL_CRITICO = 15;

      if (data.battery <= UMTRAL_CRITICO && batAnterior > UMTRAL_CRITICO) {
        const notifBat = {
          id: `bat-${uuid}-${Date.now()}`,
          title: "🪫 BATERÍA CRÍTICA",
          msg: `Dispositivo ${uuid.slice(-4)} ten só un ${data.battery}%. ¡Poñer a cargar!`,
          type: 'warn',
          time: new Date().toLocaleTimeString()
        };
        setNotifications(prev => [notifBat, ...prev].slice(0, 20));
      }
      lastBatteryRef.current[uuid] = data.battery;
    });



    // 4. Actualización de telemetría (Radar/Distancia)
    socket.on('update_audioguia', (data) => {
      // 1. 🛡️ SEGURIDAD: (Igual que el tuyo)
      if (!data || !data.uuid) return;
      const uuid = data.uuid.toLowerCase();

      // --- 🟢 PASO A: LEER LA MEMORIA ---
      const estadoPrevio = memoriaEstados.current[uuid];

      // 2. 🚀 ACTUALIZAR EL DASHBOARD (Igual que el tuyo)
      setGuias(prev => ({
        ...prev,
        [uuid]: {
          ...data,
          id: data.id,
          activa: true,
          distancia: data.distance,
          estado: data.status,
          rssi: data.rssi,
          t: new Date().toLocaleTimeString(),
          lastUpdate: Date.now()
        }
      }));

      // 3. 🔔 NOTIFICACIÓN FILTRADA
      // Solo disparamos si: el estado es 'saliendo' Y antes NO era 'saliendo'
      if (data.status === 'saliendo' && estadoPrevio !== 'saliendo') {
        const nuevaNotif = {
          id: Date.now() + Math.random(),
          title: "⚠️ INTENTO DE SAIDA",
          msg: `Dispositivo ${data.id} está fóra de zona.`,
          type: 'danger',
          time: new Date().toLocaleTimeString()
        };

        setNotifications(prev => [nuevaNotif, ...prev].slice(0, 20));
      }

      // --- 🟢 PASO B: ACTUALIZAR LA MEMORIA PARA EL PRÓXIMO SEGUNDO ---
      memoriaEstados.current[uuid] = data.status;
    });


    socket.on('login_response', (res) => {
      if (res.success) {
        setAccesoConcedido(true);
        setLoginError('');
      } else {
        setLoginError(res.message);
      }
    });

    // 🟢 EL ÚNICO RETURN (Limpieza de basura al cerrar el componente)
    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('init_db');
      socket.off('device_history');
      socket.off('initial_tcp_connections');
      socket.off('device_connection_status');
      socket.off('device_status_update');
      socket.off('update_audioguia');
    };
  }, []); // <-- Array vacío para que solo se ejecute al abrir la página


  const handleLogin = () => {
    if (!password) return setLoginError("Introduce o contrasinal");
    socket.emit('login_dashboard', password);
  };


  // 3. Función para enviar el comando desde el botón
  const handleDirectControl = (uuid, command) => {
    socket.emit('send_tcp_command', { uuid, command });
  };






  // 1. Obtenemos todas las guías que están enviando datos por el radar
  const todasLasGuias = Object.values(guias);

  // 2. 🟢 FILTRADO INTELIGENTE:
  // Una guía está "EN USO" solo si: Está activa en el radar Y su protección está ON
  const guiasActivas = todasLasGuias.filter(g =>
    g.activa && deviceEmittingState[g.uuid?.toLowerCase()] === true
  );

  // 3. 🟢 FILTRADO "EN BASE":
  // Una guía está "EN BASE" si: 
  // - Está en la DB pero NO aparece en el radar.
  // - O si aparece en el radar pero su protección está OFF.
  const guiasInactivas = dbGuias.filter(dbG => {
    const uuid = dbG.uuid.toLowerCase();
    const estaEnRadar = guias[uuid] && guias[uuid].activa;
    const estaProteccionOn = deviceEmittingState[uuid] === true;

    // Si no está en el radar O si está en el radar pero con protección OFF -> Va a la base
    return !estaEnRadar || !estaProteccionOn;
  }).map(dbG => {
    const uuid = dbG.uuid.toLowerCase();
    // Si la guía está en el radar pero apagada, recuperamos sus últimos datos para la tabla
    const datosRadar = guias[uuid] || {};

    return {
      id: dbG.id,
      uuid: dbG.uuid,
      sala: dbG.sala,
      estado: 'inactiva',
      distancia: datosRadar.distancia || '--',
      t: datosRadar.t || '--:--',
      rssi: datosRadar.rssi || '--'
    };
  });

  // 4. Los contadores se actualizan automáticamente con estas nuevas listas
  const filtrarPorEstado = (term) => guiasActivas.filter(g => g.estado === term);
  const countAlertas = filtrarPorEstado('saliendo').length;
  const countPrecaucion = filtrarPorEstado('cerca_salida').length;
  const countSeguras = filtrarPorEstado('seguro').length;
  const countInactivas = guiasInactivas.length;






  // --- PANTALLA DE BIENVENIDA ---
  // --- PANTALLA DE BIENVENIDA CON LOGIN ---
  // --- PANTALLA DE BIENVENIDA (DISEÑO PREMIUM) ---
  if (!accesoConcedido) {
    return (
      <div style={styles.welcomeScreen}>
        <GlobalStyles />
        <div style={styles.welcomeCard}>

          {/* 1. LOGO MÁS GRANDE Y CON SOMBRA SUTIL */}
          <img
            src={logo}
            alt="Logo"
            style={{
              width: '550px',
              marginBottom: '10px',
              filter: `drop-shadow(0 0 15px ${COLORS.safe}44)`
            }}
          />

          {/* TÍTULO CON PARTE EN COLOR DESTACADO */}
          <h1 style={{ fontSize: '4.5rem', fontWeight: 800, margin: '0 0 10px 0', letterSpacing: '2px' }}>
            Guide<span style={{ color: COLORS.safe }}>Guard</span>
          </h1>

          <p style={{
            color: COLORS.textMuted,
            marginBottom: '60px',
            letterSpacing: '5px',
            fontSize: '1.3rem',
            fontWeight: 600
          }}>
            SISTEMA DE SEGURIDAD
          </p>

          <div style={{ maxWidth: '400px', margin: '0 auto' }}>

            {/* 2. INPUT CON CLASE HACKER Y ESPACIADO EXTRA */}
            <input
              type="password"
              className="login-input"
              placeholder="CONTRASEÑA_SISTEMA"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
              style={{
                textAlign: 'center',
                marginBottom: '50px', // 🟢 Más espacio antes del botón
                border: loginError ? `2px solid ${COLORS.danger}` : `2px solid ${COLORS.safe}44`
              }}
            />

            {/* MENSAJE DE ERROR MÁS ELEGANTE */}
            {loginError && (
              <div className="error-msg" style={{ marginBottom: '25px' }}>
                ⚠️ ACCESO DENEGADO: {loginError}
              </div>
            )}

            {/* BOTÓN CON ESTILO ROBUSTO */}
            <button
              style={{
                ...styles.loginBtn,
                width: '100%',
                padding: '22px',
                fontSize: '1.2rem',
                letterSpacing: '2px'
              }}
              onClick={handleLogin}
            >
              ACCEDER AO PANEL
            </button>

          </div>
        </div>
      </div>
    );
  }



  // --- DASHBOARD PRINCIPAL ---
  return (

    <div style={styles.fullScreen}>
      <GlobalStyles />





      {/* SIDEBAR LATERAL */}
      <aside style={styles.sidebar}>



        {/* BRANDING */}
        <div style={styles.brandHeader}>
          <img src={logo} alt="GuideGuard Logo" style={styles.brandLogo} />
          <h2 style={styles.brandTitle}>Guide<span style={{ color: COLORS.safe }}>Guard</span></h2>
        </div>





        {/* MENÚ DE NAVEGACIÓN */}
        <div style={styles.menuContainer}>
          <div
            className="menu-item"
            style={{ ...styles.menuItem, color: activeTab === 'dashboard' ? COLORS.menuActive : COLORS.textMuted }}
            onClick={() => setActiveTab('dashboard')}
          >
            <span style={styles.menuIcon}>🏠</span>
            <span style={styles.menuText}>Dashboard</span>
          </div>





          {/* NUEVO ITEM: INVENTARIO */}
          <div
            className="menu-item"
            style={{ ...styles.menuItem, color: activeTab === 'inventario' ? COLORS.menuActive : COLORS.textMuted }}
            onClick={() => setActiveTab('inventario')}
          >
            <span style={styles.menuIcon}>📦</span>
            <span style={styles.menuText}>Inventario / DB</span>
          </div>





          <div
            className="menu-item"
            style={{
              ...styles.menuItem,
              color: activeTab === 'estadisticas' ? COLORS.menuActive : COLORS.textMuted
            }}
            onClick={() => setActiveTab('estadisticas')}
          >
            <span style={styles.menuIcon}>📊</span>
            <span style={styles.menuText}>Datos en vivo</span>
          </div>


        </div>



        {/* BOTÓN SIGN OUT LLAMATIVO */}
        <div style={styles.signOutContainer}>
          <button className="sign-out-btn" onClick={() => setAccesoConcedido(false)}>
            CERRAR SESIÓN
          </button>
        </div>





      </aside>





      {/* CONTENIDO PRINCIPAL */}
      <main style={styles.mainContent}>

        {/* ================= DASHBOARD ================= */}
        {activeTab === 'dashboard' && (
          <>


            <div style={styles.dashboardHeader}>



              <div>
                <h1 style={{ fontSize: '2.2rem', fontWeight: 800, margin: 0 }}>LPRO DAYS '26</h1>
                <p style={{ color: COLORS.textMuted, fontSize: '1.1rem', margin: '8px 0 0 0' }}>
                </p>
              </div>



              <div style={styles.topCardsGrid}>
                <StatCard title="ALERTAS CRÍTICAS" count={countAlertas} color={COLORS.danger} emoji="🚨" bg={`${COLORS.danger}15`} />
                <StatCard title="PRECAUCIÓN" count={countPrecaucion} color={COLORS.warn} emoji="⚠️" bg={`${COLORS.warn}15`} />
                <StatCard title="ZONA SEGURA" count={countSeguras} color={COLORS.safe} emoji="🛡️" bg={`${COLORS.safe}15`} />
                <StatCard title="EN BASE" count={countInactivas} color={COLORS.textMuted} emoji="📦" bg={`${COLORS.inactive}33`} />
              </div>



            </div>






            {/* EN USO */}
            <div style={{ marginTop: '10px' }}>





              <div
                className="cat-hover"
                style={{ ...styles.categoryHeader, borderLeftColor: COLORS.safe }}
                onClick={() => setShowActivas(!showActivas)}
              >



                <h2 style={styles.categoryTitle}>
                  <span style={{ color: COLORS.textMuted, fontSize: '1.4rem', marginRight: '10px' }}>
                    {showActivas ? '▼' : '▶'}
                  </span>
                  EN USO (MONITOREO ACTIVO)
                </h2>
                <span style={{ ...styles.categoryCount, background: COLORS.cyanGrad, color: '#000' }}>
                  {guiasActivas.length}
                </span>



              </div>





              {showActivas && (

                <div style={{ ...styles.zonesContainer, animation: 'slideDown 0.3s ease-out' }}>
                  <SectionTable title="ALERTA CRÍTICA" color={COLORS.danger} data={filtrarPorEstado('saliendo')} alerta={true} />
                  <SectionTable title="PRECAUCIÓN" color={COLORS.warn} data={filtrarPorEstado('cerca_salida')} />
                  <SectionTable title="ZONA SEGURA" color={COLORS.safe} data={filtrarPorEstado('seguro')} />
                </div>

              )}



            </div>





            {/* INVENTARIO EN DASHBOARD */}
            <div style={{ marginTop: '25px' }}>





              <div
                className="cat-hover"
                style={{ ...styles.categoryHeader, borderLeftColor: COLORS.inactive }}
                onClick={() => setShowInactivas(!showInactivas)}
              >



                <h2 style={styles.categoryTitle}>

                  <span style={{ color: COLORS.textMuted, fontSize: '1.4rem', marginRight: '10px' }}>
                    {showInactivas ? '▼' : '▶'}
                  </span>

                  INVENTARIO (EN BASE)

                </h2>


                <span style={{ ...styles.categoryCount, background: COLORS.inactive, color: '#fff' }}>
                  {countInactivas}
                </span>



              </div>




              {showInactivas && (
                <div style={{ ...styles.zonesContainer, animation: 'slideDown 0.3s ease-out' }}>
                  <SectionTable title="DISPOSITIVOS INACTIVOS" color={COLORS.inactive} data={guiasInactivas} inactiva={true} />
                </div>
              )}





            </div>




          </>





        )
        }










        {/* ================= ESTADÍSTICAS ================= */}
        {activeTab === 'estadisticas' && (




          <div style={{ animation: 'slideDown 0.3s ease-out' }}>



            <h1 style={{ fontSize: '2.2rem', fontWeight: 800, marginBottom: '20px' }}>
              Datos en vivo
            </h1>
            <p style={{ color: COLORS.textMuted, fontSize: '1.1rem', margin: '8px 0 0 0' }}>
              Datos en vivo sobre as audioguías
            </p>
            <p></p>


            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: '20px'
            }}>





              {dbGuias.map(g => {


                const rssi = guias[g.uuid]?.rssi ?? null;

                let statusColor = '#8F9BBA';
                let statusText = 'Sin datos';


                if (rssi !== null) {
                  if (rssi > -60) {
                    statusColor = COLORS.safe;
                    statusText = 'Óptimo';
                  } else if (rssi > -75) {
                    statusColor = COLORS.warn;
                    statusText = 'Medio';
                  } else {
                    statusColor = COLORS.danger;
                    statusText = 'Débil';
                  }
                }



                return (
                  <div
                    key={g.uuid}
                    onClick={() => {
                      setSelectedDevice(g);
                      socket.emit('get_device_history', g.uuid);
                    }}
                    style={{
                      background: 'linear-gradient(145deg, #1E2136, #151826)',
                      padding: '22px',
                      borderRadius: '18px',
                      cursor: 'pointer',
                      border: `1px solid ${statusColor}33`,
                      transition: '0.25s',
                      position: 'relative',
                      overflow: 'hidden'
                    }}
                    className="stat-hover"
                  >





                    {/* HEADER */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ margin: 0, fontSize: '1.4rem' }}>
                        {g.id}
                      </h3>

                      <span style={{
                        background: statusColor,
                        color: '#000',
                        padding: '4px 10px',
                        borderRadius: '20px',
                        fontSize: '0.75rem',
                        fontWeight: 700
                      }}>
                        {statusText}
                      </span>
                    </div>

                    <p style={{ color: '#8F9BBA', margin: '8px 0' }}>
                      📍 {g.sala}
                    </p>

                    {/* UUID */}
                    <div style={{
                      fontSize: '0.8rem',
                      color: '#00E5FF',
                      wordBreak: 'break-all',
                      marginBottom: '12px'
                    }}>
                      {g.uuid}
                    </div>






                    {/* RSSI VISUAL */}
                    <div style={{ marginTop: '10px' }}>





                      <div style={{
                        height: '8px',
                        background: '#2A2E43',
                        borderRadius: '10px',
                        overflow: 'hidden'
                      }}>



                        <div style={{
                          height: '100%',
                          width: rssi ? `${Math.min(100, Math.max(0, 100 + rssi))}%` : '0%',
                          background: statusColor,
                          transition: '0.3s'
                        }} />
                      </div>



                      <div style={{
                        marginTop: '6px',
                        fontSize: '0.85rem',
                        color: statusColor,
                        fontWeight: 600
                      }}>
                        RSSI: {rssi ?? '--'} dBm
                      </div>





                    </div>




                    {/* HOVER EFFECT */}
                    <div style={{
                      position: 'absolute',
                      inset: 0,
                      background: `radial-gradient(circle at center, ${statusColor}22, transparent 70%)`,
                      opacity: 0,
                      transition: '0.3s'
                    }} />




                  </div>




                );




              })}





            </div>




          </div>




        )}









        {/* ================= INVENTARIO ================= */}
        {activeTab === 'inventario' && (



          <div style={{ animation: 'slideDown 0.3s ease-out' }}>



            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>



              <div>

                <h1 style={{ fontSize: '2.2rem', fontWeight: 800, margin: 0 }}>INVENTARIO DE AUDIOGUIAS</h1>
                <p style={{ color: COLORS.textMuted, fontSize: '1.1rem', margin: '8px 0 0 0' }}>
                  Inventario persistente de audioguías
                </p>
              </div>


              {/* 
            <button 
              style={styles.addBtn} 
              onClick={() => {
                setEditingDevice(null);
                setNewDevice({ id: '', sala: '', uuid: '' });
                setShowModal(true);
              }}
            >
              + AÑADIR DISPOSITIVO
            </button>
            */}


              {/* BOTÓN AÑADIR EN BATCH (Siempre visible o junto al de añadir normal) */}
              <button
                style={{ ...styles.addBtn, background: COLORS.magentaGrad }}
                onClick={() => setShowBulkAddModal(true)}
              >
                📂 IMPORTACIÓN MASIVA
              </button>


            </div>


            <div style={{ display: 'flex', gap: '15px', marginBottom: '20px', alignItems: 'center' }}>



              {/* MENÚ DE ACCIÓN PARA SELECCIONADOS */}
              {selectedIds.length > 0 && (
                <div style={{ position: 'relative', animation: 'slideDown 0.2s' }}>
                  <button
                    style={styles.dropdownToggle}
                    onClick={() => setIsBatchMenuOpen(!isBatchMenuOpen)}
                  >
                    ⚙️ Accións para {selectedIds.length} unidades ▼
                  </button>

                  {isBatchMenuOpen && (
                    <div style={styles.dropdownMenu}>
                      <div style={styles.dropdownItem} onClick={() => { socket.emit('batch_tcp_command', { ids: selectedIds, cmd: 'ON' }); setIsBatchMenuOpen(false); }}>
                        ⚡ Encender protección
                      </div>
                      <div style={styles.dropdownItem} onClick={() => { socket.emit('batch_tcp_command', { ids: selectedIds, cmd: 'OFF' }); setIsBatchMenuOpen(false); }}>
                        🛑 Apagar protección
                      </div>
                      <div style={styles.dropdownItem} onClick={() => {
                        setShowBatchEditModal(true); // 🟢 Ahora sí abre el modal
                        setIsBatchMenuOpen(false);
                      }}>
                        ✏️ Editar selección (Sala)
                      </div>
                      <div style={{ ...styles.dropdownItem, color: COLORS.danger }} onClick={() => {
                        if (window.confirm(`¿Borrar ${selectedIds.length} guías?`)) {
                          socket.emit('batch_delete_devices', selectedIds);
                          setSelectedIds([]);
                        }
                        setIsBatchMenuOpen(false);
                      }}>
                        🗑️ Eliminar seleccionados
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>



            <div style={styles.zoneCard}>



              <div style={styles.tableHeader}>
                <span style={{ flex: 1 }}>ID DISPOSITIVO</span>
                <span style={{ flex: 1.5 }}>SALA ASIGNADA</span>
                <span style={{ flex: 2 }}>UUID</span>
                <span style={{ flex: 0.5, textAlign: 'right' }}>ACCIÓN</span>
              </div>



              {dbGuias.length === 0 ? (
                <div style={styles.emptyRow}>Non hai dispositivos rexistrados.</div>
              ) : (
                dbGuias.map(g => (





                  <div key={g.id} style={styles.row}>


                    <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                      {/* 🟢 Checkbox para seleccionar todo */}
                      <input
                        type="checkbox"
                        // Cambiamos el onChange para que use la función toggleSelection
                        onChange={() => toggleSelection(g.id)}
                        // Cambiamos el checked para que solo dependa de si SU id está en la lista
                        checked={selectedIds.includes(g.id)}
                        style={{ marginRight: '15px', transform: 'scale(1.2)', cursor: 'pointer' }}
                      />

                    </div>
                    <span style={{ flex: 1, fontWeight: 800 }}>{g.id}</span>
                    <span style={{ flex: 1.5, color: COLORS.textMuted }}>{g.sala}</span>
                    <code style={{ flex: 2, color: COLORS.safe }}>{g.uuid}</code>



                    <div style={{ flex: 0.5, textAlign: 'right', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>




                      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>

                        {/* Indicador de conexión TCP */}
                        <span title={tcpConnections[g.uuid] ? "Conectado al servidor TCP" : "Desconectado"}>
                          {tcpConnections[g.uuid] ? '📱🟢' : '📱🔴'}
                        </span>

                        {/* Lógica de botones idéntica al script de Python */}
                        {tcpConnections[g.uuid] ? (
                          deviceEmittingState[g.uuid] ? (
                            <button
                              onClick={() => handleDirectControl(g.uuid, 'OFF')}
                              style={{ background: COLORS.danger, color: '#fff', border: 'none', padding: '8px 12px', borderRadius: '5px', cursor: 'pointer', fontWeight: 'bold' }}>
                              🛑 APAGAR PROTECCIÓN
                            </button>
                          ) : (
                            <button
                              onClick={() => handleDirectControl(g.uuid, 'ON')}
                              style={{ background: COLORS.safe, color: '#000', border: 'none', padding: '8px 12px', borderRadius: '5px', cursor: 'pointer', fontWeight: 'bold' }}>
                              ⚡ ENCENDER PROTECCIÓN
                            </button>
                          )
                        ) : (
                          <span style={{ color: COLORS.textMuted, fontSize: '0.9rem' }}>Esperando conexión...</span>
                        )}

                      </div>



                      <button
                        style={styles.editBtn}
                        onClick={() => {
                          setEditingDevice(g);
                          setShowModal(true);
                        }}
                      >
                        ⚙️
                      </button>



                      <button
                        style={styles.deleteBtn}
                        onClick={() => handleDeleteDevice(g.id)}
                      >
                        🗑️
                      </button>



                    </div>



                  </div>



                ))



              )}



            </div>


          </div>



        )}




      </main>

      {/* ================= BARRA DE NOTIFICACIONES LATERAL ================= */}
      <aside style={{
        ...styles.notifSidebar,
        width: isNotifOpen ? '500px' : '60px',
      }}>

        {/* Botón de expansión/retracción */}
        <button
          onClick={() => setIsNotifOpen(!isNotifOpen)}
          style={{
            ...styles.notifToggle,
            left: isNotifOpen ? '10px' : '12px',
            transform: isNotifOpen ? 'rotate(0deg)' : 'rotate(180deg)',
            borderColor: notifications.length > 0 ? COLORS.danger : COLORS.safe
          }}
        >
          {isNotifOpen ? '❯' : '❮'}
        </button>

        {/* Contenido visible solo si está expandido */}
        {isNotifOpen && (
          <div style={styles.notifContent}>

            {/* Cabecera de la barra */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '30px',
              borderBottom: '1px solid rgba(255,255,255,0.05)',
              marginLeft: '50px',
              paddingBottom: '15px'
            }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0, letterSpacing: '2px' }}>
                REXISTRO DE <span style={{ color: COLORS.safe }}>INCIDENCIAS</span>
              </h2>

              {notifications.length > 0 && (
                <button
                  onClick={() => setNotifications([])}
                  style={{
                    background: 'none', border: 'none', color: COLORS.textMuted,
                    cursor: 'pointer', fontSize: '0.75rem', fontWeight: 700
                  }}
                >
                  LIMPAR TODO
                </button>
              )}
            </div>

            {/* Lista de Alertas */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {notifications.length === 0 ? (
                <div style={{ textAlign: 'center', marginTop: '60px', opacity: 0.5 }}>
                  <div style={{ fontSize: '3rem', marginBottom: '15px' }}>✨</div>
                  <p style={{ fontSize: '0.9rem', color: COLORS.textMuted }}>SISTEMA OPERATIVO SIN NOVEDADES</p>
                </div>
              ) : (
                notifications.map(n => (
                  <div
                    key={n.id}
                    className="stat-hover"
                    style={{
                      ...styles.notifCard,
                      borderLeftColor: n.type === 'danger' ? COLORS.danger : COLORS.warn,
                      backgroundColor: n.type === 'danger' ? 'rgba(255, 75, 140, 0.05)' : 'rgba(255, 184, 0, 0.05)',
                      boxShadow: n.type === 'danger' ? `0 0 15px ${COLORS.danger}15` : 'none',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <span style={{
                        color: n.type === 'danger' ? COLORS.danger : COLORS.warn,
                        fontSize: '0.8rem',
                        fontWeight: 800,
                        letterSpacing: '1px'
                      }}>
                        {n.title}
                      </span>
                      <span style={{ color: COLORS.textMuted, fontSize: '0.7rem' }}>{n.time}</span>
                    </div>

                    <p style={{
                      margin: '8px 0 0 0',
                      fontSize: '0.9rem',
                      lineHeight: '1.5',
                      color: '#E2E8F0'
                    }}>
                      {n.msg}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </aside>


      {showBulkAddModal && (
        <div style={styles.modalOverlay} onClick={() => setShowBulkAddModal(false)}>
          <div style={{ ...styles.modalCard, width: '600px' }} onClick={e => e.stopPropagation()}>
            <h2 style={{ color: COLORS.safe }}>IMPORTACIÓN MASIVA</h2>
            <p style={{ color: COLORS.textMuted }}>Pega os datos seguindo este formato por liña: <br />
              <code>ID, SALA, UUID</code></p>

            <textarea
              style={styles.bulkTextArea}
              placeholder="NOME, SALA, UUID..."
              value={bulkData}
              onChange={(e) => setBulkData(e.target.value)}
            />

            <div style={{ display: 'flex', gap: '15px', marginTop: '20px' }}>
              <button style={styles.loginBtn} onClick={() => {
                const lines = bulkData.split('\n').filter(l => l.trim());
                const devices = lines.map(l => {
                  const [id, sala, uuid] = l.split(',');
                  return { id: id?.trim(), sala: sala?.trim(), uuid: uuid?.trim() };
                });
                socket.emit('batch_add_devices', devices);
                setShowBulkAddModal(false);
                setBulkData("");
              }}>
                PROCESAR E IMPORTAR
              </button>
              <button style={styles.cancelBtn} onClick={() => setShowBulkAddModal(false)}>CANCELAR</button>
            </div>
          </div>
        </div>
      )}


      {showBatchEditModal && (
        <div style={styles.modalOverlay} onClick={() => setShowBatchEditModal(false)}>
          <div style={{ ...styles.modalCard, width: '500px' }} onClick={e => e.stopPropagation()}>
            <h2 style={{ color: COLORS.safe }}>EDITAR {selectedIds.length} DISPOSITIVOS</h2>
            <p style={{ color: COLORS.textMuted }}>Cambiaráse a sala de todas as unidades seleccionadas.</p>

            <div style={{ marginTop: '20px' }}>
              <label style={styles.infoLabel}>NOVA SALA ASIGNADA</label>
              <input
                placeholder="Ex: Gradas de Teleco"
                value={batchSala}
                onChange={(e) => setBatchSala(e.target.value)}
                autoFocus
              />
            </div>

            <div style={{ display: 'flex', gap: '15px', marginTop: '30px' }}>
              <button
                style={{ ...styles.loginBtn, flex: 1 }}
                onClick={handleBatchUpdateSala}
              >
                APLICAR CAMBIOS
              </button>
              <button
                style={{ ...styles.cancelBtn, flex: 1 }}
                onClick={() => setShowBatchEditModal(false)}
              >
                CANCELAR
              </button>
            </div>
          </div>
        </div>
      )}



      {/* --- MODAL FLOTANTE UNIFICADO --- */}

      {showModal && (

        <div
          style={styles.modalOverlay}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowModal(false);
              setEditingDevice(null);
              setNewDevice({ id: '', sala: '', uuid: '' });
            }
          }}
        >



          <div style={styles.modalCard}>



            <h2 style={{ fontSize: '2rem', marginBottom: '25px' }}>
              {editingDevice ? '🛠️ Configurar Guía' : '➕ Rexistrar Guía'}
            </h2>



            {(() => {



              const device = editingDevice || newDevice;



              return (



                <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>



                  {/* ID */}
                  <div>
                    <label>ID</label>
                    <input
                      value={device.id}
                      onChange={e => {
                        const updated = { ...device, id: e.target.value };
                        editingDevice ? setEditingDevice(updated) : setNewDevice(updated);
                      }}
                    />
                  </div>




                  {/* SALA */}
                  <div>
                    <label>Sala</label>
                    <input
                      value={device.sala}
                      onChange={e => {
                        const updated = { ...device, sala: e.target.value };
                        editingDevice ? setEditingDevice(updated) : setNewDevice(updated);
                      }}
                    />
                  </div>



                  {/* UUID */}
                  <div>
                    <label>UUID</label>
                    <input
                      disabled={!!editingDevice}
                      value={device.uuid}
                      onChange={e => {
                        if (!editingDevice) {
                          setNewDevice({ ...newDevice, uuid: e.target.value });
                        }
                      }}
                    />
                  </div>



                  <div style={{ display: 'flex', gap: '15px', marginTop: '20px' }}>



                    <button
                      style={{ ...styles.loginBtn, flex: 1 }}
                      onClick={editingDevice ? handleUpdateDevice : handleAddDevice}
                    >
                      {editingDevice ? 'GUARDAR' : 'REGISTRAR'}
                    </button>



                    <button
                      style={{ ...styles.cancelBtn, flex: 1 }}
                      onClick={() => {
                        setShowModal(false);
                        setEditingDevice(null);
                        setNewDevice({ id: '', sala: '', uuid: '' });
                      }}
                    >
                      CANCELAR
                    </button>



                  </div>



                </div>



              );



            })()}



          </div>



        </div>



      )}







      {selectedDevice && (
        <div style={styles.modalOverlay} onClick={() => { setSelectedDevice(null); setRssiHistory([]); }}>
          <div
            style={{ ...styles.modalCard, width: '750px', border: `2px solid ${COLORS.safe}88` }}
            onClick={e => e.stopPropagation()}
          >
            {/* CABECERA */}
            <div style={{ borderBottom: `1px solid ${COLORS.inactive}44`, paddingBottom: '15px', marginBottom: '20px', textAlign: 'center' }}>
              <h2 style={{ fontSize: '2.2rem', color: COLORS.safe, margin: 0, fontWeight: 800 }}>
                {selectedDevice.id}
              </h2>
              <span style={{ color: COLORS.textMuted, fontSize: '0.9rem', letterSpacing: '2px' }}>ESTADO DEL SISTEMA</span>
            </div>

            {/* CUADRÍCULA DE DATOS EN TIEMPO REAL */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>

              <div style={styles.infoBox}>
                <small style={styles.infoLabel}>SALA</small>
                <div style={styles.infoValue}>📍 {selectedDevice.sala}</div>
              </div>

              <div style={styles.infoBox}>
                <small style={styles.infoLabel}>BATERÍA</small>
                <div style={{ ...styles.infoValue, color: COLORS.danger }}>
                  🔋 {guias[selectedDevice.uuid.toLowerCase()]?.battery || '--'}%
                </div>
              </div>

              <div style={styles.infoBox}>
                <small style={styles.infoLabel}>SINAL (RSSI)</small>
                <div style={{ ...styles.infoValue, color: COLORS.safe }}>
                  📡 {guias[selectedDevice.uuid.toLowerCase()]?.rssi || '--'} dBm
                </div>
              </div>

              <div style={{ marginTop: '0px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>

                <div style={styles.hardwareBox}>
                  <small style={styles.infoLabel}>DISPOSITIVO</small>
                  <div style={styles.hardwareText}>📱 {guias[selectedDevice.uuid]?.model || 'Generico'}</div>
                </div>

                <div style={styles.hardwareBox}>
                  <small style={styles.infoLabel}>ALMACENAMIENTO</small>
                  <div style={styles.hardwareText}>💾 {guias[selectedDevice.uuid]?.storage || 0}%</div>
                  <div style={styles.miniBarBg}>
                    <div style={{ ...styles.miniBarFill, width: `${guias[selectedDevice.uuid]?.storage || 0}%` }} />
                  </div>
                </div>

                <div style={styles.hardwareBox}>
                  <small style={styles.infoLabel}>TEMPERATURA</small>
                  <div style={{ ...styles.hardwareText, color: guias[selectedDevice.uuid]?.temp > 40 ? COLORS.danger : COLORS.safe }}>
                    🌡️ {guias[selectedDevice.uuid]?.temp || '--'}°C
                  </div>
                </div>

              </div>

              <div style={styles.infoBox}>
                <small style={styles.infoLabel}>SINCRONIZACIÓN</small>
                <div style={styles.infoValue}>🕒 {guias[selectedDevice.uuid.toLowerCase()]?.t || '--:--'}</div>
              </div>

            </div>

            {/* UUID (Pie de página) */}
            <div style={{ marginTop: '20px', padding: '15px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px' }}>
              <small style={{ color: COLORS.textMuted, display: 'block', fontWeight: '800', fontSize: '1rem' }}>UUID ASIGNADO:</small>
              <code style={{ fontSize: '1rem', color: COLORS.safe }}>{selectedDevice.uuid}</code>
            </div>

            <button
              style={{ ...styles.cancelBtn, width: '100%', marginTop: '25px', padding: '15px', fontSize: '1rem' }}
              onClick={() => { setSelectedDevice(null); setRssiHistory([]); }}
            >
              CERRAR MONITOR
            </button>
          </div>
        </div>
      )}




    </div>





  );
}










// --- SUB-COMPONENTE ORIGINAL: TARJETA DE RESUMEN SUPERIOR ---
const StatCard = ({ title, count, color, emoji, bg }) => (
  <div className="stat-hover" style={{ ...styles.topStatCard, backgroundColor: bg, borderBottom: `5px solid ${color}` }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontSize: '2.2rem' }}>{emoji}</span>
      <h3 style={{ fontSize: '3.2rem', fontWeight: 800, color: color, margin: 0 }}>{count}</h3>
    </div>
    <p style={{ color: color, fontSize: '1.1rem', fontWeight: 800, margin: '10px 0 0 0', letterSpacing: '1px' }}>{title}</p>
  </div>
);





// Helper original para estados
const getStatusInfo = (estado, inactiva) => {
  if (inactiva) return { text: 'INACTIVA', emoji: '📦', color: COLORS.textMuted };
  if (estado === 'saliendo') return { text: 'ALERTA', emoji: '🚨', color: COLORS.danger };
  if (estado === 'cerca_salida') return { text: 'PRECAUCIÓN', emoji: '⚠️', color: COLORS.warn };
  return { text: 'SEGURA', emoji: '🛡️', color: COLORS.safe };
};





// --- COMPONENTE ORIGINAL DE TABLA DE ZONAS (Filas) ---
const SectionTable = ({ title, color, data, alerta = false, inactiva = false }) => (



  <div style={{ ...styles.zoneCard, borderColor: inactiva ? 'transparent' : `${color}44` }}>
    <h3 style={{ color: color, margin: '0 0 20px 0', fontSize: '1.5rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '12px' }}>
      <div style={{ width: '15px', height: '15px', borderRadius: '50%', backgroundColor: color }}></div>
      {title}
    </h3>


    <div style={styles.tableHeader}>
      <span style={{ flex: 1.5 }}>ID DISPOSITIVO</span>
      <span style={{ flex: 1.5 }}>ESTADO</span>
      <span style={{ flex: 1.5 }}>DISTANCIA</span>
      <span style={{ flex: 1 }}>SINAL</span>
      <span style={{ flex: 1, textAlign: 'right' }}>HORA</span>
    </div>


    <div style={styles.tableBody}>

      {data.length === 0 ? (

        <div style={styles.emptyRow}>{inactiva ? "TODOS OS DISPOSITIVOS ESTÁN EN USO" : "ZONA DESPEXADA"}</div>

      ) : (


        data.map(g => {

          const status = getStatusInfo(g.estado, inactiva);


          return (
            <div key={g.id} style={{
              ...styles.row,
              borderLeft: `5px solid ${color}`,
              animation: alerta ? 'pulseAlert 1.5s infinite' : 'none',
              opacity: inactiva ? 0.5 : 1
            }}>


              <span style={{ flex: 1.5, fontSize: '1.5rem', fontWeight: 800 }}>{g.id}</span>

              <span style={{ flex: 1.5, fontSize: '1.1rem', fontWeight: 800, color: status.color, display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '1.5rem' }}>{status.emoji}</span> {status.text}
              </span>

              <span style={{ flex: 1.5, fontSize: '2rem', fontWeight: 800, color: '#fff' }}>
                {inactiva ? '--' : g.distancia}<small style={{ fontSize: '1.1rem', color: COLORS.textMuted, marginLeft: '5px' }}>{inactiva ? '' : 'm'}</small>
              </span>

              <span style={{ flex: 1, fontSize: '1.2rem', color: COLORS.textMuted }}>{inactiva ? '--' : `${g.rssi} dBm`}</span>
              <span style={{ flex: 1, textAlign: 'right', fontSize: '1.1rem', color: COLORS.textMuted }}>{inactiva ? '--:--' : g.t}</span>

            </div>




          );




        })




      )}




    </div>




  </div>




);











// --- 5. ESTILOS EN LÍNEA (Tus estilos originales + los del Modal) ---
const styles = {

  /* --- BARRA LATERAL DERECHA (NOTIFICACIONES) --- */
  notifSidebar: {
    backgroundColor: COLORS.sidebar,
    height: '100vh',
    borderLeft: '1px solid rgba(255,255,255,0.05)',
    transition: 'width 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
    position: 'relative',
    overflowX: 'hidden',
    overflowY: 'auto',
    zIndex: 5,
    display: 'flex',
    flexDirection: 'column'
  },
  notifToggle: {
    position: 'absolute',
    top: '20px',
    left: '10px',
    background: '#2A2E43',
    border: `1px solid ${COLORS.safe}44`,
    color: '#fff',
    width: '35px',
    height: '35px',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '1rem',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    boxShadow: '0 4px 10px rgba(0,0,0,0.3)',
    zIndex: 10,
    transition: '0.3s'
  },
  notifContent: {
    padding: '25px',
    minWidth: '300px', // Evita que el texto se amontone al cerrar
    animation: 'slideDown 0.4s ease-out'
  },
  notifCard: {
    background: 'rgba(255,255,255,0.03)',
    padding: '15px',
    borderRadius: '12px',
    borderLeft: '4px solid',
    marginBottom: '12px',
    transition: 'transform 0.2s',
    cursor: 'default'
  },

  batchBar: {
    background: '#1E2136',
    padding: '20px',
    borderRadius: '15px',
    marginBottom: '20px',
    display: 'flex',
    alignItems: 'center',
    border: '1px dashed #4A5568',
    boxShadow: 'inset 0 0 10px rgba(0,0,0,0.2)'
  },
  batchBtnOn: {
    background: COLORS.safe, color: '#000', border: 'none', padding: '10px 20px',
    borderRadius: '8px', fontWeight: '800', cursor: 'pointer', transition: '0.2s'
  },
  batchBtnOff: {
    background: COLORS.danger, color: '#fff', border: 'none', padding: '10px 20px',
    borderRadius: '8px', fontWeight: '800', cursor: 'pointer', transition: '0.2s'
  },
  deleteBtnBulk: {
    background: 'rgba(255, 75, 140, 0.1)', color: COLORS.danger, border: `1px solid ${COLORS.danger}`,
    padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold'
  },

  dropdownToggle: {
    background: '#2A2E43',
    color: '#fff',
    border: `1px solid ${COLORS.safe}44`,
    padding: '12px 20px',
    borderRadius: '10px',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '0.9rem'
  },
  dropdownMenu: {
    position: 'absolute',
    top: '110%',
    left: '0',
    background: '#1E2136',
    border: '1px solid #4A5568',
    borderRadius: '12px',
    width: '240px',
    zIndex: 1000,
    boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
    overflow: 'hidden'
  },
  dropdownItem: {
    padding: '12px 20px',
    cursor: 'pointer',
    fontSize: '0.9rem',
    transition: '0.2s',
    borderBottom: '1px solid rgba(255,255,255,0.05)',
    '&:hover': { background: '#2A2E43' } // Nota: En inline style usa onMouseEnter
  },
  bulkTextArea: {
    width: '100%',
    height: '200px',
    background: '#0d0f1a',
    border: `1px solid ${COLORS.inactive}`,
    borderRadius: '10px',
    color: COLORS.safe,
    padding: '15px',
    fontFamily: 'monospace',
    marginTop: '10px'
  },

  hardwareText: { fontSize: '1rem', fontWeight: '700', color: '#fff', marginTop: '5px' },
  hardwareBox: { background: '#16192B', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', justifyContent: 'center' },

  infoBox: { background: '#16192B', padding: '15px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', justifyContent: 'center' },
  infoLabel: { color: '#8F9BBA', fontSize: '1rem', fontWeight: '800', marginBottom: '5px', display: 'block' },
  infoValue: { fontSize: '1.1rem', fontWeight: '700', color: '#fff' },

  fullScreen: { display: 'flex', height: '100vh', width: '100vw' },

  sidebar: { width: '320px', backgroundColor: COLORS.sidebar, display: 'flex', flexDirection: 'column', padding: '40px 25px', boxShadow: '4px 0 20px rgba(0,0,0,0.2)', zIndex: 10 },

  brandHeader: { display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '0 10px', marginBottom: '50px' },
  brandLogo: { width: '200px', objectFit: 'contain', filter: `drop-shadow(0 0 15px ${COLORS.safe}99)`, marginBottom: '25px' },
  brandTitle: { fontSize: '2.5rem', fontWeight: 800, margin: 0, letterSpacing: '2px', color: '#fff', textAlign: 'center' },

  menuContainer: { display: 'flex', flexDirection: 'column', gap: '8px', padding: '0 10px' },
  menuItem: { display: 'flex', alignItems: 'center', padding: '18px 25px', borderRadius: '12px', color: COLORS.textMuted, cursor: 'pointer', transition: '0.2s' },
  menuIcon: { fontSize: '1.5rem', marginRight: '20px', opacity: 0.8 },
  menuText: { fontSize: '1.2rem', fontWeight: 600, flex: 1 },

  signOutContainer: { marginTop: 'auto', padding: '0 10px' },

  mainContent: { flex: 1, padding: '40px 50px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '20px' },

  dashboardHeader: { marginBottom: '25px' },
  topCardsGrid: { display: 'flex', gap: '25px', marginTop: '25px' },
  topStatCard: { flex: 1, padding: '25px', borderRadius: '18px', transition: 'transform 0.2s', cursor: 'default' },

  categoryHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 30px', backgroundColor: COLORS.card, borderLeft: '8px solid', borderRadius: '15px', cursor: 'pointer', userSelect: 'none', transition: 'all 0.2s', boxShadow: '0 4px 10px rgba(0,0,0,0.1)' },
  categoryTitle: { fontSize: '1.4rem', fontWeight: 800, letterSpacing: '1px', margin: 0, display: 'flex', alignItems: 'center' },
  categoryCount: { fontSize: '1.2rem', fontWeight: 800, padding: '6px 18px', borderRadius: '25px' },

  zonesContainer: { display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '20px' },
  zoneCard: { backgroundColor: COLORS.card, borderRadius: '18px', border: '1px solid', padding: '30px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' },
  tableHeader: { display: 'flex', padding: '0 25px', fontSize: '1.1rem', color: COLORS.textMuted, fontWeight: 600, borderBottom: `2px solid ${COLORS.inactive}`, marginBottom: '18px', paddingBottom: '12px' },
  tableBody: { display: 'flex', flexDirection: 'column', gap: '10px' },
  row: { display: 'flex', padding: '20px 25px', background: '#22253A', borderRadius: '12px', alignItems: 'center' },
  emptyRow: { padding: '30px', textAlign: 'center', color: COLORS.textMuted, fontSize: '1.2rem', fontWeight: 600 },

  welcomeScreen: { height: '100vh', width: '100vw', display: 'flex', justifyContent: 'center', alignItems: 'center' },
  welcomeCard: { background: COLORS.sidebar, padding: '80px', borderRadius: '35px', textAlign: 'center', boxShadow: '0 20px 50px rgba(0,0,0,0.5)', width: '650px' },
  loginBtn: { background: COLORS.magentaGrad, border: 'none', padding: '25px 70px', borderRadius: '50px', color: '#fff', fontSize: '1.5rem', fontWeight: 800, cursor: 'pointer', boxShadow: '0 8px 25px rgba(224, 82, 255, 0.4)', transition: '0.3s' },

  // --- NUEVOS ESTILOS PARA LA GESTIÓN (Añadidos sin borrar nada) ---
  addBtn: { background: COLORS.cyanGrad, border: 'none', padding: '15px 30px', borderRadius: '12px', color: '#000', fontSize: '1.1rem', fontWeight: 800, cursor: 'pointer', boxShadow: '0 4px 15px rgba(0, 242, 254, 0.3)' },
  deleteBtn: { background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', transition: '0.2s' },
  cancelBtn: { background: COLORS.inactive, border: 'none', borderRadius: '50px', color: '#fff', fontSize: '1.1rem', fontWeight: 800, cursor: 'pointer' },
  modalOverlay: { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.85)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 },
  modalCard: { background: COLORS.sidebar, padding: '40px', borderRadius: '25px', width: '800px', border: `1px solid ${COLORS.inactive}`, boxShadow: '0 20px 50px rgba(0,0,0,0.5)' },

  // 🟢 3. ESTILOS NUEVOS

  editBtn: {
    background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', transition: '0.2s'
  }


};


export default App;