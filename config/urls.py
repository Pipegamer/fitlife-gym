from django.contrib import admin
from django.urls import path, re_path, include
from api.views import (
    home_view, aforo_view, clases_view, planes_view, mi_membresia_view,
    dashboard_view, instructor_view, login_view, logout_view, error_404_view,
    exportar_socios_csv, exportar_recaudacion_csv, exportar_asistencias_csv
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Vistas Frontend Principales
    path('', home_view, name='home'),
    path('aforo/', aforo_view, name='aforo'),
    path('clases/', clases_view, name='clases'),
    path('planes/', planes_view, name='planes'),
    path('mi-membresia/', mi_membresia_view, name='mi_membresia'),

    # Portal Instructor y Gestión
    path('instructor/', instructor_view, name='portal_instructor'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    # Exportación de Reportes CSV (Admin)
    path('reportes/socios-csv/', exportar_socios_csv, name='reporte_socios_csv'),
    path('reportes/recaudacion-csv/', exportar_recaudacion_csv, name='reporte_recaudacion_csv'),
    path('reportes/asistencias-csv/', exportar_asistencias_csv, name='reporte_asistencias_csv'),

    # API REST
    path('api/', include('api.urls')),

    # Blindaje Catch-All 404
    re_path(r'^(?P<path_invalido>.*)$', error_404_view, name='catch_all_fallback'),
]
