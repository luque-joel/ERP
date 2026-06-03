from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from .validators import validar_cedula_ruc_ecuador

class Cliente(models.Model):
    TIPO_IDENTIFICACION_CHOICES = [
        ('04', 'RUC (Persona Natural/Jurídica)'),
        ('05', 'Cédula de Identidad'),
        ('06', 'Pasaporte'),
        ('07', 'Consumidor Final'),
        ('08', 'Identificación del Exterior'),
    ]
    tipo_identificacion = models.CharField("Tipo Identificación SRI", max_length=2, choices=TIPO_IDENTIFICACION_CHOICES, default='05')
    cedula_ruc = models.CharField(
        "Cédula/RUC/Pasaporte", 
        max_length=13, 
        unique=True,
        validators=[validar_cedula_ruc_ecuador],
        help_text="Ingrese los 10 dígitos de la cédula, 13 del RUC o identificación."
    )
    nombre = models.CharField("Nombre o Razón Social", max_length=150)
    telefono = models.CharField("Teléfono", max_length=20, blank=True)
    email = models.EmailField("Correo Electrónico", blank=True)
    direccion = models.TextField("Dirección", blank=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.cedula_ruc})"

class Vehiculo(models.Model):
    TIPO_CHOICES = [
        ('MOTO', 'Motocicleta'),
        ('TRICIMOTO', 'Tricimoto'),
    ]
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='MOTO')
    marca = models.CharField("Marca", max_length=50)
    modelo = models.CharField("Modelo", max_length=50)
    anio = models.IntegerField("Año", blank=True, null=True)
    placa = models.CharField("Placa", max_length=15, unique=True, blank=True, null=True)
    numero_motor = models.CharField("Número de Motor", max_length=50, blank=True, null=True)
    numero_chasis = models.CharField("Número de Chasis (VIN)", max_length=50, blank=True, null=True)
    color = models.CharField("Color", max_length=30, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="vehiculos")

    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
        ordering = ['marca', 'modelo']

    def __str__(self):
        placa_str = self.placa if self.placa else "SIN PLACA"
        return f"{self.get_tipo_display()} - {self.marca} {self.modelo} [{placa_str}]"

class ModeloCompatibilidad(models.Model):
    marca = models.CharField("Marca de Moto/Tricimoto", max_length=50)
    modelo = models.CharField("Modelo de Moto/Tricimoto", max_length=50)

    class Meta:
        verbose_name = "Modelo de Compatibilidad"
        verbose_name_plural = "Modelos de Compatibilidad"
        unique_together = ('marca', 'modelo')
        ordering = ['marca', 'modelo']

    def __str__(self):
        return f"{self.marca} {self.modelo}"

class Repuesto(models.Model):
    CATEGORIA_CHOICES = [
        ('MOTOR', 'Motor y Componentes'),
        ('ELECTRICO', 'Sistema Eléctrico'),
        ('TRANSMISION', 'Transmisión y Embrague'),
        ('SUSPENSION', 'Suspensión y Amortiguadores'),
        ('FRENOS', 'Sistema de Frenos'),
        ('CARROCERIA', 'Chasis, Plásticos y Espejos'),
        ('LLANTAS', 'Llantas y Cámaras'),
        ('ACEITES', 'Aceites y Lubricantes'),
        ('VARIOS', 'Otros / Accesorios'),
    ]
    TARIFA_IVA_CHOICES = [
        ('0', '0% (Exento / No Objeto)'),
        ('2', '15% (Tarifa Estándar de IVA en Ecuador)'),
        ('6', 'No aplica IVA'),
    ]
    sku = models.CharField("Código / SKU (Código Principal SRI)", max_length=50, unique=True)
    tarifa_iva = models.CharField("Tarifa IVA SRI", max_length=2, choices=TARIFA_IVA_CHOICES, default='2')
    nombre = models.CharField("Nombre del Repuesto", max_length=150)
    categoria = models.CharField("Categoría", max_length=20, choices=CATEGORIA_CHOICES)
    marca = models.CharField("Marca del Repuesto", max_length=50, blank=True)
    ubicacion = models.CharField("Ubicación (Percha/Estante)", max_length=50, blank=True, help_text="Ej: Estante B - Fila 3")
    stock = models.IntegerField("Stock Actual", default=0)
    stock_minimo = models.IntegerField("Stock Mínimo (Alerta)", default=5)
    precio_compra = models.DecimalField("Precio de Compra", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    precio_venta = models.DecimalField("Precio de Venta (PVP)", max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    aplica_iva = models.BooleanField("Aplica IVA (Obs.)", default=True)
    compatibilidades = models.ManyToManyField(ModeloCompatibilidad, related_name="repuestos", blank=True, verbose_name="Compatible con")

    class Meta:
        verbose_name = "Repuesto"
        verbose_name_plural = "Repuestos"
        ordering = ['nombre']

    def __str__(self):
        return f"[{self.sku}] {self.nombre} ({self.marca}) - Stock: {self.stock}"

class Mecanico(models.Model):
    ESTADO_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('OCUPADO', 'En reparación'),
        ('INACTIVO', 'No disponible / Ausente'),
    ]
    nombre = models.CharField("Nombre Completo", max_length=100)
    telefono = models.CharField("Teléfono", max_length=20, blank=True)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='DISPONIBLE')

    class Meta:
        verbose_name = "Mecánico"
        verbose_name_plural = "Mecánicos"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.get_estado_display()})"

class OrdenTrabajo(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROCESO', 'En Reparación'),
        ('ESPERANDO_REPUESTOS', 'Esperando Repuestos'),
        ('TERMINADO', 'Trabajo Terminado (Por Entregar)'),
        ('ENTREGADO', 'Entregado y Facturado'),
        ('ANULADO', 'Anulado'),
    ]
    codigo_orden = models.CharField("Nº de Orden", max_length=20, unique=True, editable=False)
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.PROTECT, related_name="ordenes")
    mecanico = models.ForeignKey(Mecanico, on_delete=models.SET_NULL, null=True, blank=True, related_name="ordenes")
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="ordenes_creadas")
    fecha_ingreso = models.DateTimeField("Fecha de Ingreso", auto_now_add=True)
    fecha_prometida = models.DateTimeField("Fecha Prometida de Entrega", blank=True, null=True)
    fecha_entrega = models.DateTimeField("Fecha Real de Entrega", blank=True, null=True)
    facturada = models.BooleanField("Facturada", default=False)
    
    # Recepción y Checklist
    kilometraje = models.IntegerField("Kilometraje", default=0)
    nivel_combustible = models.CharField("Nivel de Gasolina", max_length=20, default="1/4", help_text="Ej: Vacío, 1/4, 1/2, 3/4, Lleno")
    observaciones_recepcion = models.TextField("Falla Reportada / Observaciones", blank=True)
    checklist_json = models.JSONField("Checklist Visual", default=dict, blank=True, help_text="Almacena estado de accesorios y daños físicos.")
    
    # Diagnóstico y Trabajo
    diagnostico = models.TextField("Diagnóstico Técnico", blank=True)
    mano_obra = models.DecimalField("Costo de Mano de Obra", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')

    class Meta:
        verbose_name = "Orden de Trabajo"
        verbose_name_plural = "Órdenes de Trabajo"
        ordering = ['-fecha_ingreso']

    def save(self, *args, **kwargs):
        if not self.codigo_orden:
            # Generación automática de código correlativo: OT-00001
            ultimo = OrdenTrabajo.objects.all().order_by('id').last()
            if not ultimo:
                self.codigo_orden = 'OT-00001'
            else:
                consecutivo = ultimo.id + 1
                self.codigo_orden = f'OT-{consecutivo:05d}'
        super().save(*args, **kwargs)

    @property
    def total_repuestos(self):
        return sum(item.subtotal for item in self.repuestos_utilizados.all())

    @property
    def total_general(self):
        return self.mano_obra + self.total_repuestos

    def __str__(self):
        return f"{self.codigo_orden} - {self.vehiculo} ({self.get_estado_display()})"

class DetalleRepuestoOrden(models.Model):
    orden = models.ForeignKey(OrdenTrabajo, on_delete=models.CASCADE, related_name="repuestos_utilizados")
    repuesto = models.ForeignKey(Repuesto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    precio_historico = models.DecimalField("Precio Cobrado", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Repuesto Utilizado"
        verbose_name_plural = "Repuestos Utilizados"

    @property
    def subtotal(self):
        return self.precio_historico * self.cantidad

    def __str__(self):
        return f"{self.cantidad} x {self.repuesto.nombre} en {self.orden.codigo_orden}"

class Empleado(models.Model):
    CARGO_CHOICES = [
        ('ADMIN_RRHH', 'Talento Humano'),
        ('OPERATIVO_RECEPCION', 'Recepcionista Taller'),
        ('VENDEDOR', 'Vendedor / Cajero'),
        ('BODEGUERO', 'Bodeguero'),
        ('GERENTE', 'Gerente'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil_empleado")
    cedula = models.CharField("Cédula", max_length=10, unique=True, validators=[validar_cedula_ruc_ecuador])
    cargo = models.CharField("Cargo", max_length=30, choices=CARGO_CHOICES)
    telefono = models.CharField("Teléfono", max_length=20, blank=True)
    sueldo_base = models.DecimalField("Sueldo Base", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    porcentaje_comision = models.DecimalField("Porcentaje Comisión (%)", max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Comisión aplicable si es mecánico o vendedor.")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_cargo_display()}"

class Horario(models.Model):
    DIA_CHOICES = [
        (1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'), (4, 'Jueves'), (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo')
    ]
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="horarios", null=True, blank=True)
    mecanico = models.ForeignKey(Mecanico, on_delete=models.CASCADE, related_name="horarios", null=True, blank=True)
    dia_semana = models.IntegerField("Día de la Semana", choices=DIA_CHOICES)
    hora_entrada = models.TimeField("Hora de Entrada")
    hora_salida = models.TimeField("Hora de Salida")

    class Meta:
        verbose_name = "Horario"
        verbose_name_plural = "Horarios"
        ordering = ['dia_semana', 'hora_entrada']

    def __str__(self):
        persona = self.empleado if self.empleado else self.mecanico
        return f"{persona} - {self.get_dia_semana_display()} ({self.hora_entrada} - {self.hora_salida})"

class Nomina(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, related_name="nominas", null=True, blank=True)
    mecanico = models.ForeignKey(Mecanico, on_delete=models.PROTECT, related_name="nominas", null=True, blank=True)
    fecha_inicio = models.DateField("Fecha Inicio")
    fecha_fin = models.DateField("Fecha Fin")
    sueldo_basico = models.DecimalField("Sueldo Básico", max_digits=10, decimal_places=2)
    comisiones = models.DecimalField("Comisiones", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    bonificaciones = models.DecimalField("Bonificaciones", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    deducciones = models.DecimalField("Deducciones (IESS, multas)", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_pagar = models.DecimalField("Total Neto a Pagar", max_digits=10, decimal_places=2, editable=False)
    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Nómina"
        verbose_name_plural = "Nóminas"
        ordering = ['-fecha_fin']

    def save(self, *args, **kwargs):
        self.total_pagar = (self.sueldo_basico + self.comisiones + self.bonificaciones) - self.deducciones
        if self.pagado and not self.fecha_pago:
            self.fecha_pago = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        persona = self.empleado if self.empleado else self.mecanico
        return f"Nómina de {persona} ({self.fecha_inicio} a {self.fecha_fin}) - Pagado: {self.pagado}"

class Proveedor(models.Model):
    ruc = models.CharField("RUC", max_length=13, unique=True, validators=[validar_cedula_ruc_ecuador])
    nombre_empresa = models.CharField("Razón Social", max_length=150)
    contacto = models.CharField("Nombre del Contacto", max_length=100, blank=True)
    telefono = models.CharField("Teléfono", max_length=20, blank=True)
    email = models.EmailField("Correo Electrónico", blank=True)
    direccion = models.TextField("Dirección", blank=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['nombre_empresa']

    def __str__(self):
        return f"{self.nombre_empresa} (RUC: {self.ruc})"

class CompraProveedor(models.Model):
    ESTADO_COMPRA = [
        ('PENDIENTE', 'Pendiente'),
        ('RECIBIDO', 'Recibido'),
        ('ANULADO', 'Anulado')
    ]
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="compras")
    fecha_compra = models.DateField("Fecha de Compra")
    documento_referencia = models.CharField("Nº Factura Proveedor", max_length=50, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    iva = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    estado = models.CharField(max_length=15, choices=ESTADO_COMPRA, default='PENDIENTE')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Compra a Proveedor"
        verbose_name_plural = "Compras a Proveedores"
        ordering = ['-fecha_compra']

    def __str__(self):
        return f"Compra #{self.id} - {self.proveedor.nombre_empresa} - Total: ${self.total} ({self.get_estado_display()})"

class DetalleCompraProveedor(models.Model):
    compra = models.ForeignKey(CompraProveedor, on_delete=models.CASCADE, related_name="detalles")
    repuesto = models.ForeignKey(Repuesto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField(default=1)
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Detalle de Compra"
        verbose_name_plural = "Detalles de Compras"

    @property
    def subtotal(self):
        return self.costo_unitario * self.cantidad

    def __str__(self):
        return f"{self.cantidad} x {self.repuesto.nombre} en Compra #{self.compra.id}"

class MovimientoInventario(models.Model):
    TIPO_MOVIMIENTO = [
        ('INGRESO_COMPRA', 'Ingreso por Compra a Proveedor'),
        ('EGRESO_VENTA', 'Egreso por Venta Directa (POS)'),
        ('EGRESO_TALLER', 'Egreso por Reparación en Taller (OT)'),
        ('INGRESO_DEVOLUCION', 'Ingreso por Devolución de Cliente'),
        ('AJUSTE_POSITIVO', 'Ajuste de Inventario (Sobrante)'),
        ('AJUSTE_NEGATIVO', 'Ajuste de Inventario (Faltante/Merma)'),
    ]
    repuesto = models.ForeignKey(Repuesto, on_delete=models.CASCADE, related_name="movimientos")
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO)
    cantidad = models.IntegerField("Cantidad")
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    motivo = models.TextField("Motivo / Observación", blank=True)

    class Meta:
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.cantidad} x {self.repuesto.nombre} ({self.fecha.strftime('%d/%m/%Y')})"

class Factura(models.Model):
    ESTADO_FACTURA = [('PAGADA', 'Pagada'), ('ANULADA', 'Anulada')]
    ESTADO_SRI_CHOICES = [
        ('PENDIENTE', 'Pendiente de Envío'),
        ('ENVIADO', 'Enviado al SRI'),
        ('AUTORIZADO', 'Autorizado y Vigente'),
        ('RECHAZADO', 'Rechazado por el SRI'),
        ('DEVUELTO', 'Devuelto / Con Errores'),
    ]
    AMBIENTE_CHOICES = [
        ('1', 'Pruebas (Test)'),
        ('2', 'Producción (Real)'),
    ]
    
    # Datos básicos de facturación
    numero_factura = models.CharField("Nº Factura", max_length=20, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="facturas")
    orden_trabajo = models.OneToOneField(OrdenTrabajo, on_delete=models.SET_NULL, null=True, blank=True, related_name="factura")
    fecha_emision = models.DateTimeField(auto_now_add=True)
    vendedor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="facturas_vendidas")
    estado = models.CharField(max_length=10, choices=ESTADO_FACTURA, default='PAGADA')
    
    # Impuestos y totales del SRI
    subtotal_15 = models.DecimalField("Subtotal IVA 15%", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    subtotal_0 = models.DecimalField("Subtotal IVA 0%", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_descuento = models.DecimalField("Total Descuento", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    valor_iva = models.DecimalField("Valor Total IVA", max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_pagar = models.DecimalField("Total Neto a Pagar", max_digits=10, decimal_places=2)
    
    # Datos específicos para la integración del SRI
    clave_acceso = models.CharField("Clave de Acceso (49 dígitos)", max_length=49, unique=True, blank=True, null=True)
    numero_autorizacion = models.CharField("Número de Autorización SRI", max_length=49, blank=True, null=True)
    fecha_autorizacion = models.DateTimeField("Fecha de Autorización SRI", blank=True, null=True)
    estado_sri = models.CharField("Estado SRI", max_length=15, choices=ESTADO_SRI_CHOICES, default='PENDIENTE')
    ambiente = models.CharField("Ambiente SRI", max_length=1, choices=AMBIENTE_CHOICES, default='1')
    tipo_emision = models.CharField("Tipo Emisión SRI", max_length=1, default='1') # 1 = Normal
    
    # Archivos físicos del comprobante electrónico
    xml_firmado = models.CharField("Ruta XML Firmado", max_length=255, blank=True, null=True)
    pdf_ride = models.CharField("Ruta PDF RIDE", max_length=255, blank=True, null=True)
    mensajes_error_sri = models.JSONField("Errores / Respuestas SRI", default=list, blank=True)

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_emision']

    def save(self, *args, **kwargs):
        if not self.numero_factura:
            # Formato secuencial estándar ecuatoriano: 001-001-000000001
            ultimo = Factura.objects.all().order_by('id').last()
            consecutivo = (ultimo.id + 1) if ultimo else 1
            self.numero_factura = f"001-001-{consecutivo:09d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero_factura} - {self.cliente.nombre} - ${self.total_pagar} ({self.estado})"

class DetalleFactura(models.Model):
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name="detalles")
    repuesto = models.ForeignKey(Repuesto, on_delete=models.PROTECT, null=True, blank=True)
    servicio_mano_obra = models.CharField("Descripción Servicio (Mano Obra)", max_length=150, null=True, blank=True)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    class Meta:
        verbose_name = "Detalle de Factura"
        verbose_name_plural = "Detalles de Facturas"

    def save(self, *args, **kwargs):
        self.subtotal = self.precio_unitario * self.cantidad
        super().save(*args, **kwargs)

    def __str__(self):
        item = self.repuesto.nombre if self.repuesto else self.servicio_mano_obra
        return f"{self.cantidad} x {item} en {self.factura.numero_factura}"

class MetodoPago(models.Model):
    METODOS = [
        ('01', 'Sin Utilización del Sistema Financiero (Efectivo)'),
        ('16', 'Tarjeta de Débito'),
        ('19', 'Tarjeta de Crédito'),
        ('20', 'Otros con Utilización del Sistema Financiero (Transferencia/Apps)'),
    ]
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name="pagos")
    metodo = models.CharField("Método de Pago SRI", max_length=2, choices=METODOS, default='01')
    monto = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Método de Pago"
        verbose_name_plural = "Métodos de Pago"

    def __str__(self):
        return f"{self.get_metodo_display()}: ${self.monto}"

class RecomendacionIA(models.Model):
    TIPO_RECOMENDACION = [
        ('INVENTARIO', 'Predicción de Compra / Stock'),
        ('MANTENIMIENTO', 'Sugerencia de Mantenimiento Preventivo a Clientes'),
    ]
    tipo = models.CharField(max_length=20, choices=TIPO_RECOMENDACION)
    titulo = models.CharField(max_length=150)
    contenido = models.TextField("Recomendación Detallada de Negocio")
    fecha_generacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Recomendación IA"
        verbose_name_plural = "Recomendaciones IA"
        ordering = ['-fecha_generacion']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.titulo} ({self.fecha_generacion.strftime('%d/%m/%Y')})"
