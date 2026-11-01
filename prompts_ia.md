# Registro de Uso de Herramientas de Inteligencia Artificial - FitLife Gym

## Proyecto Asignado
* **Caso:** Proyecto 2 - Plataforma de Control de Asistencia y Reserva de Clases para Gimnasios (FitLife).
* **Framework:** Django 5+ / Django REST Framework (DRF) sobre PostgreSQL en AWS EC2.
* **Paradigma:** 4+1 Vistas de Arquitectura de Software.

## Registro de Prompts y Apoyos Técnicos

### 1. Configuración de Base de Datos y Modelado Relacional (Fases 1 y 2)
* **Objetivo:** Modelar en PostgreSQL las entidades de Membresías (Activa, Vencida, Congelada), Clases grupales, Lista de espera y Control de aforo QR.
* **Consulta enviada a la IA:** "Estructura los modelos de Django ORM para el gimnasio FitLife cumpliendo 3NF, con relación 1:N entre usuarios y membresías, estados explícitos CHOICES, y colas de espera para clases grupales."
* **Resultado obtenido:** Modelos relacionales normalizados con generación automática de tokens QR `FIT-XXXXXXXXXX` y validación de vigencias por fecha.

### 2. Django Admin Personalizado (Fase 3)
* **Objetivo:** Personalizar listados con format_html para estados de membresías, filtros por fecha y cupos visuales.
* **Consulta enviada a la IA:** "Genera la configuración de `admin.py` con badges visuales de color (verde para Activa, rojo para Vencida y amarillo para Congelada) y acciones masivas."
* **Resultado obtenido:** Panel administrativo con filtros laterales, barras de ocupación y acciones rápidas de congelamiento.

### 3. Lógica Transaccional y Control de Sobrecupo (Fase 4)
* **Objetivo:** Manejar reservas atómicas de clases con promoción inmediata desde lista de espera al cancelar cupo.
* **Consulta enviada a la IA:** "Implementa en DRF un endpoint de reserva de clases que verifique cupos disponibles de forma atómica (@transaction.atomic) y derive a lista de espera si se agotan."
* **Resultado obtenido:** ViewSet con acciones `@action` transaccionales para reservas y cancelaciones sincronizadas.

### 4. Lector QR de Baja Latencia y Dashboard en Vivo (Fase 5)
* **Objetivo:** Validar código QR en milisegundos y graficar aforo en tiempo real.
* **Consulta enviada a la IA:** "Crea un script frontend con fetch asíncrono y Bootstrap 5 para simular un lector de torniquete QR y un dashboard con actualización automática de aforo."
* **Resultado obtenido:** Vistas HTML responsivas con consumo de APIs REST y refresco continuo de indicadores.
