from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import (
    Usuario, Plan, Membresia, Pago, 
    ClaseGrupal, ReservaClase, ListaEspera, RegistroAccesoQR
)

@admin.register(Usuario)
class UsuarioPersonalizadoAdmin(UserAdmin):
    list_display = ('username', 'rut', 'email', 'badge_rol', 'codigo_qr', 'is_active')
    list_filter = ('rol', 'is_active')
    search_fields = ('username', 'rut', 'email', 'codigo_qr')
    fieldsets = UserAdmin.fieldsets + (
        ('Datos FitLife', {'fields': ('rol', 'rut', 'telefono', 'codigo_qr')}),
    )

    def badge_rol(self, obj):
        colores = {'SOCIO': '#0d6efd', 'INSTRUCTOR': '#198754', 'ADMINISTRADOR': '#dc3545'}
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            colores.get(obj.rol, '#6c757d'), obj.get_rol_display()
        )
    badge_rol.short_description = 'Rol del Sistema'


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_formateado', 'duracion_dias')
    search_fields = ('nombre',)

    def precio_formateado(self, obj):
        return f"${obj.precio:,.0f} CLP"
    precio_formateado.short_description = 'Tarifa'


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('id', 'membresia_socio', 'monto_formateado', 'metodo', 'fecha_pago')
    list_filter = ('metodo', 'fecha_pago')
    search_fields = ('membresia__usuario__username', 'membresia__usuario__rut')

    def membresia_socio(self, obj):
        return f"{obj.membresia.usuario.username} ({obj.membresia.plan.nombre})"
    membresia_socio.short_description = 'Socio / Plan'

    def monto_formateado(self, obj):
        return f"${obj.monto:,.0f} CLP"
    monto_formateado.short_description = 'Monto Cancelado'


@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plan', 'fecha_inicio', 'fecha_fin', 'badge_estado', 'vigencia_calculada')
    list_filter = ('estado', 'plan', 'fecha_inicio')
    search_fields = ('usuario__username', 'usuario__rut', 'plan__nombre')
    actions = ['congelar_membresias', 'activar_membresias']

    def badge_estado(self, obj):
        colores = {
            'ACTIVA': '#28a745',
            'VENCIDA': '#dc3545',
            'CONGELADA': '#ffc107; color: #212529',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 11px;">{}</span>',
            colores.get(obj.estado, '#6c757d'), obj.get_estado_display()
        )
    badge_estado.short_description = 'Estado Membresía'

    def vigencia_calculada(self, obj):
        if obj.esta_vigente():
            return format_html('<span style="color: #28a745; font-weight: bold;">✔ Válida Hoy</span>')
        return format_html('<span style="color: #dc3545; font-weight: bold;">✖ No Válida</span>')
    vigencia_calculada.short_description = 'Acceso Físico'

    @admin.action(description='Congelar membresías seleccionadas')
    def congelar_membresias(self, request, queryset):
        queryset.update(estado='CONGELADA')

    @admin.action(description='Reactivar membresías seleccionadas')
    def activar_membresias(self, request, queryset):
        queryset.update(estado='ACTIVA')


@admin.register(ClaseGrupal)
class ClaseGrupalAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'instructor', 'fecha_hora', 'sala', 'estado_cupos')
    list_filter = ('nombre', 'sala', 'fecha_hora')
    search_fields = ('nombre', 'instructor__username', 'sala')

    def estado_cupos(self, obj):
        ocupados = obj.cupos_ocupados
        maximo = obj.cupo_maximo
        color = "#28a745" if ocupados < maximo else "#dc3545"
        return format_html('<b style="color: {};">{}/{}</b> reservados', color, ocupados, maximo)
    estado_cupos.short_description = 'Ocupación de Cupos'


@admin.register(ReservaClase)
class ReservaClaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'clase', 'badge_estado', 'fecha_reserva')
    list_filter = ('estado', 'clase__nombre')
    search_fields = ('usuario__username', 'clase__nombre')

    def badge_estado(self, obj):
        colores = {'CONFIRMADA': '#0d6efd', 'CANCELADA': '#6c757d', 'ASISTIO': '#198754'}
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px;">{}</span>', colores.get(obj.estado, '#000'), obj.estado)
    badge_estado.short_description = 'Estado Reserva'


@admin.register(ListaEspera)
class ListaEsperaAdmin(admin.ModelAdmin):
    list_display = ('id', 'clase', 'usuario', 'fecha_ingreso', 'promovido_badge')
    list_filter = ('promovido', 'clase__nombre')
    search_fields = ('usuario__username', 'clase__nombre')

    def promovido_badge(self, obj):
        if obj.promovido:
            return format_html('<span style="color: green; font-weight: bold;">✔ Promovido a Cupo</span>')
        return format_html('<span style="color: orange; font-weight: bold;">⏳ En Espera</span>')
    promovido_badge.short_description = 'Estado Cola'


@admin.register(RegistroAccesoQR)
class RegistroAccesoQRAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'usuario', 'tipo', 'badge_resultado', 'motivo')
    list_filter = ('tipo', 'estado', 'fecha_hora')
    search_fields = ('usuario__username', 'usuario__rut', 'motivo')

    def badge_resultado(self, obj):
        color = '#28a745' if obj.estado == 'PERMITIDO' else '#dc3545'
        return format_html('<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;">{}</span>', color, obj.estado)
    badge_resultado.short_description = 'Resultado de Acceso'
