# Registro de Uso de Herramientas de Inteligencia Artificial – FitLife Gym

* **Proyecto:** FitLife Gym Platform – API RESTful y Arquitectura Segura en AWS
* **Estudiante:** Felipe Eduardo Rivas Garrido | **Sección:** AP-N4-C2 | **Año:** 2026
* **Repositorio:** https://github.com/Pipegamer/fitlife-gym (rama `main`)

---

## 1. Resumen de la Etapa Previa (Evaluación 3 – Núcleo Backend)

Durante la etapa inicial del proyecto (Evaluación 3), la Inteligencia Artificial se empleó como apoyo en el diseño y construcción de la lógica de dominio en Django y Django REST Framework:

1. **Modelado Relacional (3NF):** Estructuración de entidades en PostgreSQL (`Usuario`, `Sala`, `Disciplina`, `Plan`, `Membresia`, `Pago`, `ClaseGrupal`, `ReservaClase`, `ListaEspera`, `RegistroAccesoQR`), generación de códigos QR `FIT-XXXXXXXXXX` y estados explícitos.
2. **Panel Administrativo:** Personalización de `admin.py` con indicadores visuales de estado, filtros y acciones masivas.
3. **Control Transaccional y Waitlist FIFO:** Implementación de reservas y cancelaciones atómicas (`@transaction.atomic`) con promoción automática desde lista de espera y regla de cancelación a 2 horas.
4. **Operativa de Torniquete QR y Aforo:** Construcción de endpoints de validación en baja latencia y visualización en tiempo real del aforo del gimnasio.

---

## 2. Evaluación N.º 4 (2026) – Arquitectura AWS, Seguridad y Pruebas SAST/DAST

En la Evaluación N.º 4, el foco se trasladó desde el desarrollo funcional hacia la **arquitectura distribuida en AWS**, el **endurecimiento de seguridad (hardening)**, la **observabilidad**, la **continuidad operativa** y la **validación mediante pruebas SAST y DAST**. Toda sugerencia generada por IA fue evaluada críticamente, probada en entorno real y contrastada con documentación oficial antes de ser aceptada o descartada.

### 2.1 Bitácora de Uso de IA en la Evaluación 4

#### 1. Desacople de Arquitectura Distribuida en AWS y Amazon API Gateway
* **Objetivo:** Separar la capa de presentación (`fitlife-frontend`, EIP `100.50.54.169`) del servidor de aplicación (`fitlife-backend`, EIP `100.56.204.105`) exponiendo la API sobre HTTPS con Amazon API Gateway (`https://r2c64ufqj2.execute-api.us-east-1.amazonaws.com`) y protección contra abusos mediante Throttling en la etapa `$default`.
* **Prompt / Consulta a la IA:** *"Diseña un frontend desacoplado ligero (`index.html` + `config.js`) que consuma una API Django REST Framework vía API Gateway con autenticación JWT Bearer, manejo de respuestas HTTP 429 por Rate Limiting y carga de hoja de estilos corporativa desde Amazon S3."*
* **Resultado y validación:** Se implementaron `frontend/index.html` y `frontend/config.js` servidos por Nginx en `fitlife-frontend`. Se verificó CORS controlado por entorno (`CORS_ALLOWED_ORIGINS`), flujo JWT completo y respuestas `HTTP 429` ante ráfagas controladas en API Gateway.

#### 2. Hardening Backend: JWT, Argon2id, RDS PostgreSQL y Amazon S3
* **Objetivo:** Migrar secretos fuera del repositorio (`.env` excluido en `.gitignore`), endurecer el hashing de contraseñas a Argon2id, aislar la base de datos en Amazon RDS PostgreSQL con TLS y configurar almacenamiento estático seguro en Amazon S3 (`fitlife-cloud-storage-2026`).
* **Prompt / Consulta a la IA:** *"Configura `settings.py` en Django/DRF para operar con variables de entorno `.env`, SimpleJWT con claims de rol, `Argon2PasswordHasher` como hasher principal, PostgreSQL en Amazon RDS con soporte `sslmode` y `django-storages` hacia Amazon S3 con cifrado SSE-S3 (`AES256`) y URLs prefirmadas para media."*
* **Resultado y validación:** Se actualizó `config/settings.py` y `api/serializers.py` (`CustomTokenObtainPairSerializer`). Se verificó en RDS la generación de hashes `argon2$argon2id$v=19`, el aislamiento de red SG-a-SG (`sg-09b72e57a23648396` permitiendo puerto `5432` solo desde `sg-07b5a41bc44512f8e`) y la entrega `HTTP 200` de `static/css/fitlife-brand.css` desde S3 con política `PublicReadGetObject` (`s3:GetObject`).

#### 3. Remediación de Hallazgos SAST (SonarQube Cloud)
* **Objetivo:** Resolver las vulnerabilidades y *security hotspots* detectados por SonarQube Cloud sobre `Pipegamer/fitlife-gym` para aprobar el Quality Gate en la rama `main`.
* **Prompt / Consulta a la IA:** *"Revisa los reportes de SonarQube sobre credenciales hardcodeadas en `seed_fitlife.py`, restricciones de verbos HTTP en `api/views.py` y ausencia de Subresource Integrity (SRI) en `frontend/index.html`, proponiendo correcciones mínimas y seguras."*
* **Resultado y validación:** Se migraron las contraseñas de `seed_fitlife.py` a variables de entorno (`SEED_*_PASSWORD` documentadas en `.env.example`), se restringieron los endpoints de vistas/CSV con `@require_GET` / `@require_http_methods` y se añadió `integrity="sha384-..."` + `crossorigin="anonymous"` en `bootstrap-icons@1.11.3`. Quality Gate resultante: **`Passed`** en `main` (`0` nuevos issues).

#### 4. Análisis e Interpretación de Pruebas DAST (OWASP ZAP 2.17.0)
* **Objetivo:** Interpretar el reporte `2026-11-26-ZAP-Report-.html` ejecutado contra el frontend (`100.50.54.169`) y API Gateway, diferenciando riesgos reales, falsos positivos por *backporting* y mitigaciones de cabeceras HTTP.
* **Prompt / Consulta a la IA:** *"Analiza el reporte de OWASP ZAP 2.17.0 (1 alerta Alta por banner `nginx/1.24.0` CWE-1395, 3 Medias por CSP, SRI CWE-345 y Anti-Clickjacking, 7 Bajas y 3 Informativas). Determina la validez técnica del hallazgo en Ubuntu Server y las medidas de mitigación recomendadas."*
* **Resultado y validación:** Se comprobó ausencia total de SQLi y XSS. Para la alerta Alta (`nginx/1.24.0`), se documentó la política de parches *backport* de Ubuntu y se definió la mitigación `server_tokens off;` en Nginx para eliminar la exposición de versión. Para las alertas Medias se documentaron las acciones de CSP, SRI selectivo y cabeceras Anti-Clickjacking.

#### 5. Monitoreo en CloudWatch y Propuesta de Respaldos cada 7 Horas
* **Objetivo:** Configurar observabilidad básica de EC2 (`CPUUtilization` + alarma en CloudWatch) y diseñar una solución para el requisito de respaldos de RDS cada 7 horas, no soportado nativamente por las copias diarias de Amazon RDS.
* **Prompt / Consulta a la IA:** *"Amazon RDS solo permite respaldos automáticos diarios. Diseña una arquitectura serverless en AWS para ejecutar snapshots de RDS PostgreSQL cada 7 horas con principio de mínimo privilegio y notificación operativa."*
* **Resultado y validación:** Se diseñó la arquitectura basada en **Amazon EventBridge Scheduler** (`rate(7 hours)`) -> **AWS Lambda** (`create_db_snapshot` + rotación por retención) -> **Amazon SNS**, complementando los backups automáticos y el snapshot manual verificados en RDS.

---

### 2.2 Tabla de Contraste: Recomendaciones de Seguridad de IA vs. Documentación Oficial

La siguiente tabla documenta las recomendaciones de seguridad propuestas por la IA durante la Evaluación 4, su verificación frente a documentación oficial y la decisión técnica adoptada en FitLife:

| # | Recomendación Generada por IA | Documentación Oficial Contrastada | Decisión | Justificación Técnica e Implementación en FitLife |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **Configurar `Argon2id` (`Argon2PasswordHasher`) como primer algoritmo en `PASSWORD_HASHERS` de Django**, manteniendo PBKDF2 como respaldo para migración transparente. | **Django Official Documentation – Password management in Django** (*Using Argon2 with Django*) y **OWASP Password Storage Cheat Sheet**. | **Aplicada** | La documentación oficial de Django señala explícitamente que Argon2 es el ganador de la *Password Hashing Competition* y recomienda ubicar `Argon2PasswordHasher` al inicio de `PASSWORD_HASHERS` (instalando `argon2-cffi`). En FitLife se instaló `argon2-cffi==25.1.0`, se configuró en `config/settings.py` y se validó que los hashes almacenados en Amazon RDS siguen el formato `argon2$argon2id$v=19`, ofreciendo resistencia superior a ataques de fuerza bruta con GPU/ASIC. |
| **2** | **Agregar atributo Subresource Integrity (`integrity` SHA-384 + `crossorigin="anonymous"`) a todos los recursos externos del frontend (`frontend/index.html`)**, incluyendo `bootstrap-icons` y `cdn.tailwindcss.com`. | **MDN Web Docs – Subresource Integrity (SRI)** y **OWASP Third-Party JavaScript / Secure Headers Guidance** (junto a documentación de Tailwind Play CDN). | **Aplicada en `bootstrap-icons` / Descartada justificadamente en `cdn.tailwindcss.com`** | Según MDN Web Docs, SRI solo es confiable sobre recursos **estáticos e inmutables** (versionados), ya que cualquier cambio de bytes invalida el hash y el navegador bloquea el recurso. Por ello se **aplicó** SRI SHA-384 en `bootstrap-icons@1.11.3` (`frontend/index.html`, logrando aprobar SonarQube SAST), pero se **descartó justificadamente** en `https://cdn.tailwindcss.com`, dado que Play CDN sirve un script sin versión fija que cambia dinámicamente y rompería el renderizado de la interfaz. Como evolución productiva se documentó compilar Tailwind en *build* y servir el CSS estático versionado desde Amazon S3. |
| **3** | **Restringir el Security Group de Amazon RDS PostgreSQL para aceptar puerto `5432` únicamente desde el Security Group de EC2 Backend** y externalizar todas las credenciales en `.env` excluido en `.gitignore`. | **AWS Amazon RDS Security Best Practices** (*VPC Security Groups & Encryption*) y **OWASP Secrets Management Cheat Sheet**. | **Aplicada** | Las mejores prácticas oficiales de AWS RDS recomiendan evitar reglas abiertas (`0.0.0.0/0`) y autorizar el tráfico por referencia directa entre Security Groups, además de habilitar cifrado en reposo y TLS en tránsito. En FitLife se configuró el SG de RDS (`sg-09b72e57a23648396`) permitiendo TCP `5432` exclusivamente desde el SG de `fitlife-backend` (`sg-07b5a41bc44512f8e`), se activó cifrado en reposo + soporte `DB_SSLMODE`, y se removieron secretos del código fuente (`.env` en `.gitignore` y `seed_fitlife.py` parametrizado con `os.environ.get`). |

---

### 2.3 Conclusión sobre Criterio Ingenieril y Uso de IA

El uso de herramientas de Inteligencia Artificial aceleró la implementación de controles de seguridad, el diagnóstico de hallazgos SAST/DAST y el diseño de arquitectura en AWS, pero **no sustituyó la verificación técnica**. Contrastar cada sugerencia con documentación oficial (Django, MDN, OWASP y AWS) permitió adoptar controles de alto impacto (Argon2id, SG-a-SG en RDS, SRI en `bootstrap-icons@1.11.3`) y descartar oportunamente recomendaciones que habrían degradado la disponibilidad del sistema (como aplicar un hash SRI estático sobre el script dinámico de Tailwind Play CDN).
