import os
import django
import random
from datetime import timedelta, time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from django.utils import timezone
from api.models import (
    Usuario, Sala, Disciplina, Plan, Membresia, Pago,
    ClaseGrupal, ReservaClase, ListaEspera, RegistroAccesoQR
)

@transaction.atomic
def sembrar_datos():
    print("Iniciando purga y sembrado de datos operativos para FitLife...")

    # 1. Limpieza de tablas operativas
    RegistroAccesoQR.objects.all().delete()
    ListaEspera.objects.all().delete()
    ReservaClase.objects.all().delete()
    ClaseGrupal.objects.all().delete()
    Pago.objects.all().delete()
    Membresia.objects.all().delete()
    Plan.objects.all().delete()
    Disciplina.objects.all().delete()
    Sala.objects.all().delete()
    Usuario.objects.all().delete()

    ahora = timezone.now()
    hoy = ahora.date()

    # 2. Infraestructura: Salas Físicas
    print("Creando salas físicas e infraestructura...")
    salas_data = [
        {"nombre": "Estudio Spinning & Cycling", "capacidad_maxima": 15, "descripcion": "15 bicicletas magnéticas Stages SC3 con consolas de potencia."},
        {"nombre": "Box Funcional & Cross Training", "capacidad_maxima": 18, "descripcion": "Zona de racks, barras olímpicas, kettlebells y suelo de caucho de alta densidad."},
        {"nombre": "Sala Polifuncional & Pilates", "capacidad_maxima": 20, "descripcion": "Espacio climatizado con espejos, reformers, colchonetas y bandas elásticas."},
        {"nombre": "Área de Musculación & Peso Libre", "capacidad_maxima": 35, "descripcion": "Máquinas selectorizadas Life Fitness, mancuernas de 2kg a 50kg y zona de poleas."},
    ]
    salas = {s["nombre"]: Sala.objects.create(**s) for s in salas_data}

    # 3. Catálogo Deportivo: Disciplinas
    print("Creando catálogo deportivo...")
    disciplinas_data = [
        {"nombre": "Spinning HIIT Potencia", "intensidad": "ALTA", "descripcion": "Intervalos de cadencia y potencia cardiovascular sobre bicicleta fija."},
        {"nombre": "Cross Training WOD", "intensidad": "ALTA", "descripcion": "Entrenamiento funcional de fuerza, levantamiento y acondicionamiento metabólico."},
        {"nombre": "Powerlifting & Fuerza", "intensidad": "ALTA", "descripcion": "Técnica y progresión de carga en sentadilla, press banca y peso muerto."},
        {"nombre": "Pilates Reformer & Core", "intensidad": "MEDIA", "descripcion": "Fortalecimiento de la musculatura estabilizadora profunda y flexibilidad guiada."},
        {"nombre": "Yoga Vinyasa Flow", "intensidad": "BAJA", "descripcion": "Secuencias fluidas de movilidad articular, equilibrio y respiración consciente."},
        {"nombre": "Boxeo & Conditioning", "intensidad": "ALTA", "descripcion": "Fundamentos de golpeo en saco, desplazamientos y circuitos pliométricos."},
    ]
    disciplinas = {d["nombre"]: Disciplina.objects.create(**d) for d in disciplinas_data}

    # 4. Tarifario y Planes Comerciales
    print("Creando planes comerciales y beneficios...")
    planes_data = [
        {
            "nombre": "Plan Mensual Full 24/7",
            "categoria": "MENSUAL",
            "precio": 34900,
            "duracion_dias": 30,
            "descripcion": "Acceso ilimitado a todas las salas y clases grupales sin restricción horaria.",
            "beneficios": "Acceso ilimitado 24/7\nClases grupales ilimitadas\nPase digital QR exclusivo\nEvaluación física mensual"
        },
        {
            "nombre": "Plan Smart Mañana AM",
            "categoria": "MANANA",
            "precio": 24900,
            "duracion_dias": 30,
            "descripcion": "Tarifa preferencial para entrenamientos matutinos (06:00 a 12:00 hrs).",
            "beneficios": "Ingreso de 06:00 a 12:00 hrs\nAcceso a salas de musculación y peso libre\nReserva de clases matutinas"
        },
        {
            "nombre": "Plan Tarde PM",
            "categoria": "TARDE",
            "precio": 26900,
            "duracion_dias": 30,
            "descripcion": "Acceso vespertino y nocturno de 12:01 a 23:00 hrs.",
            "beneficios": "Ingreso de 12:01 a 23:00 hrs\nAcceso total a peso libre y cardio\nReserva de clases vespertinas"
        },
        {
            "nombre": "Plan Black Anual VIP",
            "categoria": "ANUAL",
            "precio": 299900,
            "duracion_dias": 365,
            "descripcion": "Membresía anual completa con congelamiento libre y beneficios exclusivos.",
            "beneficios": "Acceso prioritario 365 días\nFreeze Policy hasta 60 días libres\n1 pase mensual de invitado gratis\nCasillero preferencial incluido"
        },
        {
            "nombre": "Pase Diario Express",
            "categoria": "DIARIO",
            "precio": 7900,
            "duracion_dias": 1,
            "descripcion": "Pase individual de acceso total válido durante una jornada completa.",
            "beneficios": "Acceso completo por 1 día\nUso de salas y duchas\nSin matrícula de inscripción"
        },
    ]
    planes = {p["nombre"]: Plan.objects.create(**p) for p in planes_data}

    # 5. Usuarios Staff (Administrador, Coordinador y Coaches)
    print("Creando cuentas de staff directivo y docente...")
    admin = Usuario.objects.create_superuser(
        username="admin", email="admin@fitlife.cl", password="admin1234",
        first_name="Felipe", last_name="Rivas", rut="17.892.451-2", rol="ADMINISTRADOR"
    )

    coord = Usuario.objects.create_user(
        username="coord_laura", email="laura.coord@fitlife.cl", password="coord1234",
        first_name="Laura", last_name="Contreras", rut="16.745.321-K", rol="COORDINADOR", is_staff=True
    )

    coach_carlos = Usuario.objects.create_user(
        username="coach_carlos", email="carlos.mendoza@fitlife.cl", password="coach1234",
        first_name="Carlos", last_name="Mendoza", rut="15.432.189-3", rol="INSTRUCTOR",
        especialidad="Spinning & HIIT Cardiovascular"
    )

    coach_valeria = Usuario.objects.create_user(
        username="coach_valeria", email="valeria.silva@fitlife.cl", password="coach1234",
        first_name="Valeria", last_name="Silva", rut="16.890.123-5", rol="INSTRUCTOR",
        especialidad="Cross Training & Levantamiento Olímpico"
    )

    coach_matias = Usuario.objects.create_user(
        username="coach_matias", email="matias.gomez@fitlife.cl", password="coach1234",
        first_name="Matías", last_name="Gómez", rut="17.112.334-8", rol="INSTRUCTOR",
        especialidad="Boxeo Formativo & Pilates"
    )

    # 6. Socios de Prueba Específicos para Demostración en Vivo
    print("Creando socios de casos de prueba controlados...")
    
    # 6.1 Socio Activo (Full 24/7 con pagos y reservas)
    socio_activo = Usuario.objects.create_user(
        username="socio_activo", email="camila.reyes@gmail.com", password="socio1234",
        first_name="Camila", last_name="Reyes", rut="18.222.333-4", rol="SOCIO"
    )
    m_activa = Membresia.objects.create(
        usuario=socio_activo, plan=planes["Plan Mensual Full 24/7"],
        fecha_inicio=hoy - timedelta(days=10), fecha_fin=hoy + timedelta(days=20), estado="ACTIVA"
    )
    Pago.objects.create(membresia=m_activa, monto=planes["Plan Mensual Full 24/7"].precio, metodo="TARJETA", fecha_pago=ahora - timedelta(days=10))

    # 6.2 Socio Vencido (Para probar rechazo sonoro en torniquete)
    socio_vencido = Usuario.objects.create_user(
        username="socio_vencido", email="ignacio.soto@gmail.com", password="socio1234",
        first_name="Ignacio", last_name="Soto", rut="19.444.555-6", rol="SOCIO"
    )
    m_vencida = Membresia.objects.create(
        usuario=socio_vencido, plan=planes["Plan Mensual Full 24/7"],
        fecha_inicio=hoy - timedelta(days=40), fecha_fin=hoy - timedelta(days=3), estado="VENCIDA"
    )
    Pago.objects.create(membresia=m_vencida, monto=planes["Plan Mensual Full 24/7"].precio, metodo="EFECTIVO", fecha_pago=ahora - timedelta(days=40))

    # 6.3 Socio Franja Mañana AM (Para probar validación horaria)
    socio_manana = Usuario.objects.create_user(
        username="socio_manana", email="diego.morales@gmail.com", password="socio1234",
        first_name="Diego", last_name="Morales", rut="17.333.444-5", rol="SOCIO"
    )
    m_manana = Membresia.objects.create(
        usuario=socio_manana, plan=planes["Plan Smart Mañana AM"],
        fecha_inicio=hoy - timedelta(days=5), fecha_fin=hoy + timedelta(days=25), estado="ACTIVA"
    )
    Pago.objects.create(membresia=m_manana, monto=planes["Plan Smart Mañana AM"].precio, metodo="TRANSFERENCIA", fecha_pago=ahora - timedelta(days=5))

    # 6.4 Socio Franja Tarde PM
    socio_tarde = Usuario.objects.create_user(
        username="socio_tarde", email="francisca.parra@gmail.com", password="socio1234",
        first_name="Francisca", last_name="Parra", rut="19.888.999-0", rol="SOCIO"
    )
    m_tarde = Membresia.objects.create(
        usuario=socio_tarde, plan=planes["Plan Tarde PM"],
        fecha_inicio=hoy - timedelta(days=12), fecha_fin=hoy + timedelta(days=18), estado="ACTIVA"
    )
    Pago.objects.create(membresia=m_tarde, monto=planes["Plan Tarde PM"].precio, metodo="TARJETA", fecha_pago=ahora - timedelta(days=12))

    # 6.5 Socio Congelado (Para probar reactivación y extensión de vigencia)
    socio_congelado = Usuario.objects.create_user(
        username="socio_congelado", email="valentina.castro@gmail.com", password="socio1234",
        first_name="Valentina", last_name="Castro", rut="18.555.666-7", rol="SOCIO"
    )
    Membresia.objects.create(
        usuario=socio_congelado, plan=planes["Plan Black Anual VIP"],
        fecha_inicio=hoy - timedelta(days=60), fecha_fin=hoy + timedelta(days=300),
        estado="CONGELADA", fecha_congelacion=hoy - timedelta(days=4)
    )

    # 6.6 Socio Nuevo sin membresía (Para probar el botón 'Cobrar en Caja' de recepción)
    socio_nuevo = Usuario.objects.create_user(
        username="socio_nuevo", email="tomas.araya@gmail.com", password="socio1234",
        first_name="Tomás", last_name="Araya", rut="20.123.456-7", rol="SOCIO"
    )

    # 7. Nómina Masiva Realista (20 Socios Adicionales)
    print("Creando nómina de socios regulares para tráfico y reservas...")
    nombres_apellidos = [
        ("Matías", "Albornoz", "18.321.654-1"), ("Catalina", "Valenzuela", "19.123.876-2"),
        ("Sebastián", "Navarro", "17.987.234-3"), ("Javiera", "Herrera", "20.456.789-4"),
        ("Rodrigo", "Fuentes", "16.543.210-5"), ("Paula", "Bustos", "18.876.543-6"),
        ("Andrés", "Cáceres", "17.432.198-7"), ("Fernanda", "Garrido", "19.654.321-8"),
        ("Gonzalo", "Miranda", "18.111.222-9"), ("Daniela", "Pizarro", "19.333.444-K"),
        ("Cristóbal", "Vargas", "17.555.666-1"), ("Macarena", "Ríos", "18.777.888-2"),
        ("Felipe", "Saavedra", "16.999.000-3"), ("Constanza", "Peña", "20.222.333-4"),
        ("Nicolás", "Lagos", "17.888.777-5"), ("Bárbara", "Escobar", "19.000.111-6"),
        ("Gabriel", "Acuña", "18.666.555-7"), ("Sofía", "Bravo", "19.777.666-8"),
        ("Esteban", "Correa", "17.222.111-9"), ("Claudia", "Medina", "18.999.888-0")
    ]

    socios_regulares = []
    planes_lista = [planes["Plan Mensual Full 24/7"], planes["Plan Smart Mañana AM"], planes["Plan Tarde PM"], planes["Plan Black Anual VIP"]]
    
    for idx, (nom, ape, rut_val) in enumerate(nombres_apellidos, start=1):
        u = Usuario.objects.create_user(
            username=f"socio_{idx}", email=f"{nom.lower()}.{ape.lower()}@gmail.com",
            password="socio1234", first_name=nom, last_name=ape, rut=rut_val, rol="SOCIO"
        )
        plan_sel = random.choice(planes_lista)
        # 16 activos, 4 vencidos
        if idx <= 16:
            inicio = hoy - timedelta(days=random.randint(5, 25))
            fin = inicio + timedelta(days=plan_sel.duracion_dias)
            m = Membresia.objects.create(usuario=u, plan=plan_sel, fecha_inicio=inicio, fecha_fin=fin, estado="ACTIVA")
            metodo = random.choice(["TARJETA", "TRANSFERENCIA", "EFECTIVO"])
            Pago.objects.create(membresia=m, monto=plan_sel.precio, metodo=metodo, fecha_pago=inicio)
        else:
            inicio = hoy - timedelta(days=45)
            fin = inicio + timedelta(days=plan_sel.duracion_dias)
            m = Membresia.objects.create(usuario=u, plan=plan_sel, fecha_inicio=inicio, fecha_fin=fin, estado="VENCIDA")
            Pago.objects.create(membresia=m, monto=plan_sel.precio, metodo="EFECTIVO", fecha_pago=inicio)
        
        socios_regulares.append(u)

    # 8. Clases Grupales (Agenda de Hoy y Semana)
    print("Programando clases grupales, listas de espera y reservas...")

    # 8.1 Clase Inminente (Inicia en 30 minutos: ideal para probar check-in automático del torniquete)
    hora_inminente = ahora + timedelta(minutes=30)
    clase_inminente = ClaseGrupal.objects.create(
        nombre="Spinning HIIT Potencia Matinal",
        descripcion="Intervalos de alta exigencia cardiovascular en subida simulada y sprints.",
        disciplina=disciplinas["Spinning HIIT Potencia"],
        sala=salas["Estudio Spinning & Cycling"],
        instructor=coach_carlos,
        fecha_hora=hora_inminente,
        cupo_maximo=15,
        estado="COORDINADA"
    )
    # Reserva de Camila Reyes (socio_activo) en estado CONFIRMADA
    ReservaClase.objects.create(usuario=socio_activo, clase=clase_inminente, estado="CONFIRMADA")
    for s in socios_regulares[:7]:
        ReservaClase.objects.create(usuario=s, clase=clase_inminente, estado="CONFIRMADA")

    # 8.2 Clase Llena con Lista de Espera FIFO activa
    hora_tarde = ahora.replace(hour=19, minute=0, second=0, microsecond=0)
    if hora_tarde < ahora:
        hora_tarde = ahora + timedelta(hours=3)

    clase_llena = ClaseGrupal.objects.create(
        nombre="Cross Training WOD Explosivo",
        descripcion="Circuito EMOM de 24 minutos combinando clean & jerk, pull-ups y box jumps.",
        disciplina=disciplinas["Cross Training WOD"],
        sala=salas["Box Funcional & Cross Training"],
        instructor=coach_valeria,
        fecha_hora=hora_tarde,
        cupo_maximo=10,
        estado="COORDINADA"
    )
    # 10 cupos llenos
    for s in socios_regulares[8:18]:
        ReservaClase.objects.create(usuario=s, clase=clase_llena, estado="CONFIRMADA")

    # 3 socios en lista de espera FIFO
    ListaEspera.objects.create(usuario=socio_manana, clase=clase_llena, fecha_ingreso=ahora - timedelta(minutes=45))
    ListaEspera.objects.create(usuario=socio_tarde, clase=clase_llena, fecha_ingreso=ahora - timedelta(minutes=30))
    ListaEspera.objects.create(usuario=socios_regulares[0], clase=clase_llena, fecha_ingreso=ahora - timedelta(minutes=15))

    # 8.3 Clase Pasada de Hoy (Para verificar asistencia acreditada por profesor)
    hora_pasada = ahora - timedelta(hours=3)
    clase_pasada = ClaseGrupal.objects.create(
        nombre="Pilates Reformer & Postura",
        descripcion="Trabajo excéntrico de core y alineación pélvica.",
        disciplina=disciplinas["Pilates Reformer & Core"],
        sala=salas["Sala Polifuncional & Pilates"],
        instructor=coach_matias,
        fecha_hora=hora_pasada,
        cupo_maximo=12,
        estado="COORDINADA"
    )
    for idx, s in enumerate(socios_regulares[2:8]):
        # 4 asistieron, 2 faltaron
        st = "ASISTIO" if idx < 4 else "NO_SHOW"
        ReservaClase.objects.create(usuario=s, clase=clase_pasada, estado=st)

    # 8.4 Clase Programada sin Coordinar (Para probar el modal 'Coordinar' del coordinador)
    ClaseGrupal.objects.create(
        nombre="Boxeo & Conditioning Sparring",
        descripcion="Combinaciones de golpeo al saco y desplazamientos tácticos.",
        disciplina=disciplinas["Boxeo & Conditioning"],
        sala=salas["Box Funcional & Cross Training"],
        cupo_maximo=15,
        estado="PROGRAMADA"
    )

    # 9. Auditoría de Accesos en Torniquete y Aforo Real
    print("Generando eventos de torniquete y ocupación física actual...")
    
    # 16 socios ingresaron hoy
    # 10 salieron, 6 permanecen adentro (+ 12 socios adicionales distribuidos = 18 personas en aforo)
    tiempo_base = ahora - timedelta(hours=4)
    
    # Entradas con salida registrada
    for s in socios_regulares[:8]:
        RegistroAccesoQR.objects.create(
            usuario=s, tipo="ENTRADA", estado="PERMITIDO",
            fecha_hora=tiempo_base + timedelta(minutes=random.randint(10, 60)),
            motivo="Lector QR - Plan Mensual Full 24/7"
        )
        RegistroAccesoQR.objects.create(
            usuario=s, tipo="SALIDA", estado="PERMITIDO",
            fecha_hora=tiempo_base + timedelta(minutes=random.randint(70, 120)),
            motivo="Salida normal"
        )

    # 18 socios que ingresaron en las últimas 2 horas y siguen dentro (Aforo en sala = 18 / 80)
    for s in socios_regulares[8:]:
        RegistroAccesoQR.objects.create(
            usuario=s, tipo="ENTRADA", estado="PERMITIDO",
            fecha_hora=ahora - timedelta(minutes=random.randint(15, 95)),
            motivo="Lector QR - Plan Mensual Full 24/7"
        )

    # Evento de rechazo registrado en torniquete (auditoría visible)
    RegistroAccesoQR.objects.create(
        usuario=socio_vencido, tipo="ENTRADA", estado="DENEGADO",
        fecha_hora=ahora - timedelta(minutes=25),
        motivo="Membresía Vencida"
    )

    print("\nSembrado de datos finalizado con éxito.")
    print("================================================================")
    print("Resumen del estado operativo:")
    print(f"• Socios Totales: {Usuario.objects.filter(rol='SOCIO').count()}")
    print(f"• Membresías Activas: {Membresia.objects.filter(estado='ACTIVA').count()}")
    print(f"• Aforo en Vivo: {RegistroAccesoQR.objects.filter(tipo='ENTRADA', estado='PERMITIDO', fecha_hora__date=hoy).count() - RegistroAccesoQR.objects.filter(tipo='SALIDA', estado='PERMITIDO', fecha_hora__date=hoy).count()} personas")
    print(f"• Recaudación Bruta del Mes: ${Pago.objects.aggregate(t=django.db.models.Sum('monto'))['t']:,} CLP")
    print(f"• Clases en Agenda: {ClaseGrupal.objects.count()} sesiones")
    print("================================================================")

if __name__ == "__main__":
    sembrar_datos()
