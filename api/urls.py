from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UsuarioViewSet, SalaViewSet, DisciplinaViewSet, PlanViewSet,
    MembresiaViewSet, PagoViewSet, ClaseGrupalViewSet,
    ValidarAccesoQRView, DashboardAforoView
)

router = DefaultRouter()
router.register(r'usuarios', UsuarioViewSet, basename='usuarios')
router.register(r'salas', SalaViewSet, basename='salas')
router.register(r'disciplinas', DisciplinaViewSet, basename='disciplinas')
router.register(r'planes', PlanViewSet, basename='planes')
router.register(r'membresias', MembresiaViewSet, basename='membresias')
router.register(r'pagos', PagoViewSet, basename='pagos')
router.register(r'clases', ClaseGrupalViewSet, basename='clases')

urlpatterns = [
    path('acceso-qr/validar/', ValidarAccesoQRView.as_view(), name='validar_acceso_qr'),
    path('aforo/metricas/', DashboardAforoView.as_view(), name='aforo_metricas'),
    path('', include(router.urls)),
]
