# FitLife Gym Platform - Arquitectura de Software 4+1

Plataforma SaaS de gestión de recintos deportivos, automatización de torniquetes de control de acceso y reserva de clases grupales con arquitectura desacoplada en AWS EC2, Gunicorn, Nginx y PostgreSQL.

Producción: https://fitlife-gym.duckdns.org/
Cifrado: Certificado SSL/TLS Let's Encrypt (HTTPS nativo)
Dirección IP Elástica: 184.193.244.91

---

## 1. FICHA TÉCNICA DE LA EVALUACIÓN

* Institución / Asignatura: Desarrollo Backend - Evaluación 3
* Desarrollador / Alumno: Felipe Eduardo Rivas Garrido
* Sección: AP-N4-C2
* Año Académico: 2026
* Docente Evaluador: Marcelo Alvarado Aravena
* Repositorio GitHub: https://github.com/Pipegamer/fitlife-gym.git

---

## 2. ARQUITECTURA DEL SISTEMA

El despliegue en producción opera sobre una arquitectura en capas protegida y demonizada para alta disponibilidad:

[ Cliente Web / Móvil ]
          │ (HTTPS - Puerto 443 / HTTP - Puerto 80)
          ▼
[ Nginx (Proxy Inverso & Servidor de Estáticos) ]
    ├── Despacho autónomo de /static/ (Tailwind / JS / Imágenes)
    ├── Terminación de cifrado SSL/TLS (Certbot Let's Encrypt)
    └── Preservación de IP real del cliente (X-Real-IP)
          │ (Socket local / HTTP Interno 127.0.0.1:8000)
          ▼
[ Gunicorn (Servidor WSGI con 3 Workers en Systemd) ]
          │ (Procesamiento Python / Django)
          ▼
[ Django 5.x Backend & Lógica de Negocio ]
    ├── Middleware de Auditoría SLA (< 30 ms promedio)
    └── Control de Acceso Basado en Roles (RBAC)
          │ (Puerto 5432 - Conexión nativa)
          ▼
[ PostgreSQL (Base de Datos Relacional ACID & MVCC) ]

---

## 3. CREDENCIALES DEMO PARA EVALUACIÓN EN VIVO

Para validar los casos de uso y la separación estricta de privilegios, se encuentran precargados los siguientes perfiles:

1. Administrador General:
   - Usuario: admin
   - Clave: admin1234
   - Escenario: KPIs de recaudación bruta en CLP, cobro en caja presencial, CRUD de salas/disciplinas/planes y exportaciones CSV.

2. Coordinador Deportivo:
   - Usuario: coord_laura
   - Clave: coord1234
   - Escenario: Lector de torniquete con audio (880 Hz / 220 Hz), pases de cortesía, validación AM/PM y agenda semanal.

3. Instructor / Coach:
   - Usuario: coach_carlos
   - Clave: coach1234
   - Escenario: Portal docente /instructor/, toma de asistencia presencial en sala y edición de la rutina de entrenamiento (WOD).

4. Socio Full (24/7):
   - Usuario: socio_activo
   - Clave: socio1234
   - Escenario: Credencial QR digital, freeze policy (pausa de membresía) y seguimiento de turno en lista de espera FIFO.

5. Socio Vencido:
   - Usuario: socio_vencido
   - Clave: socio1234
   - Escenario: Validación de rechazo inmediato en torniquete por membresía caducada.

6. Socio Plan Mañana AM:
   - Usuario: socio_manana
   - Clave: socio1234
   - Escenario: Denegación horaria en jornada PM (válido solo de 06:00 a 12:00 hrs).

7. Socio Tarde PM:
   - Usuario: socio_tarde
   - Clave: socio1234
   - Escenario: Denegación horaria en jornada AM (válido de 12:01 a 23:00 hrs).

8. Socio Nuevo en Espera:
   - Usuario: socio_nuevo
   - Clave: socio1234
   - Escenario: Cliente inactivo sin membresía para demostrar la venta presencial en mesón.

---

## 4. REGLAS DE NEGOCIO IMPLEMENTADAS

1. Control de Acceso Basado en Roles (RBAC):
   - Administrador: Dirección comercial, altas de personal, configuración de infraestructura y finanzas.
   - Coordinador: Operación del torniquete en recepción y agenda diaria de profesores/salas.
   - Instructor: Visualización de sus alumnos inscritos y acreditación manual de asistencia.
   - Socio: Consulta de aforo en vivo, reservas, cancelaciones y credencial QR.

2. Torniquete Inteligente & Check-in Automático:
   - Doble método de entrada: Escaneo de token QR criptográfico o ingreso manual de RUT normalizado.
   - Verificación en tiempo real de la franja horaria asociada al plan contratado (AM/PM).
   - Si el socio cuenta con una reserva para una clase que comienza dentro de los próximos 45 a 60 minutos, el torniquete confirma automáticamente su asistencia (ASISTIO) al pasar por la entrada.

3. Lista de Espera Automatizada (Cola FIFO):
   - Cuando una sesión agota sus cupos, el socio entra a la lista de espera con orden de prelación estricto.
   - Si un socio titular cancela con al menos 2 horas de anticipación, el primer turno de la fila pasa a estado CONFIRMADA sin intervención manual.

4. Regla de Cancelación a 2 Horas y Política No-Show:
   - Se bloquean las cancelaciones con menos de 120 minutos de anticipación para evitar cupos vacíos.
   - La acumulación de 3 inasistencias injustificadas (NO_SHOW) suspende la cuenta del socio por 7 días.

5. Política de Congelamiento (Freeze Policy):
   - Los socios pueden suspender temporalmente su plan. Al reanudarlo, el sistema calcula la cantidad exacta de días pausados y pospone la fecha de vencimiento (fecha_fin) en esa misma proporción.

6. Trazabilidad Financiera sin Regalías:
   - Los socios creados por el administrador quedan en estado inactivo por defecto.
   - Para activar un plan, se debe registrar el cobro en caja asociando un método formal: Tarjeta (POS), Efectivo o Transferencia Bancaria.

---

## 5. STACK TECNOLÓGICO

* Lenguaje: Python 3.10+
* Framework Backend: Django 5.x & Django REST Framework (DRF)
* Base de Datos: PostgreSQL 14+ (Conexión nativa en puerto 5432)
* Servidor de Aplicaciones: Gunicorn 21.x (WSGI con 3 workers pre-fork)
* Servidor Web & Proxy Inverso: Nginx
* Seguridad SSL: Certbot / Let's Encrypt (Protocolo ACME HTTP-01)
* Cloud: AWS EC2 (t2.micro, Ubuntu Server 22.04 LTS) en región us-east-1
* Frontend: Django Templates, Tailwind CSS (CDN), Bootstrap Icons, Chart.js

---

## 6. CONFIGURACIÓN DEL SERVICIO SYSTEMD

Archivo: /etc/systemd/system/fitlife.service

[Unit]
Description=Gunicorn daemon for FitLife Gym Platform
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/apps
ExecStart=/home/ubuntu/apps/env/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 config.wsgi:application

[Install]
WantedBy=multi-user.target

---

## 7. CONFIGURACIÓN DEL PROXY INVERSO EN NGINX

Archivo: /etc/nginx/sites-available/fitlife

server {
    server_name fitlife-gym.duckdns.org 184.193.244.91;

    location /static/ {
        alias /home/ubuntu/apps/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl;
}

---

## 8. COMANDOS DE ADMINISTRACIÓN EN PRODUCCIÓN

Reinicio de la aplicación Django / Gunicorn:
$ sudo systemctl restart fitlife

Recarga de la configuración de Nginx:
$ sudo systemctl reload nginx

Inspección de registros en vivo (Logs):
$ journalctl -u fitlife -n 50 --no-pager

Verificación de integridad de Django:
$ python manage.py check

---

## 9. MEDICIÓN DE LATENCIA Y CUMPLIMIENTO SLA (< 100 ms)

La plataforma incluye un middleware de auditoría (AuditSLAMiddleware) que intercepta el ciclo de vida de cada solicitud HTTP, registrando la latencia en milisegundos y la IP pública en access_log.log:

Ejemplo de registro:
[2026-11-01 20:15:22] GET /clases/ - IP: 190.160.x.x - Latencia: 18.42 ms [SLA OK]
[2026-11-01 20:16:04] POST /api/acceso-qr/validar/ - IP: 184.193.244.91 - Latencia: 14.12 ms [SLA OK]

---

## 10. LICENCIA

Proyecto desarrollado con fines académicos para la asignatura de Desarrollo Backend (Evaluación 3). Todos los derechos reservados © 2026.
