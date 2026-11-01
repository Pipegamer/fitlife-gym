from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

# ==============================================================================
# 1. USUARIOS Y CONTROL DE ACCESO BASADO EN ROLES (RBAC)
# ==============================================================================
class Usuario(AbstractUser):
    ROLES = (
        ('SOCIO', 'Socio / Cliente'),
        ('INSTRUCTOR', 'Instructor de Clases'),
        ('COORDINADOR', 'Coordinador Deportivo'),
        ('ADMINISTRADOR', 'Administrador General / Recepción'),
    )
    rol = models.CharField(max_length=20, choices=ROLES, default='SOCIO')
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=15, blank=True, default='')
    especialidad = models.CharField(max_length=120, blank=True, default='')
    codigo_qr = models.CharField(max_length=64, unique=True, blank=True, null=True)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)  # Penalización por No-Show

    def save(self, *args, **kwargs):
        if not self.codigo_qr:
            self.codigo_qr = f"FIT-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def esta_penalizado(self):
        return bool(self.bloqueado_hasta and self.bloqueado_hasta > timezone.now())

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_rol_display()})"


# ==============================================================================
# 2. INFRAESTRUCTURA Y CATÁLOGO DE DISCIPLINAS
# ==============================================================================
class Sala(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    capacidad_maxima = models.PositiveIntegerField(default=20)
    descripcion = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f"{self.nombre} (Capacidad: {self.capacidad_maxima} pers.)"


class Disciplina(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, default='')
    intensidad = models.CharField(
        max_length=20,
        choices=(('BAJA', 'Baja'), ('MEDIA', 'Media'), ('ALTA', 'Alta')),
        default='MEDIA'
    )

    def __str__(self):
        return f"{self.nombre} (Intensidad {self.intensidad})"


# ==============================================================================
# 3. PLANES CON BENEFICIOS Y MEMBRESÍAS CON FREEZE POLICY
# ==============================================================================
class Plan(models.Model):
    CATEGORIAS = (
        ('DIARIO', 'Pase Diario (1 Día)'),
        ('MANANA', 'Plan Mañana (AM: 06:00 a 12:00)'),
        ('TARDE', 'Plan Tarde (PM: 12:01 a 23:00)'),
        ('MENSUAL', 'Plan Mensual Full (24/7)'),
        ('ANUAL', 'Plan Anual VIP (24/7)'),
    )
    nombre = models.CharField(max_length=100, unique=True)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='MENSUAL')
    precio = models.DecimalField(max_digits=10, decimal_places=0)
    duracion_dias = models.PositiveIntegerField(default=30)
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fin = models.TimeField(null=True, blank=True)
    descripcion = models.TextField(blank=True, default='')
    beneficios = models.TextField(blank=True, default='Acceso a sala de musculación\nEvaluación física inicial\nCasillero en camarines')

    def lista_beneficios(self):
        if not self.beneficios:
            return []
        return [b.strip() for b in self.beneficios.split('\n') if b.strip()]

    def __str__(self):
        return f"{self.nombre} (${self.precio:,}) [{self.get_categoria_display()}]"


class Membresia(models.Model):
    ESTADOS = (
        ('ACTIVA', 'Activa'),
        ('VENCIDA', 'Vencida'),
        ('CONGELADA', 'Congelada'),
        ('CANCELADA', 'Cancelada'),
    )
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='membresias')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='membresias')
    fecha_inicio = models.DateField(default=timezone.now)
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVA')
    fecha_congelacion = models.DateField(null=True, blank=True)  # Freeze Policy
    actualizado_el = models.DateTimeField(auto_now=True)

    def esta_vigente(self):
        hoy = timezone.now().date()
        return self.estado == 'ACTIVA' and self.fecha_inicio <= hoy <= self.fecha_fin

    def __str__(self):
        return f"Membresía {self.plan.nombre} - {self.usuario.username} [{self.estado}]"


class Pago(models.Model):
    METODOS = (
        ('TRANSFERENCIA', 'Transferencia'),
        ('TARJETA', 'Tarjeta Débito/Crédito'),
        ('EFECTIVO', 'Efectivo'),
    )
    membresia = models.ForeignKey(Membresia, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=10, decimal_places=0)
    fecha_pago = models.DateTimeField(auto_now_add=True)
    metodo = models.CharField(max_length=20, choices=METODOS, default='TARJETA')

    def __str__(self):
        return f"Pago #{self.id} (${self.monto}) - {self.membresia.usuario.username}"


# ==============================================================================
# 4. CLASES GRUPALES CON DESCRIPCIÓN Y ESTADOS DE COORDINACIÓN
# ==============================================================================
class ClaseGrupal(models.Model):
    ESTADOS_CLASE = (
        ('PROGRAMADA', 'Programada (Sin Coordinar)'),
        ('COORDINADA', 'Coordinada / Activa'),
        ('SUSPENDIDA', 'Suspendida por Coordinador'),
    )
    DIAS_SEMANA_MAP = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

    nombre = models.CharField(max_length=100)
    disciplina = models.ForeignKey(Disciplina, on_delete=models.SET_NULL, null=True, related_name='clases')
    sala = models.ForeignKey(Sala, on_delete=models.SET_NULL, null=True, related_name='clases_programadas')
    instructor = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'rol': 'INSTRUCTOR'}, related_name='clases_asignadas'
    )
    fecha_hora = models.DateTimeField(null=True, blank=True)
    cupo_maximo = models.PositiveIntegerField(default=15)
    descripcion = models.TextField(blank=True, default='Enfoque del entrenamiento funcional y acondicionamiento general.')
    estado = models.CharField(max_length=20, choices=ESTADOS_CLASE, default='PROGRAMADA')
    motivo_suspension = models.CharField(max_length=255, blank=True, default='')

    @property
    def dia_semana_nombre(self):
        if self.fecha_hora:
            local_dt = timezone.localtime(self.fecha_hora)
            return self.DIAS_SEMANA_MAP[local_dt.weekday()]
        return "Sin fecha"

    @property
    def cupos_ocupados(self):
        return self.reservas.filter(estado__in=['CONFIRMADA', 'ASISTIO']).count()

    @property
    def cupos_disponibles(self):
        if self.estado == 'SUSPENDIDA':
            return 0
        return max(0, self.cupo_maximo - self.cupos_ocupados)

    def __str__(self):
        fecha_str = self.fecha_hora.strftime('%d/%m %H:%M') if self.fecha_hora else 'Sin fecha'
        return f"{self.nombre} ({fecha_str}) - {self.get_estado_display()}"


class ReservaClase(models.Model):
    ESTADOS = (
        ('CONFIRMADA', 'Confirmada'),
        ('CANCELADA', 'Cancelada'),
        ('ASISTIO', 'Asistió'),
        ('NO_SHOW', 'No Asistió'),
    )
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='reservas')
    clase = models.ForeignKey(ClaseGrupal, on_delete=models.CASCADE, related_name='reservas')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='CONFIRMADA')
    fecha_reserva = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'clase')

    def __str__(self):
        return f"Reserva {self.clase.nombre} - {self.usuario.username} [{self.estado}]"


class ListaEspera(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='esperas')
    clase = models.ForeignKey(ClaseGrupal, on_delete=models.CASCADE, related_name='en_espera')
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    promovido = models.BooleanField(default=False)

    class Meta:
        ordering = ['fecha_ingreso']
        unique_together = ('usuario', 'clase')

    def __str__(self):
        return f"Espera {self.clase.nombre} - {self.usuario.username}"


# ==============================================================================
# 5. CONTROL DE ACCESO QR Y AUDITORÍA DE AFORO (TORNIQUETE)
# ==============================================================================
class RegistroAccesoQR(models.Model):
    TIPOS = (
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida'),
    )
    ESTADOS = (
        ('PERMITIDO', 'Permitido'),
        ('DENEGADO', 'Denegado'),
    )
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='accesos')
    tipo = models.CharField(max_length=10, choices=TIPOS, default='ENTRADA')
    estado = models.CharField(max_length=10, choices=ESTADOS)
    motivo = models.CharField(max_length=255, blank=True, default='')
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"[{self.fecha_hora.strftime('%H:%M:%S')}] {self.usuario.username} - {self.tipo} ({self.estado})"
