import csv
import io
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from django.db.models import Sum, Q, Count
from django.utils import timezone
from datetime import timedelta, time
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from .models import (
    Usuario, Sala, Disciplina, Plan, Membresia, Pago, 
    ClaseGrupal, ReservaClase, ListaEspera, RegistroAccesoQR
)
from .serializers import (
    UsuarioSerializer, SalaSerializer, DisciplinaSerializer, PlanSerializer,
    MembresiaSerializer, PagoSerializer, ClaseGrupalSerializer,
    ReservaClaseSerializer, ListaEsperaSerializer, RegistroAccesoQRSerializer
)

# ==============================================================================
# HELPERS DE PERMISOS ESTRICTOS (RBAC)
# ==============================================================================
def es_administrador(user):
    return user.is_authenticated and (user.rol == 'ADMINISTRADOR' or user.is_superuser)

def es_coordinador_o_admin(user):
    return user.is_authenticated and (user.rol in ['COORDINADOR', 'ADMINISTRADOR'] or user.is_superuser)

# ==============================================================================
# RUTINAS AUTOMÁTICAS: NO-SHOW Y AFORO LIMPIO
# ==============================================================================
def procesar_reglas_automaticas():
    ahora = timezone.now()
    hoy = ahora.date()
    hace_1_hora = ahora - timedelta(hours=1)

    reservas_olvidadas = ReservaClase.objects.filter(
        estado='CONFIRMADA', clase__fecha_hora__lt=hace_1_hora
    ).select_related('usuario')

    for r in reservas_olvidadas:
        r.estado = 'NO_SHOW'
        r.save()
        inicio_mes = hoy.replace(day=1)
        faltas = ReservaClase.objects.filter(
            usuario=r.usuario, estado='NO_SHOW', clase__fecha_hora__date__gte=inicio_mes
        ).count()
        if faltas >= 3:
            r.usuario.bloqueado_hasta = ahora + timedelta(days=7)
            r.usuario.save()

    hace_3_horas = ahora - timedelta(hours=3)
    entradas_antiguas = RegistroAccesoQR.objects.filter(
        tipo='ENTRADA', estado='PERMITIDO', fecha_hora__date=hoy, fecha_hora__lt=hace_3_horas
    ).select_related('usuario')

    for ent in entradas_antiguas:
        tiene_salida = RegistroAccesoQR.objects.filter(
            usuario=ent.usuario, tipo='SALIDA', estado='PERMITIDO', fecha_hora__gt=ent.fecha_hora
        ).exists()
        if not tiene_salida:
            RegistroAccesoQR.objects.create(
                usuario=ent.usuario, tipo='SALIDA', estado='PERMITIDO',
                motivo='Salida automática por inactividad (> 3 hrs)'
            )

# ==============================================================================
# 1. GESTIÓN ADMINISTRADOR: USUARIOS, COBRO EN CAJA Y NÓMINA
# ==============================================================================
class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all().order_by('-id')
    serializer_class = UsuarioSerializer

    @action(detail=False, methods=['post'], url_path='crear-usuario')
    @transaction.atomic
    def crear_usuario(self, request):
        if not es_administrador(request.user):
            return Response({'error': 'Acceso denegado: Se requiere rol ADMINISTRADOR.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        rol = data.get('rol', 'SOCIO')
        rut = data.get('rut', '').strip()
        nombre = data.get('first_name', '').strip()
        especialidad = data.get('especialidad', '').strip()
        email = data.get('email', '').strip()
        plan_id = data.get('plan_id')
        metodo_pago = data.get('metodo_pago', 'TARJETA')

        if not username or not password:
            return Response({'error': 'Usuario y contraseña son requeridos.'}, status=status.HTTP_400_BAD_REQUEST)

        if Usuario.objects.filter(username=username).exists():
            return Response({'error': f'El usuario "{username}" ya existe.'}, status=status.HTTP_400_BAD_REQUEST)

        if rut and Usuario.objects.filter(rut=rut).exists():
            return Response({'error': f'El RUT "{rut}" ya está registrado en el sistema.'}, status=status.HTTP_400_BAD_REQUEST)

        nuevo_user = Usuario.objects.create_user(
            username=username, password=password, email=email,
            first_name=nombre, rut=rut, rol=rol, especialidad=especialidad
        )

        if rol in ['ADMINISTRADOR', 'COORDINADOR']:
            nuevo_user.is_staff = True
            nuevo_user.save()

        if rol == 'SOCIO' and plan_id:
            plan = Plan.objects.filter(id=plan_id).first()
            if plan:
                hoy = timezone.now().date()
                memb = Membresia.objects.create(
                    usuario=nuevo_user, plan=plan, fecha_inicio=hoy,
                    fecha_fin=hoy + timedelta(days=plan.duracion_dias), estado='ACTIVA'
                )
                monto_real = 0 if metodo_pago == 'CORTESIA' else plan.precio
                Pago.objects.create(
                    membresia=memb, 
                    monto=monto_real, 
                    metodo='EFECTIVO' if metodo_pago == 'CORTESIA' else metodo_pago
                )

        return Response({
            'mensaje': f'Usuario "{nuevo_user.username}" registrado exitosamente como {nuevo_user.get_rol_display()}.', 
            'id': nuevo_user.id
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='cobrar-membresia-caja')
    @transaction.atomic
    def cobrar_membresia_caja(self, request, pk=None):
        if not es_administrador(request.user):
            return Response({'error': 'Acceso no autorizado: Solo recepción / administración puede cobrar planes.'}, status=status.HTTP_403_FORBIDDEN)

        socio = self.get_object()
        plan_id = request.data.get('plan_id')
        metodo_pago = request.data.get('metodo_pago', 'EFECTIVO')

        plan = Plan.objects.filter(id=plan_id).first()
        if not plan:
            return Response({'error': 'Debes seleccionar un plan válido.'}, status=status.HTTP_400_BAD_REQUEST)

        hoy = timezone.now().date()
        socio.membresias.filter(estado='ACTIVA').update(estado='CANCELADA')

        nueva_membresia = Membresia.objects.create(
            usuario=socio,
            plan=plan,
            fecha_inicio=hoy,
            fecha_fin=hoy + timedelta(days=plan.duracion_dias),
            estado='ACTIVA'
        )

        monto_cobrado = 0 if metodo_pago == 'CORTESIA' else plan.precio
        pago = Pago.objects.create(
            membresia=nueva_membresia,
            monto=monto_cobrado,
            metodo='EFECTIVO' if metodo_pago == 'CORTESIA' else metodo_pago
        )

        return Response({
            'mensaje': f'Cobro exitoso: Plan "{plan.nombre}" activado para {socio.username} hasta el {nueva_membresia.fecha_fin.strftime("%d/%m/%Y")} (Monto: ${monto_cobrado:,} vía {metodo_pago}).',
            'pago_id': pago.id
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='carga-masiva-csv')
    @transaction.atomic
    def carga_masiva_csv(self, request):
        if not es_administrador(request.user):
            return Response({'error': 'Acceso denegado: Solo el Administrador puede procesar migraciones masivas.'}, status=status.HTTP_403_FORBIDDEN)

        archivo = request.FILES.get('archivo_csv')
        if not archivo or not archivo.name.endswith('.csv'):
            return Response({'error': 'Debes subir un archivo .csv válido.'}, status=status.HTTP_400_BAD_REQUEST)

        decoded_file = archivo.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded_file))
        plan_defecto = Plan.objects.first()
        hoy = timezone.now().date()
        creados = 0

        for row in reader:
            u_name = row.get('username', '').strip()
            p_word = row.get('password', 'socio1234').strip()
            rut = row.get('rut', '').strip()
            nombre = row.get('nombre', '').strip()
            email = row.get('email', '').strip()

            if u_name and not Usuario.objects.filter(username=u_name).exists():
                socio = Usuario.objects.create_user(
                    username=u_name, password=p_word, email=email,
                    first_name=nombre, rut=rut, rol='SOCIO'
                )
                if plan_defecto:
                    m = Membresia.objects.create(
                        usuario=socio, plan=plan_defecto, fecha_inicio=hoy,
                        fecha_fin=hoy + timedelta(days=plan_defecto.duracion_dias), estado='ACTIVA'
                    )
                    Pago.objects.create(membresia=m, monto=plan_defecto.precio, metodo='TRANSFERENCIA')
                creados += 1

        return Response({'mensaje': f'Carga masiva completada: {creados} nuevos socios registrados con membresía activa.'})

    @action(detail=True, methods=['post'], url_path='cambiar-estado-membresia')
    def cambiar_estado_membresia(self, request, pk=None):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede suspender o cancelar membresías.'}, status=status.HTTP_403_FORBIDDEN)
        socio = self.get_object()
        nuevo_estado = request.data.get('estado')
        
        if nuevo_estado == 'ACTIVA':
            return Response({'error': 'Para activar o renovar una membresía debes usar el módulo "Cobrar en Caja" con su respectivo método de pago.'}, status=status.HTTP_400_BAD_REQUEST)

        memb = socio.membresias.filter(estado='ACTIVA').first() or socio.membresias.first()
        if memb:
            memb.estado = nuevo_estado
            memb.save()
            return Response({'mensaje': f'Membresía de {socio.username} cambiada a {nuevo_estado}.'})
        return Response({'error': 'El usuario no posee una membresía vinculada.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='toggle-cuenta')
    def toggle_cuenta(self, request, pk=None):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede suspender o activar cuentas.'}, status=status.HTTP_403_FORBIDDEN)
        usuario = self.get_object()
        if usuario == request.user:
            return Response({'error': 'No puedes bloquear tu propia cuenta administrativa.'}, status=status.HTTP_400_BAD_REQUEST)
        usuario.is_active = not usuario.is_active
        usuario.save()
        msg = "reactivada" if usuario.is_active else "desactivada"
        return Response({'mensaje': f'Cuenta de {usuario.username} {msg}.'})

# ==============================================================================
# 2. INFRAESTRUCTURA, PLANES Y FREEZE POLICY
# ==============================================================================
class SalaViewSet(viewsets.ModelViewSet):
    queryset = Sala.objects.all().order_by('nombre')
    serializer_class = SalaSerializer

    def create(self, request, *args, **kwargs):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede crear salas físicas.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede eliminar salas físicas.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class DisciplinaViewSet(viewsets.ModelViewSet):
    queryset = Disciplina.objects.all().order_by('nombre')
    serializer_class = DisciplinaSerializer

    def create(self, request, *args, **kwargs):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede crear disciplinas deportivas.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede eliminar disciplinas.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class PlanViewSet(viewsets.ModelViewSet):
    queryset = Plan.objects.all().order_by('precio')
    serializer_class = PlanSerializer

    def create(self, request, *args, **kwargs):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede crear planes comerciales.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede modificar planes.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede modificar planes.'}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede eliminar planes.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class MembresiaViewSet(viewsets.ModelViewSet):
    queryset = Membresia.objects.all().select_related('usuario', 'plan')
    serializer_class = MembresiaSerializer

    @action(detail=False, methods=['post'], url_path='contratar')
    @transaction.atomic
    def contratar_plan(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Inicia sesión para contratar.'}, status=status.HTTP_401_UNAUTHORIZED)
        plan_id = request.data.get('plan_id')
        plan = Plan.objects.filter(id=plan_id).first()
        if not plan:
            return Response({'error': 'Plan no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        hoy = timezone.now().date()
        Membresia.objects.filter(usuario=request.user, estado='ACTIVA').update(estado='CANCELADA')
        nueva = Membresia.objects.create(
            usuario=request.user, plan=plan, fecha_inicio=hoy,
            fecha_fin=hoy + timedelta(days=plan.duracion_dias), estado='ACTIVA'
        )
        Pago.objects.create(membresia=nueva, monto=plan.precio, metodo='TARJETA')
        return Response({'mensaje': f'Plan {plan.nombre} contratado con éxito.', 'vence': nueva.fecha_fin.strftime('%d/%m/%Y')}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='congelar-socio')
    @transaction.atomic
    def congelar_membresia(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado.'}, status=status.HTTP_401_UNAUTHORIZED)
        memb = request.user.membresias.filter(estado='ACTIVA').first()
        if not memb:
            return Response({'error': 'No posees una membresía activa para pausar.'}, status=status.HTTP_400_BAD_REQUEST)
        if memb.plan.categoria == 'DIARIO':
            return Response({'error': 'El pase diario no admite congelamiento.'}, status=status.HTTP_400_BAD_REQUEST)

        memb.estado = 'CONGELADA'
        memb.fecha_congelacion = timezone.now().date()
        memb.save()
        return Response({'mensaje': 'Membresía pausada con éxito. El acceso al gimnasio ha sido suspendido temporalmente.'})

    @action(detail=False, methods=['post'], url_path='reactivar-socio')
    @transaction.atomic
    def reactivar_membresia(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado.'}, status=status.HTTP_401_UNAUTHORIZED)
        memb = request.user.membresias.filter(estado='CONGELADA').first()
        if not memb or not memb.fecha_congelacion:
            return Response({'error': 'No tienes una membresía congelada.'}, status=status.HTTP_400_BAD_REQUEST)

        hoy = timezone.now().date()
        dias_pausa = max(1, (hoy - memb.fecha_congelacion).days)
        memb.fecha_fin = memb.fecha_fin + timedelta(days=dias_pausa)
        memb.estado = 'ACTIVA'
        memb.fecha_congelacion = None
        memb.save()
        return Response({'mensaje': f'Membresía reactivada. Se añadieron {dias_pausa} días a tu vigencia (Nuevo vencimiento: {memb.fecha_fin.strftime("%d/%m/%Y")}).'})

    @action(detail=False, methods=['post'], url_path='cancelar-socio')
    @transaction.atomic
    def cancelar_plan_socio(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'No autenticado.'}, status=status.HTTP_401_UNAUTHORIZED)
        memb = request.user.membresias.filter(estado='ACTIVA').first()
        if not memb:
            return Response({'error': 'No tienes una membresía activa.'}, status=status.HTTP_400_BAD_REQUEST)
        memb.estado = 'CANCELADA'
        memb.save()
        return Response({'mensaje': 'Membresía cancelada correctamente.'})


class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.all().select_related('membresia__usuario')
    serializer_class = PagoSerializer

# ==============================================================================
# 3. CLASES GRUPALES: RESERVAS, WAITLIST FIFO Y CANCELACIÓN A 2 HORAS
# ==============================================================================
class ClaseGrupalViewSet(viewsets.ModelViewSet):
    queryset = ClaseGrupal.objects.all().select_related('disciplina', 'instructor', 'sala').order_by('fecha_hora')
    serializer_class = ClaseGrupalSerializer

    @action(detail=False, methods=['post'], url_path='crear-clase-admin')
    def crear_clase_admin(self, request):
        if not es_administrador(request.user):
            return Response({'error': 'Solo el Administrador puede registrar clases en el catálogo base.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        nombre = data.get('nombre', '').strip()
        descripcion = data.get('descripcion', '').strip()
        disciplina_id = data.get('disciplina_id')
        sala_id = data.get('sala_id')
        cupo_maximo = int(data.get('cupo_maximo', 15))

        sala = Sala.objects.filter(id=sala_id).first()
        disciplina = Disciplina.objects.filter(id=disciplina_id).first()

        if not (nombre and sala and disciplina):
            return Response({'error': 'Nombre, Sala y Disciplina son campos requeridos.'}, status=status.HTTP_400_BAD_REQUEST)

        clase = ClaseGrupal.objects.create(
            nombre=nombre, descripcion=descripcion or 'Entrenamiento físico guiado.',
            disciplina=disciplina, sala=sala, cupo_maximo=cupo_maximo, estado='PROGRAMADA'
        )
        return Response({'mensaje': f'Clase "{clase.nombre}" agregada al catálogo base.', 'id': clase.id}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='coordinar')
    @transaction.atomic
    def coordinar_clase(self, request, pk=None):
        if not es_coordinador_o_admin(request.user):
            return Response({'error': 'Permiso denegado: Se requiere rol COORDINADOR.'}, status=status.HTTP_403_FORBIDDEN)

        clase = self.get_object()
        instructor_id = request.data.get('instructor_id')
        fecha_hora = request.data.get('fecha_hora')

        instructor = Usuario.objects.filter(id=instructor_id, rol='INSTRUCTOR').first()
        if not instructor:
            return Response({'error': 'Instructor no válido.'}, status=status.HTTP_404_NOT_FOUND)

        dt = timezone.datetime.fromisoformat(fecha_hora)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)

        v_inicio = dt - timedelta(minutes=50)
        v_fin = dt + timedelta(minutes=50)

        if ClaseGrupal.objects.filter(sala=clase.sala, fecha_hora__range=(v_inicio, v_fin)).exclude(id=clase.id).exists():
            return Response({'error': f'La sala "{clase.sala.nombre}" ya tiene una clase en ese bloque horario.'}, status=status.HTTP_400_BAD_REQUEST)

        if ClaseGrupal.objects.filter(instructor=instructor, fecha_hora__range=(v_inicio, v_fin)).exclude(id=clase.id).exists():
            return Response({'error': f'El profesor {instructor.get_full_name()} ya tiene otra clase agendada a esa misma hora.'}, status=status.HTTP_400_BAD_REQUEST)

        clase.instructor = instructor
        clase.fecha_hora = dt
        clase.estado = 'COORDINADA'
        clase.motivo_suspension = ''
        clase.save()
        return Response({'mensaje': f'Clase "{clase.nombre}" coordinada exitosamente para el {dt.strftime("%d/%m %H:%M")}.'})

    @action(detail=True, methods=['post'], url_path='suspender')
    @transaction.atomic
    def suspender_clase(self, request, pk=None):
        if not es_coordinador_o_admin(request.user):
            return Response({'error': 'Permiso denegado: Se requiere rol COORDINADOR.'}, status=status.HTTP_403_FORBIDDEN)

        clase = self.get_object()
        motivo = request.data.get('motivo', 'Imprevisto de fuerza mayor informado por Coordinación.')
        clase.estado = 'SUSPENDIDA'
        clase.motivo_suspension = motivo
        clase.save()
        clase.reservas.filter(estado='CONFIRMADA').update(estado='CANCELADA')
        return Response({'mensaje': f'Clase "{clase.nombre}" suspendida. Motivo: {motivo}'})

    @action(detail=True, methods=['post'], url_path='actualizar-rutina')
    def actualizar_rutina(self, request, pk=None):
        clase = self.get_object()
        if not (request.user.is_authenticated and (request.user == clase.instructor or request.user.rol == 'ADMINISTRADOR' or request.user.is_superuser)):
            return Response({'error': 'No tienes autorización para editar el plan de entrenamiento de esta clase.'}, status=status.HTTP_403_FORBIDDEN)

        descripcion = request.data.get('descripcion', '').strip()
        if not descripcion:
            return Response({'error': 'La descripción física del entrenamiento no puede estar vacía.'}, status=status.HTTP_400_BAD_REQUEST)

        clase.descripcion = descripcion
        clase.save()
        return Response({'mensaje': f'Enfoque de entrenamiento actualizado para la sesión "{clase.nombre}".'})

    @action(detail=True, methods=['post'], url_path='reservar')
    @transaction.atomic
    def reservar(self, request, pk=None):
        clase = self.get_object()
        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response({'error': 'Inicia sesión para reservar.'}, status=status.HTTP_401_UNAUTHORIZED)

        if user.esta_penalizado():
            dias_rest = (user.bloqueado_hasta - timezone.now()).days + 1
            return Response({
                'error': f'Tu cuenta está temporalmente suspendida por acumulación de inasistencias (No-Show). Podrás reservar en {dias_rest} días.'
            }, status=status.HTTP_403_FORBIDDEN)

        if clase.estado == 'SUSPENDIDA':
            return Response({'error': f'Clase suspendida: {clase.motivo_suspension}'}, status=status.HTTP_400_BAD_REQUEST)
        if clase.estado != 'COORDINADA' or not clase.fecha_hora:
            return Response({'error': 'Clase pendiente de coordinación.'}, status=status.HTTP_400_BAD_REQUEST)

        hoy = timezone.now().date()
        if not user.membresias.filter(estado='ACTIVA', fecha_inicio__lte=hoy, fecha_fin__gte=hoy).exists():
            return Response({'error': 'Necesitas una membresía ACTIVA para reservar clases.'}, status=status.HTTP_403_FORBIDDEN)

        v_inicio = clase.fecha_hora - timedelta(minutes=50)
        v_fin = clase.fecha_hora + timedelta(minutes=50)
        if ReservaClase.objects.filter(usuario=user, estado='CONFIRMADA', clase__fecha_hora__range=(v_inicio, v_fin)).exclude(clase=clase).exists():
            return Response({'error': 'Ya tienes una reserva confirmada en este mismo horario.'}, status=status.HTTP_400_BAD_REQUEST)

        reserva_existente = ReservaClase.objects.filter(usuario=user, clase=clase).first()
        if reserva_existente and reserva_existente.estado in ['CONFIRMADA', 'ASISTIO']:
            return Response({'error': 'Ya tienes cupo confirmado en esta clase.'}, status=status.HTTP_400_BAD_REQUEST)

        if clase.cupos_disponibles > 0:
            if reserva_existente:
                reserva_existente.estado = 'CONFIRMADA'
                reserva_existente.save()
            else:
                ReservaClase.objects.create(usuario=user, clase=clase, estado='CONFIRMADA')
            ListaEspera.objects.filter(usuario=user, clase=clase).update(promovido=True)
            return Response({'mensaje': f'¡Cupo confirmado para {clase.nombre}!', 'tipo': 'CONFIRMADA'}, status=status.HTTP_201_CREATED)
        else:
            espera, _ = ListaEspera.objects.get_or_create(usuario=user, clase=clase)
            espera.promovido = False
            espera.save()
            pos = ListaEspera.objects.filter(clase=clase, promovido=False, fecha_ingreso__lte=espera.fecha_ingreso).count()
            return Response({'mensaje': f'Clase llena. Ingresaste a la Lista de Espera en la posición #{pos}.', 'tipo': 'ESPERA', 'posicion': pos}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='cancelar-reserva')
    @transaction.atomic
    def cancelar_reserva(self, request, pk=None):
        clase = self.get_object()
        user = request.user if request.user.is_authenticated else None
        reserva = ReservaClase.objects.filter(usuario=user, clase=clase, estado='CONFIRMADA').first()
        if not reserva:
            return Response({'error': 'No tienes una reserva activa para cancelar.'}, status=status.HTTP_404_NOT_FOUND)

        if clase.fecha_hora and (clase.fecha_hora - timezone.now() < timedelta(hours=2)):
            return Response({
                'error': 'Solo puedes cancelar con al menos 2 horas de anticipación para que otro socio pueda ocupar el cupo.'
            }, status=status.HTTP_400_BAD_REQUEST)

        reserva.estado = 'CANCELADA'
        reserva.save()

        siguiente = ListaEspera.objects.filter(clase=clase, promovido=False).order_by('fecha_ingreso').first()
        msg_espera = "No hay socios en espera."
        if siguiente:
            res_sig, _ = ReservaClase.objects.get_or_create(usuario=siguiente.usuario, clase=clase)
            res_sig.estado = 'CONFIRMADA'
            res_sig.save()
            siguiente.promovido = True
            siguiente.save()
            msg_espera = f"Cupo transferido automáticamente a {siguiente.usuario.username} (Waitlist FIFO)."

        return Response({'mensaje': 'Reserva cancelada correctamente.', 'promocion_espera': msg_espera}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='cancelar-espera')
    @transaction.atomic
    def cancelar_espera(self, request, pk=None):
        """Permite al socio salirse voluntariamente de la lista de espera."""
        clase = self.get_object()
        espera = ListaEspera.objects.filter(usuario=request.user, clase=clase, promovido=False).first()
        if not espera:
            return Response({'error': 'No estás en la lista de espera de esta clase.'}, status=status.HTTP_404_NOT_FOUND)
        espera.delete()
        return Response({'mensaje': f'Saliste de la lista de espera de "{clase.nombre}".'})

    @action(detail=True, methods=['post'], url_path='asistencia-manual')
    @transaction.atomic
    def asistencia_manual(self, request, pk=None):
        if not (request.user.is_authenticated and (request.user.rol in ['INSTRUCTOR', 'COORDINADOR', 'ADMINISTRADOR'] or request.user.is_superuser)):
            return Response({'error': 'Acceso no autorizado.'}, status=status.HTTP_403_FORBIDDEN)

        clase = self.get_object()
        usuario_id = request.data.get('usuario_id')
        reserva = ReservaClase.objects.filter(clase=clase, usuario_id=usuario_id).first()
        if not reserva:
            return Response({'error': 'Reserva no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        reserva.estado = 'ASISTIO'
        reserva.save()
        return Response({'mensaje': f'Asistencia manual acreditada para {reserva.usuario.get_full_name() or reserva.usuario.username}.'})

# ==============================================================================
# 4. TORNIQUETE QR: NORMALIZACIÓN, REGLAS Y PASE EXCEPCIONAL
# ==============================================================================
class ValidarAccesoQRView(APIView):
    def post(self, request):
        procesar_reglas_automaticas()
        codigo_qr = request.data.get('codigo_qr', '').strip().upper()
        rut_raw = request.data.get('rut', '').strip()
        tipo = request.data.get('tipo', 'ENTRADA').upper()
        es_excepcion = bool(request.data.get('es_excepcion', False))

        socio = None
        if codigo_qr:
            socio = Usuario.objects.filter(codigo_qr__iexact=codigo_qr).first()
        elif rut_raw:
            rut_limpio = rut_raw.replace('.', '').replace('-', '').strip().upper()
            for u in Usuario.objects.exclude(rut__isnull=True).exclude(rut=''):
                if u.rut.replace('.', '').replace('-', '').strip().upper() == rut_limpio:
                    socio = u
                    break

        if not socio:
            return Response({'estado': 'DENEGADO', 'mensaje': 'Identificador (QR o RUT) no reconocido en el sistema.'}, status=status.HTTP_404_NOT_FOUND)

        if es_excepcion and es_coordinador_o_admin(request.user):
            motivo_excep = f"Pase Excepcional / Cortesía autorizado por {request.user.username}"
            RegistroAccesoQR.objects.create(usuario=socio, tipo=tipo, estado='PERMITIDO', motivo=motivo_excep)
            return Response({
                'estado': 'PERMITIDO', 'tipo': tipo,
                'socio': socio.get_full_name() or socio.username,
                'rut': socio.rut or '-', 'codigo_qr': socio.codigo_qr,
                'plan': 'Cortesía / Excepción Operativa',
                'vence': 'Autorizado por Coordinador',
                'mensaje': f'Acceso Excepcional Aprobado. Registrado bajo firma de {request.user.username}.'
            }, status=status.HTTP_200_OK)

        if not socio.is_active:
            RegistroAccesoQR.objects.create(usuario=socio, tipo=tipo, estado='DENEGADO', motivo='Cuenta Desactivada')
            return Response({
                'estado': 'DENEGADO', 'tipo': tipo,
                'socio': socio.get_full_name() or socio.username,
                'rut': socio.rut or '-', 'codigo_qr': socio.codigo_qr,
                'mensaje': 'Acceso Bloqueado: Cuenta inactiva o suspendida.'
            }, status=status.HTTP_403_FORBIDDEN)

        if tipo == 'SALIDA':
            RegistroAccesoQR.objects.create(usuario=socio, tipo='SALIDA', estado='PERMITIDO', motivo='Salida normal')
            return Response({
                'estado': 'PERMITIDO', 'tipo': 'SALIDA',
                'socio': socio.get_full_name() or socio.username,
                'rut': socio.rut or '-', 'codigo_qr': socio.codigo_qr,
                'mensaje': 'Salida registrada. ¡Hasta pronto!'
            }, status=status.HTTP_200_OK)

        hoy = timezone.now().date()
        memb_activa = socio.membresias.filter(estado='ACTIVA', fecha_inicio__lte=hoy, fecha_fin__gte=hoy).first()

        if not memb_activa:
            m_congelada = socio.membresias.filter(estado='CONGELADA').first()
            m_vencida = socio.membresias.filter(estado='VENCIDA').first()
            motivo = 'Membresía Congelada' if m_congelada else ('Membresía Vencida' if m_vencida else 'Sin membresía activa')

            RegistroAccesoQR.objects.create(usuario=socio, tipo='ENTRADA', estado='DENEGADO', motivo=motivo)
            return Response({
                'estado': 'DENEGADO', 'tipo': 'ENTRADA',
                'socio': socio.get_full_name() or socio.username,
                'rut': socio.rut or '-', 'codigo_qr': socio.codigo_qr,
                'motivo': motivo, 'mensaje': f'Acceso Bloqueado: {motivo}'
            }, status=status.HTTP_403_FORBIDDEN)

        plan = memb_activa.plan
        hora_actual = timezone.localtime().time()

        if plan.categoria == 'MANANA' and hora_actual > time(12, 0):
            motivo = f'Plan Mañana AM restringido: Válido de 06:00 a 12:00 hrs. (Hora actual: {hora_actual.strftime("%H:%M")})'
            RegistroAccesoQR.objects.create(usuario=socio, tipo='ENTRADA', estado='DENEGADO', motivo=motivo)
            return Response({
                'estado': 'DENEGADO', 'tipo': 'ENTRADA',
                'socio': socio.get_full_name() or socio.username,
                'rut': socio.rut or '-', 'codigo_qr': socio.codigo_qr,
                'plan': plan.nombre, 'motivo': motivo, 'mensaje': f'Acceso Denegado: {motivo}'
            }, status=status.HTTP_403_FORBIDDEN)

        elif plan.categoria == 'TARDE' and hora_actual < time(12, 1):
            motivo = f'Plan Tarde PM restringido: Válido de 12:01 a 23:00 hrs. (Hora actual: {hora_actual.strftime("%H:%M")})'
            RegistroAccesoQR.objects.create(usuario=socio, tipo='ENTRADA', estado='DENEGADO', motivo=motivo)
            return Response({
                'estado': 'DENEGADO', 'tipo': 'ENTRADA',
                'socio': socio.get_full_name() or socio.username,
                'rut': socio.rut or '-', 'codigo_qr': socio.codigo_qr,
                'plan': plan.nombre, 'motivo': motivo, 'mensaje': f'Acceso Denegado: {motivo}'
            }, status=status.HTTP_403_FORBIDDEN)

        ahora = timezone.now()
        reserva_inminente = ReservaClase.objects.filter(
            usuario=socio, estado='CONFIRMADA', clase__fecha_hora__range=(ahora - timedelta(minutes=15), ahora + timedelta(minutes=60))
        ).first()

        detalle_clase = ""
        if reserva_inminente:
            reserva_inminente.estado = 'ASISTIO'
            reserva_inminente.save()
            prof_nom = reserva_inminente.clase.instructor.get_full_name() if reserva_inminente.clase.instructor else "Profesor"
            detalle_clase = f" • Asistencia confirmada a: {reserva_inminente.clase.nombre} (con {prof_nom})"

        metodo_ingreso = "Validación Manual por RUT" if rut_raw and not codigo_qr else "Lector QR"
        RegistroAccesoQR.objects.create(
            usuario=socio, tipo='ENTRADA', estado='PERMITIDO',
            motivo=f'{metodo_ingreso} - Plan {plan.nombre}{detalle_clase}'
        )

        return Response({
            'estado': 'PERMITIDO', 'tipo': 'ENTRADA',
            'socio': socio.get_full_name() or socio.username,
            'rut': socio.rut or '-', 'codigo_qr': socio.codigo_qr,
            'plan': plan.nombre, 'vence': memb_activa.fecha_fin.strftime('%d/%m/%Y'),
            'clase_info': detalle_clase,
            'mensaje': f'Acceso Autorizado. Torniquete liberado.{detalle_clase}'
        }, status=status.HTTP_200_OK)


class DashboardAforoView(APIView):
    def get(self, request):
        procesar_reglas_automaticas()
        hoy = timezone.now().date()
        capacidad_maxima = 80
        entradas_hoy = RegistroAccesoQR.objects.filter(tipo='ENTRADA', estado='PERMITIDO', fecha_hora__date=hoy).count()
        salidas_hoy = RegistroAccesoQR.objects.filter(tipo='SALIDA', estado='PERMITIDO', fecha_hora__date=hoy).count()
        aforo_actual = max(0, entradas_hoy - salidas_hoy)
        porcentaje_aforo = round((aforo_actual / capacidad_maxima) * 100, 1)

        socios_activos = Membresia.objects.filter(estado='ACTIVA', fecha_fin__gte=hoy).count()
        ingresos_mes = Pago.objects.aggregate(total=Sum('monto'))['total'] or 0
        total_espera = ListaEspera.objects.filter(promovido=False).count()

        ultimos = RegistroAccesoQR.objects.select_related('usuario').order_by('-fecha_hora')[:8]
        historial = []
        for reg in ultimos:
            historial.append({
                'usuario_username': reg.usuario.username,
                'usuario_nombre': reg.usuario.get_full_name() or reg.usuario.username,
                'usuario_rut': reg.usuario.rut or '-',
                'codigo_qr': reg.usuario.codigo_qr,
                'tipo': reg.tipo, 'estado': reg.estado, 'motivo': reg.motivo,
                'hora_ms': reg.fecha_hora.strftime('%H:%M:%S'),
                'avatar': f"https://api.dicebear.com/7.x/avataaars/svg?seed={reg.usuario.username}"
            })

        clases_data = []
        for c in ClaseGrupal.objects.all().order_by('fecha_hora'):
            clases_data.append({
                'id': c.id, 'nombre': c.nombre, 'descripcion': c.descripcion,
                'disciplina': c.disciplina.nombre if c.disciplina else 'General',
                'sala': c.sala.nombre if c.sala else 'Por Asignar',
                'instructor': c.instructor.get_full_name() if c.instructor else 'Sin Asignar',
                'dia_semana': c.dia_semana_nombre,
                'hora': c.fecha_hora.strftime('%d/%m %H:%M') if c.fecha_hora else 'Sin fecha',
                'ocupados': c.cupos_ocupados, 'maximo': c.cupo_maximo,
                'disponibles': c.cupos_disponibles, 'estado': c.estado,
                'motivo_suspension': c.motivo_suspension,
                'en_cola': c.en_espera.filter(promovido=False).count()
            })

        disciplinas_stats = Disciplina.objects.annotate(
            total_clases=Count('clases')
        ).values('nombre', 'total_clases')

        return Response({
            'capacidad_maxima': capacidad_maxima,
            'aforo_actual': aforo_actual,
            'porcentaje_aforo': porcentaje_aforo,
            'entradas_hoy': entradas_hoy,
            'salidas_hoy': salidas_hoy,
            'socios_activos': socios_activos,
            'ingresos_mes': ingresos_mes,
            'total_espera': total_espera,
            'ultimos_accesos': historial,
            'clases_hoy': clases_data,
            'chart_disciplinas': list(disciplinas_stats)
        })

# ==============================================================================
# 5. REPORTES CSV (ADMINISTRADOR)
# ==============================================================================
@login_required(login_url='login')
def exportar_socios_csv(request):
    if not es_administrador(request.user):
        return HttpResponse('Acceso no autorizado.', status=403)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="nomina_socios_fitlife.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Username', 'Nombre Completo', 'RUT', 'Email', 'Plan Actual', 'Estado Membresia', 'Vencimiento'])

    for s in Usuario.objects.filter(rol='SOCIO').prefetch_related('membresias__plan'):
        m = s.membresias.first()
        writer.writerow([
            s.id, s.username, s.get_full_name() or s.username, s.rut or '-', s.email or '-',
            m.plan.nombre if m else 'Sin Plan', m.estado if m else 'N/A',
            m.fecha_fin.strftime('%d/%m/%Y') if m else '-'
        ])
    return response


@login_required(login_url='login')
def exportar_recaudacion_csv(request):
    if not es_administrador(request.user):
        return HttpResponse('Acceso no autorizado.', status=403)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="recaudacion_fitlife.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID Pago', 'Socio', 'RUT', 'Plan', 'Monto (CLP)', 'Metodo', 'Fecha de Pago'])

    for p in Pago.objects.select_related('membresia__usuario', 'membresia__plan').order_by('-fecha_pago'):
        writer.writerow([
            p.id, p.membresia.usuario.get_full_name() or p.membresia.usuario.username,
            p.membresia.usuario.rut or '-', p.membresia.plan.nombre,
            p.monto, p.metodo, p.fecha_pago.strftime('%d/%m/%Y %H:%M')
        ])
    return response


@login_required(login_url='login')
def exportar_asistencias_csv(request):
    if not es_administrador(request.user):
        return HttpResponse('Acceso no autorizado.', status=403)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="auditoria_torniquetes_fitlife.csv"'
    writer = csv.writer(response)
    writer.writerow(['Fecha y Hora', 'Socio', 'RUT', 'Sentido', 'Resultado', 'Detalle'])

    for reg in RegistroAccesoQR.objects.select_related('usuario').order_by('-fecha_hora')[:500]:
        writer.writerow([
            reg.fecha_hora.strftime('%d/%m/%Y %H:%M:%S'),
            reg.usuario.get_full_name() or reg.usuario.username,
            reg.usuario.rut or '-', reg.tipo, reg.estado, reg.motivo
        ])
    return response

# ==============================================================================
# 6. PORTALES: SOCIO (AUTOSERVICIO COMPLETO), DOCENTE Y DASHBOARD
# ==============================================================================
@login_required(login_url='login')
def mi_membresia_view(request):
    """Portal exclusivo del Socio: credencial digital, cálculo de vencimiento y lista de espera."""
    hoy = timezone.now().date()
    
    # Membresía más reciente del cliente
    membresia = request.user.membresias.order_by('-id').first()
    
    # Cálculo de días restantes y alerta de vencimiento
    dias_restantes = 0
    alerta_por_vencer = False
    if membresia and membresia.estado == 'ACTIVA':
        dias_restantes = (membresia.fecha_fin - hoy).days
        if 0 <= dias_restantes <= 3:
            alerta_por_vencer = True

    # Entrenamientos realizados este mes (auditoría de hábito)
    asistencias_mes = RegistroAccesoQR.objects.filter(
        usuario=request.user, tipo='ENTRADA', estado='PERMITIDO', fecha_hora__month=hoy.month, fecha_hora__year=hoy.year
    ).count()

    # Historial de pagos
    historial_pagos = Pago.objects.filter(membresia__usuario=request.user).order_by('-fecha_pago')

    # Reservas de clases (ordenadas por fecha de clase descendente)
    reservas = request.user.reservas.select_related('clase__disciplina', 'clase__sala', 'clase__instructor').order_by('-clase__fecha_hora')

    # Listas de espera activas con cálculo exacto de posición FIFO
    esperas_raw = request.user.esperas.filter(promovido=False).select_related('clase__disciplina', 'clase__sala')
    esperas_con_posicion = []
    for esp in esperas_raw:
        pos = ListaEspera.objects.filter(
            clase=esp.clase, promovido=False, fecha_ingreso__lte=esp.fecha_ingreso
        ).count()
        esperas_con_posicion.append({
            'objeto': esp,
            'posicion': pos
        })

    # Últimos accesos por el torniquete
    historial_accesos = RegistroAccesoQR.objects.filter(usuario=request.user).order_by('-fecha_hora')[:10]

    return render(request, 'mi_membresia.html', {
        'membresia': membresia,
        'dias_restantes': dias_restantes,
        'alerta_por_vencer': alerta_por_vencer,
        'asistencias_mes': asistencias_mes,
        'pagos': historial_pagos,
        'reservas': reservas,
        'esperas': esperas_con_posicion,
        'historial_accesos': historial_accesos,
        'hoy': hoy
    })


@login_required(login_url='login')
def instructor_view(request):
    if request.user.rol != 'INSTRUCTOR' and not request.user.is_superuser:
        return redirect('home')

    hoy = timezone.now().date()
    clases_qs = ClaseGrupal.objects.filter(instructor=request.user).prefetch_related(
        'reservas__usuario', 'sala', 'disciplina'
    ).order_by('fecha_hora')

    total_clases = clases_qs.count()
    clases_hoy_count = 0
    alumnos_confirmados_hoy = 0
    alumnos_asistidos_hoy = 0

    for c in clases_qs:
        if c.fecha_hora and c.fecha_hora.date() == hoy:
            clases_hoy_count += 1
            alumnos_confirmados_hoy += c.reservas.filter(estado__in=['CONFIRMADA', 'ASISTIO']).count()
            alumnos_asistidos_hoy += c.reservas.filter(estado='ASISTIO').count()

    return render(request, 'instructor.html', {
        'clases': clases_qs,
        'total_clases': total_clases,
        'clases_hoy_count': clases_hoy_count,
        'alumnos_confirmados_hoy': alumnos_confirmados_hoy,
        'alumnos_asistidos_hoy': alumnos_asistidos_hoy,
        'hoy_str': hoy.strftime('%d/%m/%Y')
    })


@login_required(login_url='login')
def dashboard_view(request):
    if request.user.rol not in ['ADMINISTRADOR', 'COORDINADOR'] and not request.user.is_superuser:
        return redirect('home')

    hoy = timezone.now().date()
    usuarios = Usuario.objects.all().order_by('-id')
    profesores = Usuario.objects.filter(rol='INSTRUCTOR')
    salas = Sala.objects.all()
    disciplinas = Disciplina.objects.all()
    planes = Plan.objects.all().order_by('precio')
    clases = ClaseGrupal.objects.all().select_related('disciplina', 'sala', 'instructor').prefetch_related('en_espera__usuario').order_by('fecha_hora')

    capacidad_maxima = 80
    entradas_hoy = RegistroAccesoQR.objects.filter(tipo='ENTRADA', estado='PERMITIDO', fecha_hora__date=hoy).count()
    salidas_hoy = RegistroAccesoQR.objects.filter(tipo='SALIDA', estado='PERMITIDO', fecha_hora__date=hoy).count()
    aforo_actual = max(0, entradas_hoy - salidas_hoy)
    porcentaje_aforo = round((aforo_actual / capacidad_maxima) * 100, 1) if capacidad_maxima > 0 else 0
    total_espera = ListaEspera.objects.filter(promovido=False).count()
    ultimos_accesos = RegistroAccesoQR.objects.select_related('usuario').order_by('-fecha_hora')[:8]

    kpi_recaudacion_total = Pago.objects.aggregate(total=Sum('monto'))['total'] or 0
    kpi_socios_activos = Membresia.objects.filter(estado='ACTIVA', fecha_fin__gte=hoy).count()
    kpi_vencen_7_dias = Membresia.objects.filter(estado='ACTIVA', fecha_fin__range=(hoy, hoy + timedelta(days=7))).count()
    kpi_total_capacidad = salas.aggregate(cap=Sum('capacidad_maxima'))['cap'] or 0

    return render(request, 'dashboard.html', {
        'usuarios': usuarios,
        'profesores': profesores,
        'salas': salas,
        'disciplinas': disciplinas,
        'planes': planes,
        'clases': clases,
        'aforo_actual': aforo_actual,
        'capacidad_maxima': capacidad_maxima,
        'porcentaje_aforo': porcentaje_aforo,
        'entradas_hoy': entradas_hoy,
        'salidas_hoy': salidas_hoy,
        'total_espera': total_espera,
        'ultimos_accesos': ultimos_accesos,
        'kpi_recaudacion_total': kpi_recaudacion_total,
        'kpi_socios_activos': kpi_socios_activos,
        'kpi_vencen_7_dias': kpi_vencen_7_dias,
        'kpi_total_capacidad': kpi_total_capacidad,
    })


def home_view(request):
    hoy = timezone.now().date()
    capacidad = 80
    entradas = RegistroAccesoQR.objects.filter(tipo='ENTRADA', estado='PERMITIDO', fecha_hora__date=hoy).count()
    salidas = RegistroAccesoQR.objects.filter(tipo='SALIDA', estado='PERMITIDO', fecha_hora__date=hoy).count()
    aforo = max(0, entradas - salidas)
    porcentaje = round((aforo / capacidad) * 100, 1) if capacidad > 0 else 0

    if porcentaje < 45:
        nivel_trafico = 'Bajo'
        badge_clase = 'bg-emerald-100 text-emerald-800 border-emerald-200'
        mensaje_trafico = 'Tráfico Bajo: Momento ideal para entrenar sin esperas de máquinas.'
    elif porcentaje < 80:
        nivel_trafico = 'Moderado'
        badge_clase = 'bg-amber-100 text-amber-800 border-amber-200'
        mensaje_trafico = 'Tráfico Moderado: Flujo constante de socios en salas.'
    else:
        nivel_trafico = 'Alto'
        badge_clase = 'bg-rose-100 text-rose-800 border-rose-200'
        mensaje_trafico = 'Horario Punta: Alta concurrencia en salas y máquinas.'

    planes = Plan.objects.all().order_by('precio')
    profesores = Usuario.objects.filter(rol='INSTRUCTOR')
    disciplinas = Disciplina.objects.all()

    return render(request, 'index.html', {
        'aforo': aforo,
        'capacidad': capacidad,
        'porcentaje': porcentaje,
        'nivel_trafico': nivel_trafico,
        'badge_clase': badge_clase,
        'mensaje_trafico': mensaje_trafico,
        'planes': planes,
        'profesores': profesores,
        'disciplinas': disciplinas,
        'total_clases': ClaseGrupal.objects.filter(estado='COORDINADA').count(),
    })

def aforo_view(request):
    return render(request, 'aforo.html')

def clases_view(request):
    clases = ClaseGrupal.objects.all().select_related('disciplina', 'instructor', 'sala').order_by('fecha_hora')
    disciplinas = Disciplina.objects.all()
    profesores = Usuario.objects.filter(rol='INSTRUCTOR')
    return render(request, 'clases.html', {
        'clases': clases, 'disciplinas': disciplinas, 'profesores': profesores
    })

def planes_view(request):
    planes = Plan.objects.all().order_by('precio')
    membresia_activa = request.user.membresias.filter(estado='ACTIVA').first() if request.user.is_authenticated else None
    return render(request, 'planes.html', {'planes': planes, 'membresia_activa': membresia_activa})

def login_view(request):
    if request.user.is_authenticated:
        if request.user.rol == 'INSTRUCTOR':
            return redirect('portal_instructor')
        if request.user.rol in ['ADMINISTRADOR', 'COORDINADOR'] or request.user.is_superuser:
            return redirect('dashboard')
        return redirect('home')

    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user:
            login(request, user)
            if user.rol == 'INSTRUCTOR':
                return redirect('portal_instructor')
            if user.rol in ['ADMINISTRADOR', 'COORDINADOR'] or user.is_superuser:
                return redirect('dashboard')
            return redirect('home')
        return render(request, 'login.html', {'error': 'Credenciales no válidas.'})
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('home')

def error_404_view(request, exception=None, path_invalido=None):
    ruta = path_invalido if path_invalido is not None else request.path.lstrip('/')
    return render(request, '404.html', {'ruta': ruta}, status=404)
