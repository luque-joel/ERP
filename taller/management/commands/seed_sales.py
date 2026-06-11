import random
import sys
import calendar
import time
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction, connection, InterfaceError, OperationalError
from django.db.models import F
from django.core.management.color import no_style

from taller.models import (
    Cliente, Vehiculo, Mecanico, Repuesto, ModeloCompatibilidad,
    OrdenTrabajo, DetalleRepuestoOrden, Factura, DetalleFactura,
    MetodoPago, MovimientoInventario
)

# Helpers for unique code generation
def generate_valid_cedula():
    prov = f"{random.randint(1, 24):02d}"
    third = str(random.randint(0, 5))
    digits = [int(prov[0]), int(prov[1]), int(third)] + [random.randint(0, 9) for _ in range(6)]
    
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0
    for i in range(9):
        valor = digits[i] * coeficientes[i]
        if valor >= 10:
            valor -= 9
        suma += valor
    
    residuo = suma % 10
    digito_esperado = 10 - residuo if residuo != 0 else 0
    
    cedula = "".join(map(str, digits)) + str(digito_esperado)
    return cedula

def generate_valid_ruc():
    return generate_valid_cedula() + "001"

def generate_valid_plate():
    letters = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3))
    digits = "".join(random.choices("0123456789", k=4))
    return f"{letters}-{digits}"

def generate_unique_sku():
    sku = f"REP-{random.randint(10000, 99999)}"
    while Repuesto.objects.filter(sku=sku).exists():
        sku = f"REP-{random.randint(10000, 99999)}"
    return sku

# State variables for robust sequential unique codes
_next_ot_num = None
_next_factura_num = None

def generate_unique_codigo_orden():
    global _next_ot_num
    if _next_ot_num is None:
        ultimo = OrdenTrabajo.objects.all().order_by('id').last()
        if ultimo:
            _next_ot_num = ultimo.id + 1
        else:
            _next_ot_num = 1
            
    while True:
        code = f"OT-{_next_ot_num:05d}"
        if not OrdenTrabajo.objects.filter(codigo_orden=code).exists():
            _next_ot_num += 1
            return code
        _next_ot_num += 1

def generate_unique_numero_factura():
    global _next_factura_num
    if _next_factura_num is None:
        ultimo = Factura.objects.all().order_by('id').last()
        if ultimo:
            _next_factura_num = ultimo.id + 1
        else:
            _next_factura_num = 1
            
    while True:
        code = f"001-001-{_next_factura_num:09d}"
        if not Factura.objects.filter(numero_factura=code).exists():
            _next_factura_num += 1
            return code
        _next_factura_num += 1

class Command(BaseCommand):
    help = 'Genera un conjunto de datos históricos de ventas y órdenes de trabajo para análisis y módulo de IA.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--months',
            type=int,
            default=12,
            help='Número de meses de historial a generar (por defecto: 12)'
        )
        parser.add_argument(
            '--target-sales',
            type=float,
            default=3000.0,
            help='Meta promedio de ventas mensuales en USD antes de estacionalidad (por defecto: 3000.0)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Eliminar facturas, ordenes de trabajo e inventario existentes antes de sembrar.'
        )

    def handle(self, *args, **options):
        months = options['months']
        target_sales = options['target_sales']
        clear_existing = options['clear']

        self.stdout.write(self.style.WARNING(f"Iniciando siembra de datos para {months} meses en el pasado..."))

        # Sincronizar secuencias de autoincremento en base de datos para evitar IntegrityErrors de claves primarias
        self.stdout.write("Sincronizando secuencias de autoincremento (IDs)...")
        models_to_reset = [
            Cliente, Vehiculo, Mecanico, Repuesto, ModeloCompatibilidad,
            OrdenTrabajo, DetalleRepuestoOrden, Factura, DetalleFactura,
            MetodoPago, MovimientoInventario
        ]
        sequence_sql = connection.ops.sequence_reset_sql(no_style(), models_to_reset)
        with connection.cursor() as cursor:
            for sql in sequence_sql:
                try:
                    cursor.execute(sql)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"No se pudo sincronizar secuencia: {e}"))
        self.stdout.write(self.style.SUCCESS("Secuencias de ID sincronizadas."))

        if clear_existing:
            self.stdout.write(self.style.WARNING("Eliminando registros antiguos (Facturas, Detalles, Métodos de Pago, Órdenes, Movimientos de Inventario)..."))
            MetodoPago.objects.all().delete()
            DetalleFactura.objects.all().delete()
            DetalleRepuestoOrden.objects.all().delete()
            Factura.objects.all().delete()
            OrdenTrabajo.objects.all().delete()
            MovimientoInventario.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Registros antiguos eliminados."))

            # Resetear secuencias de nuevo tras la eliminación para comenzar desde ID 1
            sequence_sql = connection.ops.sequence_reset_sql(no_style(), models_to_reset)
            with connection.cursor() as cursor:
                for sql in sequence_sql:
                    try:
                        cursor.execute(sql)
                    except Exception:
                        pass
            self.stdout.write(self.style.SUCCESS("Secuencias reiniciadas a 1."))

        # Reiniciar contadores de códigos de cadenas si se limpian los datos
        global _next_ot_num, _next_factura_num
        if clear_existing:
            _next_ot_num = 1
            _next_factura_num = 1
        else:
            _next_ot_num = None
            _next_factura_num = None

        # 1. Asegurar existencia de Usuarios / Vendedores
        vendedores = list(User.objects.all())
        if not vendedores:
            self.stdout.write("No se encontraron usuarios. Creando usuario administrativo 'admin'...")
            admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            vendedores = [admin_user]
            self.stdout.write(self.style.SUCCESS("Superusuario creado: admin / admin123"))
        
        # 2. Asegurar existencia de Mecánicos
        mecanicos = list(Mecanico.objects.all())
        nombres_mecanicos = ["Juan Cajas", "Pedro Silva", "Luis Cueva", "Carlos Ortiz", "Diego Morán"]
        if len(mecanicos) < 3:
            self.stdout.write("Creando mecánicos básicos...")
            for nombre in nombres_mecanicos:
                if not Mecanico.objects.filter(nombre=nombre).exists():
                    m = Mecanico.objects.create(
                        nombre=nombre,
                        telefono=f"09{random.randint(10000000, 99999999)}",
                        estado='DISPONIBLE'
                    )
                    mecanicos.append(m)
            self.stdout.write(self.style.SUCCESS(f"Mecánicos disponibles: {len(mecanicos)}"))

        # 3. Asegurar existencia de Clientes
        clientes = list(Cliente.objects.all())
        nombres_clientes = [
            "Carlos Mendoza", "María José Delgado", "Juan Carlos Pérez", "Ana María Castro",
            "José Luis Moreira", "Diana Carolina Solís", "Roberto Carlos Vera", "Gabriela Estefanía Loor",
            "Fernando Javier Intriago", "Patricia Elizabeth Cedeño", "Manuel Agustín Cevallos", "Sandra Milena Holguín",
            "Luis Alfredo Zambrano", "Mónica Alexandra Barreto", "Washington Vinicio Falconí"
        ]
        if len(clientes) < 10:
            self.stdout.write("Creando clientes de prueba...")
            for nombre in nombres_clientes:
                cedula = generate_valid_cedula()
                while Cliente.objects.filter(cedula_ruc=cedula).exists():
                    cedula = generate_valid_cedula()
                
                c = Cliente.objects.create(
                    tipo_identificacion='05', # Cédula
                    cedula_ruc=cedula,
                    nombre=nombre,
                    telefono=f"09{random.randint(10000000, 99999999)}",
                    email=f"{nombre.lower().replace(' ', '.')}@example.com",
                    direccion=f"Calle Principal {random.randint(100, 999)} y Av. Central"
                )
                clientes.append(c)
            self.stdout.write(self.style.SUCCESS(f"Clientes disponibles: {len(clientes)}"))

        # 4. Asegurar existencia de Modelos de Compatibilidad
        compatibilidades = list(ModeloCompatibilidad.objects.all())
        motos_modelos = [
            ("Shineray", "XY200"), ("Shineray", "Chief 250"), ("Yamaha", "FZ25"), ("Yamaha", "Crypton"),
            ("Honda", "CB190R"), ("Honda", "XR190L"), ("Suzuki", "GN125"), ("Tuko", "TK150"),
            ("Dayang", "DY200"), ("Motor Uno", "Monster 200")
        ]
        if not compatibilidades:
            self.stdout.write("Creando modelos de compatibilidad de motos...")
            for marca, modelo in motos_modelos:
                try:
                    mc = ModeloCompatibilidad.objects.create(marca=marca, modelo=modelo)
                    compatibilidades.append(mc)
                except Exception:
                    pass
            self.stdout.write(self.style.SUCCESS(f"Compatibilidades disponibles: {len(compatibilidades)}"))

        # 5. Asegurar existencia de Repuestos y reabastecer stock para evitar quiebres
        repuestos = list(Repuesto.objects.all())
        repuestos_lista = [
            ("Filtro de Aceite FZ25", "MOTOR", "Yamaha", 1.50, 4.50),
            ("Llanta Rinaldi 90/90-18", "LLANTAS", "Rinaldi", 25.00, 45.00),
            ("Zapatas de Freno Posterior", "FRENOS", "Coheco", 4.00, 8.50),
            ("Aceite Motul 5100 10W40", "ACEITES", "Motul", 7.50, 13.50),
            ("Faro Delantero LED", "ELECTRICO", "Generic", 6.00, 15.00),
            ("Batería de Gel 12V 7Ah", "ELECTRICO", "Bosch", 15.00, 32.00),
            ("Bujía NGK CPR8EA-9", "ELECTRICO", "NGK", 2.00, 4.50),
            ("Kit de Transmisión (Arrastre)", "TRANSMISION", "Riffel", 18.00, 35.00),
            ("Amortiguador Posterior Reforzado", "SUSPENSION", "Gabriel", 22.00, 48.00),
            ("Pastillas de Freno Delantero", "FRENOS", "Fras-le", 3.50, 7.00),
            ("Espejos Retrovisores Homologados", "CARROCERIA", "Generic", 5.00, 12.00),
            ("Direccionales LED Universales (Par)", "ELECTRICO", "Generic", 4.00, 9.50),
            ("Cadena de Transmisión 428H", "TRANSMISION", "DID", 8.00, 17.00),
            ("Cable de Acelerador", "VARIOS", "Generic", 1.80, 4.00),
            ("Tubo de Escape Deportivo", "CARROCERIA", "Yoshimura", 45.00, 95.00),
        ]

        if len(repuestos) < 8:
            self.stdout.write("Creando catálogo de repuestos de prueba...")
            for nombre, cat, marca, p_compra, p_venta in repuestos_lista:
                sku = generate_unique_sku()
                r = Repuesto.objects.create(
                    sku=sku,
                    tarifa_iva='2', # 15% IVA
                    nombre=nombre,
                    categoria=cat,
                    marca=marca,
                    ubicacion=f"Percha {random.choice(['A','B','C'])}-{random.randint(1,5)}",
                    stock=random.randint(40, 100),
                    stock_minimo=random.randint(5, 10),
                    precio_compra=Decimal(str(p_compra)),
                    precio_venta=Decimal(str(p_venta)),
                    aplica_iva=True
                )
                if compatibilidades:
                    r.compatibilidades.set(random.sample(compatibilidades, k=random.randint(1, 3)))
                repuestos.append(r)
            self.stdout.write(self.style.SUCCESS(f"Catálogo de repuestos listo: {len(repuestos)} repuestos."))
        else:
            self.stdout.write("Restableciendo stock de repuestos existentes...")
            for r in repuestos:
                r.stock = random.randint(150, 300)
                r.save()

        # 6. Asegurar existencia de Vehículos
        vehiculos = list(Vehiculo.objects.all())
        if len(vehiculos) < 10:
            self.stdout.write("Creando vehículos para clientes...")
            marcas = ["Yamaha", "Honda", "Shineray", "Suzuki", "Dayang"]
            modelos_moto = ["FZ25", "CB190R", "XY200", "GN125", "DY200"]
            for c in clientes:
                for _ in range(random.randint(1, 2)):
                    placa = generate_valid_plate()
                    while Vehiculo.objects.filter(placa=placa).exists():
                        placa = generate_valid_plate()
                    
                    idx = random.randint(0, len(marcas)-1)
                    v = Vehiculo.objects.create(
                        tipo=random.choice(['MOTO', 'TRICIMOTO']),
                        marca=marcas[idx],
                        modelo=modelos_moto[idx],
                        anio=random.randint(2018, 2025),
                        placa=placa,
                        color=random.choice(["Negro", "Rojo", "Azul", "Blanco", "Gris"]),
                        cliente=c
                    )
                    vehiculos.append(v)
            self.stdout.write(self.style.SUCCESS(f"Vehículos listos: {len(vehiculos)}"))

        problemas = [
            ("Moto no enciende con el botón de arranque", "Batería descargada o dañada, requiere cambio."),
            ("Frenos traseros muy largos y ruidosos", "Zapatas de freno desgastadas, se realiza cambio."),
            ("Golpeteo fuerte en la rueda posterior al acelerar", "Kit de arrastre desgastado (cadena estirada), requiere kit nuevo."),
            ("Fuga de aceite en la parte inferior del motor", "Retenedores desgastados y empaque de cárter roto."),
            ("Falta de fuerza al subir cuestas y tironeo", "Carburador obstruido y bujía desgastada. Requiere limpieza y cambio de bujía."),
            ("Humo azul por el escape y consumo de aceite", "Desgaste de anillos y guías de válvula. Requiere reparación parcial."),
            ("Dirección dura y vibra al frenar", "Cunas de dirección flojas y pastillas delanteras cristalizadas."),
            ("Luz de faro delantero no enciende", "Foco LED quemado o fusible de alimentación cortado."),
            ("Mantenimiento general preventivo por kilometraje", "Limpieza de carburador, calibración de válvulas, ajuste de pernos, cambio de aceite."),
            ("Cambio de llanta posterior lisa", "Llanta posterior desgastada por rodamiento diario. Cambio de llanta."),
        ]

        # 7. Ciclo de siembra por meses
        now = timezone.now()
        start_date = now - timedelta(days=30 * months)
        
        total_facturas_creadas = 0
        total_ordenes_creadas = 0
        total_recaudado = Decimal('0.00')

        self.stdout.write("Iniciando generación de transacciones...")

        # Generar mes a mes
        for m_idx in range(months + 1):
            current_date_ref = start_date + timedelta(days=30 * m_idx)
            year = current_date_ref.year
            month = current_date_ref.month

            if year == now.year and month > now.month:
                break

            # Calcular factor estacional
            seasonal_factor = 1.0
            if month == 12:
                seasonal_factor = 1.35
            elif month == 1:
                seasonal_factor = 1.20
            elif month == 4:
                seasonal_factor = 0.85
            elif month in [5, 6]:
                seasonal_factor = 1.10

            growth_factor = 1.0 + (m_idx * 0.015)
            month_target = Decimal(str(target_sales)) * Decimal(str(seasonal_factor)) * Decimal(str(growth_factor))
            month_target *= Decimal(str(random.uniform(0.9, 1.1)))

            month_sales = Decimal('0.00')
            month_invoices_count = 0
            
            self.stdout.write(f"Sembrando {year}-{month:02d} | Meta: ${month_target:,.2f}...")

            while month_sales < month_target:
                last_day = calendar.monthrange(year, month)[1]
                if year == now.year and month == now.month:
                    last_day = min(last_day, now.day)
                
                day = random.randint(1, last_day)
                hour = random.randint(8, 17)
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                
                invoice_date = timezone.make_aware(
                    datetime(year, month, day, hour, minute, second),
                    timezone.get_current_timezone()
                )

                if invoice_date > now:
                    invoice_date = now

                client = random.choice(clientes)
                vendedor = random.choice(vendedores)
                is_taller = random.random() < 0.60
                
                # Implementación de reintentos robusta con transacciones atómicas independientes
                max_retries = 3
                success_invoice = False
                
                for attempt in range(max_retries):
                    try:
                        with transaction.atomic():
                            orden_trabajo = None
                            detalles_factura = []
                            detalles_orden = []
                            movimientos_inventario = []

                            if is_taller:
                                client_vehicles = list(client.vehiculos.all())
                                if not client_vehicles:
                                    placa = generate_valid_plate()
                                    while Vehiculo.objects.filter(placa=placa).exists():
                                        placa = generate_valid_plate()
                                    v = Vehiculo.objects.create(
                                        tipo=random.choice(['MOTO', 'TRICIMOTO']),
                                        marca=random.choice(["Yamaha", "Honda", "Shineray"]),
                                        modelo=random.choice(["FZ25", "CB190R", "XY200"]),
                                        anio=random.randint(2018, 2025),
                                        placa=placa,
                                        cliente=client
                                    )
                                    client_vehicles = [v]
                                
                                vehicle = random.choice(client_vehicles)
                                mecanico = random.choice(mecanicos)
                                prob_desc = random.choice(problemas)
                                mano_obra_cost = Decimal(str(round(random.uniform(12.00, 45.00), 2)))
                                codigo_ot_gen = generate_unique_codigo_orden()

                                # Crear OT
                                orden_trabajo = OrdenTrabajo.objects.create(
                                    codigo_orden=codigo_ot_gen,
                                    vehiculo=vehicle,
                                    mecanico=mecanico,
                                    creado_por=vendedor,
                                    facturada=True,
                                    kilometraje=random.randint(1000, 45000),
                                    nivel_combustible=random.choice(["1/4", "1/2", "3/4", "Lleno"]),
                                    observaciones_recepcion=prob_desc[0],
                                    diagnostico=prob_desc[1],
                                    mano_obra=mano_obra_cost,
                                    estado='ENTREGADO'
                                )
                                
                                det_mano_obra = DetalleFactura(
                                    servicio_mano_obra=f"Servicio Taller: {prob_desc[0]}",
                                    cantidad=1,
                                    precio_unitario=mano_obra_cost,
                                    subtotal=mano_obra_cost
                                )
                                detalles_factura.append(det_mano_obra)

                                num_repuestos = random.randint(1, 3)
                                selected_repuestos = random.sample(repuestos, k=min(num_repuestos, len(repuestos)))
                                
                                for r in selected_repuestos:
                                    qty = random.randint(1, 2)
                                    
                                    det_ot = DetalleRepuestoOrden(
                                        orden=orden_trabajo,
                                        repuesto=r,
                                        cantidad=qty,
                                        precio_historico=r.precio_venta
                                    )
                                    detalles_orden.append(det_ot)

                                    det_fac = DetalleFactura(
                                        repuesto=r,
                                        cantidad=qty,
                                        precio_unitario=r.precio_venta,
                                        subtotal=r.precio_venta * qty
                                    )
                                    detalles_factura.append(det_fac)

                                    mov = MovimientoInventario(
                                        repuesto=r,
                                        tipo='EGRESO_TALLER',
                                        cantidad=qty,
                                        usuario=vendedor,
                                        motivo=f"Consumo en Orden {orden_trabajo.codigo_orden}"
                                    )
                                    movimientos_inventario.append(mov)
                                    Repuesto.objects.filter(pk=r.pk).update(stock=F('stock') - qty)
                            else:
                                num_repuestos = random.randint(1, 4)
                                selected_repuestos = random.sample(repuestos, k=min(num_repuestos, len(repuestos)))
                                
                                for r in selected_repuestos:
                                    qty = random.randint(1, 3)
                                    
                                    det_fac = DetalleFactura(
                                        repuesto=r,
                                        cantidad=qty,
                                        precio_unitario=r.precio_venta,
                                        subtotal=r.precio_venta * qty
                                    )
                                    detalles_factura.append(det_fac)

                                    mov = MovimientoInventario(
                                        repuesto=r,
                                        tipo='EGRESO_VENTA',
                                        cantidad=qty,
                                        usuario=vendedor,
                                        motivo="Venta POS Directa"
                                    )
                                    movimientos_inventario.append(mov)
                                    Repuesto.objects.filter(pk=r.pk).update(stock=F('stock') - qty)

                            # Calcular Totales de la Factura
                            subtotal_15 = Decimal('0.00')
                            subtotal_0 = Decimal('0.00')

                            for d in detalles_factura:
                                if d.repuesto:
                                    if d.repuesto.tarifa_iva == '2':
                                        subtotal_15 += d.subtotal
                                    else:
                                        subtotal_0 += d.subtotal
                                else:
                                    subtotal_15 += d.subtotal

                            valor_iva = subtotal_15 * Decimal('0.15')
                            total_pagar = subtotal_15 + subtotal_0 + valor_iva

                            subtotal_15 = round(subtotal_15, 2)
                            subtotal_0 = round(subtotal_0, 2)
                            valor_iva = round(valor_iva, 2)
                            total_pagar = round(total_pagar, 2)

                            num_factura_gen = generate_unique_numero_factura()

                            # Crear y guardar Factura
                            factura = Factura.objects.create(
                                numero_factura=num_factura_gen,
                                cliente=client,
                                orden_trabajo=orden_trabajo,
                                vendedor=vendedor,
                                estado='PAGADA',
                                subtotal_15=subtotal_15,
                                subtotal_0=subtotal_0,
                                total_descuento=Decimal('0.00'),
                                valor_iva=valor_iva,
                                total_pagar=total_pagar,
                                estado_sri='AUTORIZADO',
                                ambiente='1',
                                clave_acceso=f"{invoice_date.strftime('%d%m%Y')}0109999999990011001001{random.randint(100000000, 999999999)}123456781",
                                numero_autorizacion=f"AUT-{random.randint(10000000, 99999999)}-{random.randint(100000,999999)}",
                                fecha_autorizacion=invoice_date
                            )

                            # Guardar detalles y métodos de pago dentro del bloque atómico
                            for d in detalles_factura:
                                d.factura = factura
                                d.save()

                            for d_ot in detalles_orden:
                                d_ot.save()

                            for m in movimientos_inventario:
                                m.save()

                            rand_pay = random.random()
                            if rand_pay < 0.60:
                                metodo_str = '01'
                            elif rand_pay < 0.85:
                                metodo_str = '20'
                            elif rand_pay < 0.93:
                                metodo_str = '16'
                            else:
                                metodo_str = '19'
                            
                            MetodoPago.objects.create(
                                factura=factura,
                                metodo=metodo_str,
                                monto=total_pagar
                            )

                            # Actualizar fechas
                            Factura.objects.filter(pk=factura.pk).update(fecha_emision=invoice_date)
                            
                            if orden_trabajo:
                                ingreso_date = invoice_date - timedelta(hours=random.randint(2, 48))
                                OrdenTrabajo.objects.filter(pk=orden_trabajo.pk).update(
                                    fecha_ingreso=ingreso_date,
                                    fecha_prometida=invoice_date,
                                    fecha_entrega=invoice_date
                                )
                                total_ordenes_creadas += 1

                            if movimientos_inventario:
                                mov_ids = [mv.pk for mv in movimientos_inventario]
                                MovimientoInventario.objects.filter(pk__in=mov_ids).update(fecha=invoice_date)

                        # Si se completó sin excepciones, salir del bucle de reintentos
                        success_invoice = True
                        break
                    except (OperationalError, InterfaceError) as db_err:
                        # Cerrar conexión rota para forzar reconexión limpia en el siguiente intento
                        self.stdout.write(self.style.WARNING(f"Conexión perdida con base de datos, reintentando factura... Intento {attempt + 1}/{max_retries}. Error: {db_err}"))
                        try:
                            connection.close()
                        except Exception:
                            pass
                        time.sleep(1.5)
                
                # Si fallaron todos los reintentos de conexión, abortar
                if not success_invoice:
                    raise CommandError("La conexión con la base de datos de Railway se perdió definitivamente.")

                month_sales += total_pagar
                month_invoices_count += 1
                total_facturas_creadas += 1
                total_recaudado += total_pagar

            self.stdout.write(self.style.SUCCESS(f"-> Terminado {year}-{month:02d}: {month_invoices_count} facturas creadas. Total recaudado: ${month_sales:,.2f} USD"))

        self.stdout.write(self.style.SUCCESS("========================================================="))
        self.stdout.write(self.style.SUCCESS("¡PROCESO DE SIEMBRA COMPLETADO EXITOSAMENTE!"))
        self.stdout.write(self.style.SUCCESS(f"Total Facturas creadas: {total_facturas_creadas}"))
        self.stdout.write(self.style.SUCCESS(f"Total Órdenes creadas: {total_ordenes_creadas}"))
        self.stdout.write(self.style.SUCCESS(f"Total Recaudado en simulación: ${total_recaudado:,.2f} USD"))
        self.stdout.write(self.style.SUCCESS("========================================================="))
