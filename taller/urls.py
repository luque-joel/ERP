from django.urls import path
from . import views

app_name = 'taller'

urlpatterns = [
    # Autenticación y Ruteo de Roles
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.dashboard_router, name='home_redirect'),

    # Dashboard Principal (Gerencia)
    path('', views.dashboard, name='dashboard'),
    
    # Órdenes de Trabajo (Taller - Operativa)
    path('ordenes/', views.orden_list, name='orden_list'),
    path('ordenes/<int:pk>/', views.orden_detail, name='orden_detail'),
    path('ordenes/<int:pk>/estado/', views.orden_update_status, name='orden_update_status'),
    path('ordenes/nueva/', views.orden_create, name='orden_create'),
    path('ordenes/<int:pk>/agregar-repuesto/', views.orden_agregar_repuesto, name='orden_agregar_repuesto'),
    
    # Bodega (Inventario y Kardex)
    path('repuestos/', views.repuesto_list, name='repuesto_list'),
    path('repuestos/movimiento/', views.bodega_movimiento, name='bodega_movimiento'),
    
    # Ventas (POS y Facturación SRI)
    path('pos/', views.pos_console, name='pos_console'),
    path('pos/facturar/', views.pos_facturar, name='pos_facturar'),
    path('pos/facturas/', views.factura_list, name='factura_list'),
    path('pos/facturas/<int:pk>/pdf/', views.factura_pdf, name='factura_pdf'),
    
    # Talento Humano (RRHH)
    path('rrhh/', views.rrhh_console, name='rrhh_console'),
    path('rrhh/mecanico/nuevo/', views.mecanico_create, name='mecanico_create'),
    path('rrhh/horario/nuevo/', views.horario_create, name='horario_create'),
    path('rrhh/nomina/nueva/', views.nomina_create, name='nomina_create'),
    
    # IA Analítica
    path('ia/recomendar/', views.generar_ia_recomendacion, name='generar_ia_recomendacion'),

    # Reportes Automatizados y Exportaciones (Gerencia & Ventas)
    path('reportes/', views.reportes_dashboard, name='reportes'),
    path('reportes/ventas/pdf/', views.export_ventas_pdf, name='export_ventas_pdf'),
    path('reportes/ventas/excel/', views.export_ventas_excel, name='export_ventas_excel'),
    path('reportes/compras/pdf/', views.export_compras_pdf, name='export_compras_pdf'),
    path('reportes/compras/excel/', views.export_compras_excel, name='export_compras_excel'),
]
