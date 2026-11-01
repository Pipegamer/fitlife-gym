from rest_framework import serializers
from .models import (
    Usuario, Sala, Disciplina, Plan, Membresia, Pago, 
    ClaseGrupal, ReservaClase, ListaEspera, RegistroAccesoQR
)

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'rol', 'rut', 'telefono', 'especialidad', 'codigo_qr', 'is_active']


class SalaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sala
        fields = '__all__'


class DisciplinaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disciplina
        fields = '__all__'


class PlanSerializer(serializers.ModelSerializer):
    beneficios_lista = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = '__all__'

    def get_beneficios_lista(self, obj):
        return obj.lista_beneficios()


class PagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = '__all__'


class MembresiaSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.get_full_name', read_only=True)
    plan_nombre = serializers.CharField(source='plan.nombre', read_only=True)
    vigente = serializers.BooleanField(source='esta_vigente', read_only=True)

    class Meta:
        model = Membresia
        fields = ['id', 'usuario', 'usuario_nombre', 'plan', 'plan_nombre', 'fecha_inicio', 'fecha_fin', 'estado', 'vigente']


class ClaseGrupalSerializer(serializers.ModelSerializer):
    disciplina_nombre = serializers.CharField(source='disciplina.nombre', read_only=True, default='General')
    disciplina_intensidad = serializers.CharField(source='disciplina.intensidad', read_only=True, default='MEDIA')
    sala_nombre = serializers.CharField(source='sala.nombre', read_only=True, default='Por Asignar')
    sala_capacidad = serializers.IntegerField(source='sala.capacidad_maxima', read_only=True, default=0)
    instructor_nombre = serializers.SerializerMethodField()
    dia_semana = serializers.CharField(source='dia_semana_nombre', read_only=True)
    cupos_ocupados = serializers.IntegerField(read_only=True)
    cupos_disponibles = serializers.IntegerField(read_only=True)

    class Meta:
        model = ClaseGrupal
        fields = [
            'id', 'nombre', 'descripcion', 'disciplina', 'disciplina_nombre', 'disciplina_intensidad',
            'instructor', 'instructor_nombre', 'sala', 'sala_nombre', 'sala_capacidad',
            'fecha_hora', 'dia_semana', 'cupo_maximo', 'estado', 'motivo_suspension',
            'cupos_ocupados', 'cupos_disponibles'
        ]

    def get_instructor_nombre(self, obj):
        if obj.instructor:
            return obj.instructor.get_full_name() or obj.instructor.username
        return 'Por Asignar'


class ReservaClaseSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source='usuario.username', read_only=True)
    clase_nombre = serializers.CharField(source='clase.nombre', read_only=True)

    class Meta:
        model = ReservaClase
        fields = ['id', 'usuario', 'usuario_username', 'clase', 'clase_nombre', 'estado', 'fecha_reserva']


class ListaEsperaSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = ListaEspera
        fields = ['id', 'usuario', 'usuario_username', 'clase', 'fecha_ingreso', 'promovido']


class RegistroAccesoQRSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = RegistroAccesoQR
        fields = ['id', 'usuario', 'usuario_username', 'tipo', 'estado', 'motivo', 'fecha_hora']
