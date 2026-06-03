from django.contrib import admin
from django.utils.html import format_html
from django.db.models import F
from .models import (
    Cliente, Vehiculo, ModeloCompatibilidad, 
    Repuesto, Mecanico, OrdenTrabajo, DetalleRepuestoOrden,
    Empleado, Horario, Nomina, Proveedor, CompraProveedor,
    DetalleCompraProveedor, MovimientoInventario, Factura,
    DetalleFactura, MetodoPago, RecomendacionIA
)

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cedula_ruc', 'telefono', 'email', 'direccion_corta')
    search_fields = ('nombre', 'cedula_ruc', 'telefono')
    list_per_page = 20

    def direccion_corta(self, obj):
        if obj.direccion and len(obj.direccion) > 40:
            return obj.direccion[:37] + "..."
        return obj.direccion or "-"
    direccion_corta.short_description = "Dirección"

class VehiculoInline(admin.TabularInline):
    model = Vehiculo
    extra = 1

@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ('tipo_icon', 'marca', 'modelo', 'anio', 'placa_styled', 'cliente', 'numero_motor')
    list_filter = ('tipo', 'marca')
    search_fields = ('placa', 'marca', 'modelo', 'cliente__nombre', 'cliente__cedula_ruc')
    raw_id_fields = ('cliente',)
    list_per_page = 20

    def tipo_icon(self, obj):
        if obj.tipo == 'MOTO':
            return format_html('🏍️ <strong>Motocicleta</strong>')
        return format_html('🛺 <strong>Tricimoto</strong>')
    tipo_icon.short_description = "Tipo"

    def placa_styled(self, obj):
        if obj.placa:
            return format_html('<code style="background-color: #f8f9fa; border: 1px solid #ccc; padding: 2px 6px; border-radius: 4px; font-weight: bold;">{}</code>', obj.placa)
        return format_html('<span style="color: #999; font-style: italic;">Sin Placa</span>')
    placa_styled.short_description = "Placa"

@admin.register(ModeloCompatibilidad)
class ModeloCompatibilidadAdmin(admin.ModelAdmin):
    list_display = ('marca', 'modelo')
    search_fields = ('marca', 'modelo')
    list_per_page = 30

@admin.register(Repuesto)
class RepuestoAdmin(admin.ModelAdmin):
    list_display = ('sku_code', 'nombre', 'categoria_tag', 'marca', 'precio_compra_styled', 'precio_venta_styled', 'stock_status', 'ubicacion')
    list_filter = ('categoria', 'aplica_iva', 'marca')
    search_fields = ('sku', 'nombre', 'marca', 'compatibilidades__modelo', 'compatibilidades__marca')
    filter_horizontal = ('compatibilidades',)
    list_per_page = 25

    def sku_code(self, obj):
        return format_html('<span style="font-family: monospace; font-weight: bold; color: #d63384;">{}</span>', obj.sku)
    sku_code.short_description = "SKU"

    def categoria_tag(self, obj):
        return obj.get_categoria_display()
    categoria_tag.short_description = "Categoría"

    def precio_compra_styled(self, obj):
        return f"${obj.precio_compra}"
    precio_compra_styled.short_description = "P. Compra"

    def precio_venta_styled(self, obj):
        return f"${obj.precio_venta}"
    precio_venta_styled.short_description = "P. Venta (PVP)"

    def stock_status(self, obj):
        if obj.stock <= 0:
            return format_html('<span style="color: #dc3545; font-weight: bold;">⚠️ Agotado (0)</span>')
        elif obj.stock <= obj.stock_minimo:
            return format_html('<span style="color: #ffc107; font-weight: bold;">⚠️ Reorden ({})</span>', obj.stock)
        return format_html('<span style="color: #198754; font-weight: bold;">{}</span>', obj.stock)
    stock_status.short_description = "Stock"

@admin.register(Mecanico)
class MecanicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'estado_pill')
    list_filter = ('estado',)
    search_fields = ('nombre', 'telefono')

    def estado_pill(self, obj):
        if obj.estado == 'DISPONIBLE':
            return format_html('<span style="background-color: #d1e7dd; color: #0f5132; padding: 3px 8px; border-radius: 12px; font-size: 0.85em; font-weight: bold;">Disponible</span>')
        elif obj.estado == 'OCUPADO':
            return format_html('<span style="background-color: #fff3cd; color: #664d03; padding: 3px 8px; border-radius: 12px; font-size: 0.85em; font-weight: bold;">En Reparación</span>')
        return format_html('<span style="background-color: #f8d7da; color: #842029; padding: 3px 8px; border-radius: 12px; font-size: 0.85em; font-weight: bold;">Inactivo</span>')
    estado_pill.short_description = "Estado"

class DetalleRepuestoOrdenInline(admin.TabularInline):
    model = DetalleRepuestoOrden
    extra = 1
    raw_id_fields = ('repuesto',)
    fields = ('repuesto', 'cantidad', 'precio_historico', 'subtotal_styled')
    readonly_fields = ('subtotal_styled',)

    def subtotal_styled(self, obj):
        if obj.id:
            return f"${obj.subtotal:.2f}"
        return "$0.00"
    subtotal_styled.short_description = "Subtotal"

@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ('codigo_orden', 'vehiculo_link', 'mecanico', 'fecha_ingreso_styled', 'estado_badge', 'mano_obra_styled', 'repuestos_styled', 'total_styled')
    list_filter = ('estado', 'mecanico', 'fecha_ingreso', 'vehiculo__tipo')
    search_fields = ('codigo_orden', 'vehiculo__placa', 'vehiculo__marca', 'vehiculo__modelo', 'vehiculo__cliente__nombre')
    raw_id_fields = ('vehiculo', 'mecanico')
    inlines = [DetalleRepuestoOrdenInline]
    list_per_page = 15

    fieldsets = (
        ('Información General', {
            'fields': (('vehiculo', 'mecanico', 'estado'), ('fecha_prometida', 'fecha_entrega'))
        }),
        ('Recepción en Taller', {
            'fields': (('kilometraje', 'nivel_combustible'), 'observaciones_recepcion', 'checklist_json')
        }),
        ('Diagnóstico y Presupuesto', {
            'fields': ('diagnostico', 'mano_obra')
        }),
    )

    def vehiculo_link(self, obj):
        return f"{obj.vehiculo}"
    vehiculo_link.short_description = "Vehículo"

    def fecha_ingreso_styled(self, obj):
        return obj.fecha_ingreso.strftime("%d/%m/%Y %H:%M")
    fecha_ingreso_styled.short_description = "Ingreso"

    def estado_badge(self, obj):
        colors = {
            'PENDIENTE': ('#f8f9fa', '#212529', 'Pendiente'),
            'EN_PROCESO': ('#cfe2ff', '#084298', 'En Reparación'),
            'ESPERANDO_REPUESTOS': ('#fff3cd', '#664d03', 'Falta Repuesto'),
            'TERMINADO': ('#d1e7dd', '#0f5132', 'Terminado'),
            'ENTREGADO': ('#e2e3e5', '#41464b', 'Entregado'),
            'ANULADO': ('#f8d7da', '#842029', 'Anulado'),
        }
        bg, text, label = colors.get(obj.estado, ('#fff', '#000', obj.estado))
        return format_html('<span style="background-color: {}; color: {}; padding: 4px 10px; border-radius: 4px; font-size: 0.9em; font-weight: bold; border: 1px solid rgba(0,0,0,0.1);">{}</span>', bg, text, label)
    estado_badge.short_description = "Estado"

    def mano_obra_styled(self, obj):
        return f"${obj.mano_obra:.2f}"
    mano_obra_styled.short_description = "Mano de Obra"

    def repuestos_styled(self, obj):
        return f"${obj.total_repuestos:.2f}"
    repuestos_styled.short_description = "Repuestos"

    def total_styled(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.total_general)
    total_styled.short_description = "Total Gral."

    def save_formset(self, request, form, formset, change):
        """
        Sobrescribir el guardado de los inlines para descontar automáticamente 
        el stock del repuesto cuando se agrega a una orden terminada o en proceso,
        y registrar el precio histórico de venta del repuesto si no está seteado.
        """
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, DetalleRepuestoOrden):
                # Rellenar precio histórico si no está provisto
                if not instance.precio_historico:
                    instance.precio_historico = instance.repuesto.precio_venta
                
                # Descontar del inventario solo si es una nueva entrada
                if not instance.id:
                    repuesto = instance.repuesto
                    repuesto.stock = F('stock') - instance.cantidad
                    repuesto.save()
                    
                instance.save()
        formset.save_m2m()

@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('user', 'cedula', 'cargo', 'telefono', 'sueldo_base', 'porcentaje_comision', 'activo')
    list_filter = ('cargo', 'activo')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'cedula', 'telefono')

@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('empleado_o_mecanico', 'dia_semana', 'hora_entrada', 'hora_salida')
    list_filter = ('dia_semana',)

    def empleado_o_mecanico(self, obj):
        return obj.empleado if obj.empleado else obj.mecanico
    empleado_o_mecanico.short_description = "Empleado / Mecánico"

@admin.register(Nomina)
class NominaAdmin(admin.ModelAdmin):
    list_display = ('empleado_o_mecanico', 'fecha_inicio', 'fecha_fin', 'sueldo_basico', 'comisiones', 'total_pagar', 'pagado')
    list_filter = ('pagado', 'fecha_fin')

    def empleado_o_mecanico(self, obj):
        return obj.empleado if obj.empleado else obj.mecanico
    empleado_o_mecanico.short_description = "Empleado / Mecánico"

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre_empresa', 'ruc', 'contacto', 'telefono', 'email')
    search_fields = ('nombre_empresa', 'ruc', 'contacto')

class DetalleCompraProveedorInline(admin.TabularInline):
    model = DetalleCompraProveedor
    extra = 1

@admin.register(CompraProveedor)
class CompraProveedorAdmin(admin.ModelAdmin):
    list_display = ('id', 'proveedor', 'fecha_compra', 'documento_referencia', 'total', 'estado')
    list_filter = ('estado', 'fecha_compra')
    inlines = [DetalleCompraProveedorInline]

@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('repuesto', 'tipo', 'cantidad', 'fecha', 'usuario')
    list_filter = ('tipo', 'fecha')

class DetalleFacturaInline(admin.TabularInline):
    model = DetalleFactura
    extra = 1

class MetodoPagoInline(admin.TabularInline):
    model = MetodoPago
    extra = 1

@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ('numero_factura', 'cliente', 'fecha_emision', 'total_pagar', 'estado', 'estado_sri')
    list_filter = ('estado', 'estado_sri', 'ambiente', 'fecha_emision')
    search_fields = ('numero_factura', 'cliente__nombre', 'clave_acceso')
    inlines = [DetalleFacturaInline, MetodoPagoInline]

@admin.register(RecomendacionIA)
class RecomendacionIAAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'titulo', 'fecha_generacion')
    list_filter = ('tipo', 'fecha_generacion')


