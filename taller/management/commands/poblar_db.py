from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import random
from datetime import date, timedelta, time

from taller.models import (
    Cliente, Vehiculo, ModeloCompatibilidad, Repuesto, Mecanico,
    OrdenTrabajo, DetalleRepuestoOrden, Empleado, Horario, Nomina,
    Proveedor, CompraProveedor, DetalleCompraProveedor, MovimientoInventario,
    Factura, DetalleFactura, MetodoPago, RecomendacionIA
)

# Helpers for Ecuadorian IDs validation (Module 10 & 11)
def generar_cedula_valida(existentes):
    while True:
        provincia = random.choice([f"{p:02d}" for p in range(1, 25)] + ["30"])
        tercer_digito = str(random.randint(0, 5))
        cuerpo = provincia + tercer_digito + "".join(str(random.randint(0, 9)) for _ in range(6))
        coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        suma = 0
        for i in range(9):
            valor = int(cuerpo[i]) * coeficientes[i]
            if valor >= 10:
                valor -= 9
            suma += valor
        residuo = suma % 10
        verificador = 10 - residuo if residuo != 0 else 0
        cedula = cuerpo + str(verificador)
        if cedula not in existentes:
            existentes.add(cedula)
            return cedula

def generar_ruc_persona_valida(existentes):
    while True:
        ced = generar_cedula_valida(existentes)
        ruc = ced + "001"
        if ruc not in existentes:
            existentes.add(ruc)
            return ruc

def generar_ruc_sociedad_valida(existentes):
    while True:
        provincia = random.choice([f"{p:02d}" for p in range(1, 25)] + ["30"])
        cuerpo = provincia + "9" + "".join(str(random.randint(0, 9)) for _ in range(6))
        coeficientes = [4, 3, 2, 5, 4, 3, 2, 0, 0]
        suma = 0
        for i in range(9):
            suma += int(cuerpo[i]) * coeficientes[i]
        residuo = suma % 11
        verificador = 11 - residuo if residuo != 0 else 0
        if verificador == 11:
            verificador = 0
        ruc = cuerpo + str(verificador) + "001"
        if ruc not in existentes:
            existentes.add(ruc)
            return ruc

class Command(BaseCommand):
    help = 'Pobla la base de datos con registros de prueba realistas para el ERP'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Elimina todos los datos existentes de pruebas (excepto superusuarios) antes de poblar la base de datos.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Iniciando proceso de población de base de datos..."))
        
        if options['clean']:
            self.stdout.write(self.style.WARNING("Limpiando datos existentes..."))
            with transaction.atomic():
                # Delete details first to avoid foreign key errors
                DetalleFactura.objects.all().delete()
                MetodoPago.objects.all().delete()
                Factura.objects.all().delete()
                DetalleRepuestoOrden.objects.all().delete()
                OrdenTrabajo.objects.all().delete()
                MovimientoInventario.objects.all().delete()
                DetalleCompraProveedor.objects.all().delete()
                CompraProveedor.objects.all().delete()
                Nomina.objects.all().delete()
                Horario.objects.all().delete()
                Empleado.objects.all().delete()
                Mecanico.objects.all().delete()
                Vehiculo.objects.all().delete()
                Cliente.objects.all().delete()
                Proveedor.objects.all().delete()
                
                # Delete non-superuser users
                User.objects.filter(is_superuser=False).delete()
                
                # We can also clean compatibilities and parts
                Repuesto.objects.all().delete()
                ModeloCompatibilidad.objects.all().delete()
                RecomendacionIA.objects.all().delete()
                
            self.stdout.write(self.style.SUCCESS("Limpieza completada con éxito."))

        # Load sets of existing unique identifiers to avoid integrity constraints errors
        cedulas_generadas = set(Cliente.objects.values_list('cedula_ruc', flat=True)) | set(Empleado.objects.values_list('cedula', flat=True))
        placas_generadas = set(Vehiculo.objects.exclude(placa__isnull=True).values_list('placa', flat=True))
        skus_generados = set(Repuesto.objects.values_list('sku', flat=True))
        claves_generadas = set(Factura.objects.exclude(clave_acceso__isnull=True).values_list('clave_acceso', flat=True))

        def generar_placa_unica():
            while True:
                letra_provincia = random.choice('ABCDEFGHJKLMNOPQRSTU')
                letra_tipo = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                numeros = f"{random.randint(100, 999)}"
                letra_fin = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                placa = f"{letra_provincia}{letra_tipo}{numeros}{letra_fin}"
                if placa not in placas_generadas:
                    placas_generadas.add(placa)
                    return placa

        def generar_sku(existentes):
            while True:
                sku = f"REP-{random.randint(10000, 99999)}"
                if sku not in existentes:
                    existentes.add(sku)
                    return sku

        def generar_clave_acceso(existentes):
            while True:
                clave = "".join(str(random.randint(0, 9)) for _ in range(49))
                if clave not in existentes:
                    existentes.add(clave)
                    return clave

        with transaction.atomic():
            # 1. Users & Employees
            self.stdout.write("Creando usuarios y perfiles de empleados...")
            superuser = User.objects.filter(is_superuser=True).first()
            if not superuser:
                superuser = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
                self.stdout.write(self.style.SUCCESS("Superusuario por defecto creado: admin/admin123"))

            test_users = []
            for username, first, last, cargo in [
                ('cajero1', 'Juan', 'Pérez', 'VENDEDOR'),
                ('bodeguero1', 'Luis', 'Gómez', 'BODEGUERO'),
                ('admin_rrhh', 'María', 'Lasso', 'ADMIN_RRHH'),
            ]:
                user, created = User.objects.get_or_create(username=username, defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f"{username}@taller.com"
                })
                if created:
                    user.set_password('taller123')
                    user.save()
                test_users.append(user)

            for user in test_users:
                if not hasattr(user, 'perfil_empleado'):
                    cargo = 'VENDEDOR'
                    if 'bodeguero' in user.username:
                        cargo = 'BODEGUERO'
                    elif 'admin_rrhh' in user.username:
                        cargo = 'ADMIN_RRHH'
                    
                    Empleado.objects.create(
                        user=user,
                        cedula=generar_cedula_valida(cedulas_generadas),
                        cargo=cargo,
                        telefono=f"09{random.randint(10000000, 99999999)}",
                        sueldo_base=Decimal(random.randint(450, 800)),
                        porcentaje_comision=Decimal(random.choice([0.00, 2.50, 5.00]))
                    )

            # 2. Compatibilidades
            self.stdout.write("Creando marcas y modelos de compatibilidad...")
            marcas_motos = ["Honda", "Yamaha", "Suzuki", "Shineray", "Daytona", "IGM", "Ranger", "Tundra"]
            modelos_motos = {
                "Honda": ["CB190R", "CBR250", "XR190", "Wave 110"],
                "Yamaha": ["FZ25", "YBR125", "XTZ150", "Crypton"],
                "Suzuki": ["GN125", "AX100", "GIXXER 150"],
                "Shineray": ["XY150", "XY200", "Jet 125"],
                "Daytona": ["D200", "Ryder 150"],
                "IGM": ["Cargo 150", "Racer 200"],
                "Ranger": ["R150", "R200"],
                "Tundra": ["T150", "T200"]
            }
            compatibilidades = []
            for _ in range(12):
                marca = random.choice(marcas_motos)
                modelo = random.choice(modelos_motos[marca])
                comp, created = ModeloCompatibilidad.objects.get_or_create(marca=marca, modelo=modelo)
                compatibilidades.append(comp)

            # 3. Mecánicos
            self.stdout.write("Creando mecánicos...")
            nombres_mecanicos = ["Segundo Chimbo", "Manuel Guachamín", "Kleber Toaquiza", "Ángel Chasi", "Wilson Pallo"]
            mecanicos = []
            for nombre in nombres_mecanicos:
                mec, created = Mecanico.objects.get_or_create(
                    nombre=nombre,
                    defaults={
                        'telefono': f"09{random.randint(10000000, 99999999)}",
                        'estado': random.choice(['DISPONIBLE', 'DISPONIBLE', 'OCUPADO'])
                    }
                )
                mecanicos.append(mec)

            # 4. Repuestos
            self.stdout.write("Creando catálogo de repuestos...")
            repuestos_data = [
                ("Bujía NGK D8TC", "MOTOR", 1.50, 3.50),
                ("Filtro de Aceite FZ25", "MOTOR", 2.20, 5.00),
                ("Pastillas de Freno Delanteras", "FRENOS", 3.00, 7.50),
                ("Zapatas de Freno Posterior", "FRENOS", 4.00, 9.00),
                ("Kit de Arrastre GN125", "TRANSMISION", 12.00, 25.00),
                ("Llanta Rinaldi 90/90-18", "LLANTAS", 18.00, 35.00),
                ("Cámara de Llanta R18", "LLANTAS", 3.50, 7.00),
                ("Aceite Motul 5100 10W40", "ACEITES", 6.50, 11.50),
                ("Aceite Castrol Actevo 20W50", "ACEITES", 5.00, 9.00),
                ("Batería Bosch 12V 7Ah", "ELECTRICO", 15.00, 28.00),
                ("Cable de Acelerador", "VARIOS", 1.80, 4.00),
                ("Cable de Embrague", "VARIOS", 1.80, 4.00),
                ("Faro Delantero LED", "ELECTRICO", 8.00, 18.00),
                ("Direccionales LED (Par)", "ELECTRICO", 3.00, 7.00),
                ("Amortiguador Posterior (Par)", "SUSPENSION", 20.00, 42.00),
                ("Cadena de Transmisión 428H", "TRANSMISION", 5.00, 12.00),
                ("Disco de Freno Delantero", "FRENOS", 10.00, 22.00),
                ("Retenedores de Barra (Par)", "SUSPENSION", 1.50, 4.50),
                ("Espejos Retrovisores (Par)", "CARROCERIA", 4.00, 10.00),
                ("Manubrio Deportivo", "CARROCERIA", 7.00, 15.00),
                ("Carburador Completo 150cc", "MOTOR", 14.00, 30.00),
                ("Empaque de Cilindro", "MOTOR", 0.50, 2.00),
                ("Flotador de Gasolina", "ELECTRICO", 2.50, 6.00),
                ("Switch de Encendido (Llaves)", "ELECTRICO", 5.00, 12.00),
                ("Foco de Stop Posterior", "ELECTRICO", 0.80, 2.50)
            ]
            repuestos = []
            for nombre, categoria, p_compra, p_venta in repuestos_data:
                sku = generar_sku(skus_generados)
                rep = Repuesto.objects.create(
                    sku=sku,
                    tarifa_iva='2',
                    nombre=nombre,
                    categoria=categoria,
                    marca=random.choice(["SL", "Koyo", "NGK", "Bosch", "Motul", "Castrol", "Rinaldi", "Generic"]),
                    ubicacion=f"Estante {random.choice('ABCDE')} - Fila {random.randint(1, 5)}",
                    stock=random.randint(10, 50),
                    stock_minimo=5,
                    precio_compra=Decimal(p_compra),
                    precio_venta=Decimal(p_venta),
                    aplica_iva=True
                )
                rep.compatibilidades.set(random.sample(compatibilidades, random.randint(1, 3)))
                repuestos.append(rep)

            # 5. Proveedores
            self.stdout.write("Creando proveedores...")
            nombres_proveedores = ["Motos Repuestos S.A.", "Importadora Castro", "Distribuidora El Turi", "Rueda Seguro Ltda."]
            proveedores = []
            for nombre in nombres_proveedores:
                ruc = generar_ruc_sociedad_valida(cedulas_generadas)
                prov = Proveedor.objects.create(
                    ruc=ruc,
                    nombre_empresa=nombre,
                    contacto=f"Ing. {random.choice(['Carlos', 'Sofía', 'Daniel', 'Marcela'])} {random.choice(['López', 'Ramos', 'García', 'Villalba'])}",
                    telefono=f"02{random.randint(2000000, 9999999)}",
                    email=f"ventas@{nombre.lower().replace(' ', '').replace('.', '')}.com",
                    direccion=f"Av. Principal N{random.randint(10, 99)} y Calle {random.randint(1, 20)}"
                )
                proveedores.append(prov)

            # 6. Compras a Proveedores e ingresos de Inventario
            self.stdout.write("Creando historial de compras a proveedores...")
            for i in range(8):
                prov = random.choice(proveedores)
                compra_date = date.today() - timedelta(days=random.randint(10, 60))
                compra = CompraProveedor.objects.create(
                    proveedor=prov,
                    fecha_compra=compra_date,
                    documento_referencia=f"001-002-{random.randint(1000, 99999):09d}",
                    estado='RECIBIDO'
                )
                subtotal = Decimal('0.00')
                for _ in range(random.randint(2, 5)):
                    rep = random.choice(repuestos)
                    qty = random.randint(5, 20)
                    cost = rep.precio_compra
                    DetalleCompraProveedor.objects.create(
                        compra=compra,
                        repuesto=rep,
                        cantidad=qty,
                        costo_unitario=cost
                    )
                    
                    # Movimiento de inventario
                    MovimientoInventario.objects.create(
                        repuesto=rep,
                        tipo='INGRESO_COMPRA',
                        cantidad=qty,
                        fecha=timezone.make_aware(timezone.datetime.combine(compra_date, time(random.randint(9, 17), 0))),
                        usuario=random.choice(test_users + [superuser]),
                        motivo=f"Ingreso por compra al proveedor {prov.nombre_empresa}"
                    )
                    
                    rep.stock += qty
                    rep.save()
                    subtotal += cost * qty
                
                compra.subtotal = subtotal
                compra.iva = subtotal * Decimal('0.15')
                compra.total = subtotal + compra.iva
                compra.save()

            # 7. Clientes
            self.stdout.write("Creando clientes...")
            nombres_clientes = [
                ("Juan Pérez", "05"), ("María Silva", "05"), ("Carlos Mendoza", "05"), ("Ana Coba", "05"),
                ("Luis Chiriboga", "05"), ("Sofía Espinoza", "05"), ("Diego Romero", "05"), ("Lucía Vaca", "05"),
                ("José Torres", "05"), ("Gabriela Noboa", "05"), ("Fernando Castro", "05"), ("Diana Ortega", "05"),
                ("Corporación MotoGas S.A.", "04"), ("Taxis RuedaLibre S.A.", "04"), ("Hugo Sánchez", "05"),
                ("Patricia Peralta", "05"), ("Ramiro Játiva", "05"), ("Estela Falconí", "05"), ("Consumidor Final", "07")
            ]
            clientes = []
            for nombre, tipo in nombres_clientes:
                if tipo == "07":
                    ruc_ced = "9999999999999"
                elif tipo == "04":
                    ruc_ced = generar_ruc_sociedad_valida(cedulas_generadas)
                else:
                    ruc_ced = generar_cedula_valida(cedulas_generadas)
                
                cli, created = Cliente.objects.get_or_create(
                    cedula_ruc=ruc_ced,
                    defaults={
                        'tipo_identificacion': tipo,
                        'nombre': nombre,
                        'telefono': f"09{random.randint(10000000, 99999999)}" if tipo != "07" else "",
                        'email': f"{nombre.lower().split()[0]}@gmail.com" if tipo != "07" else "",
                        'direccion': f"Calle {random.choice(['Quito', 'Guayaquil', 'Amazonas', '10 de Agosto', 'Shyris'])} N{random.randint(10, 150)}" if tipo != "07" else ""
                    }
                )
                clientes.append(cli)

            # 8. Vehículos
            self.stdout.write("Creando vehículos y asociando a clientes...")
            marcas_modelos = [
                ("Yamaha", "FZ25"), ("Yamaha", "YBR125"), ("Yamaha", "Crypton"),
                ("Honda", "CB190R"), ("Honda", "XR190"), ("Honda", "Wave 110"),
                ("Suzuki", "GN125"), ("Suzuki", "AX100"),
                ("Shineray", "XY150"), ("Shineray", "XY200"),
                ("Daytona", "D200"), ("Daytona", "Ryder 150")
            ]
            vehiculos = []
            clientes_reales = [c for c in clientes if c.tipo_identificacion != "07"]
            for _ in range(18):
                marca, modelo = random.choice(marcas_modelos)
                tipo = 'MOTO'
                if random.random() < 0.15:
                    tipo = 'TRICIMOTO'
                
                veh = Vehiculo.objects.create(
                    tipo=tipo,
                    marca=marca,
                    modelo=modelo,
                    anio=random.randint(2015, 2026),
                    placa=generar_placa_unica(),
                    numero_motor=f"ENG-{random.randint(100000, 999999)}",
                    numero_chasis=f"VIN-{random.randint(100000, 999999)}",
                    color=random.choice(["Negro", "Rojo", "Azul", "Blanco", "Plomo", "Verde"]),
                    cliente=random.choice(clientes_reales)
                )
                vehiculos.append(veh)

            # 9. Horarios
            self.stdout.write("Creando horarios para empleados y mecánicos...")
            for emp in Empleado.objects.all():
                for dia in [1, 2, 3, 4, 5]:
                    Horario.objects.create(
                        empleado=emp,
                        dia_semana=dia,
                        hora_entrada=time(8, 30),
                        hora_salida=time(17, 30)
                    )
            for mec in mecanicos:
                for dia in [1, 2, 3, 4, 5, 6]:
                    Horario.objects.create(
                        mecanico=mec,
                        dia_semana=dia,
                        hora_entrada=time(8, 0),
                        hora_salida=time(17, 0)
                    )

            # 10. Órdenes de Trabajo y Facturas asociadas
            self.stdout.write("Creando órdenes de trabajo y facturación asociada...")
            estados_ot = ['PENDIENTE', 'EN_PROCESO', 'ESPERANDO_REPUESTOS', 'TERMINADO', 'ENTREGADO', 'ENTREGADO', 'ENTREGADO', 'ANULADO']
            for i in range(30):
                veh = random.choice(vehiculos)
                mec = random.choice(mecanicos)
                creador = random.choice(test_users)
                estado = random.choice(estados_ot)
                
                dias_atras = random.randint(1, 45)
                fecha_ing = timezone.now() - timedelta(days=dias_atras)
                
                ot = OrdenTrabajo.objects.create(
                    vehiculo=veh,
                    mecanico=mec,
                    creado_por=creador,
                    kilometraje=veh.anio * random.randint(10, 50) + random.randint(1000, 5000),
                    nivel_combustible=random.choice(["1/4", "1/2", "3/4", "Lleno"]),
                    observaciones_recepcion=random.choice([
                        "Fallo en encendido", "Sonido extraño en motor", "Frenos desgastados",
                        "Mantenimiento general", "Cambio de aceite y filtros", "Problema eléctrico en luces",
                        "Llanta posterior pinchada", "Embrague patina", "Revisión de suspensión"
                    ]),
                    checklist_json={
                        "retrovisores": random.choice(["OK", "Roto", "N/A"]),
                        "luces": random.choice(["OK", "Fallo"]),
                        "casco": random.choice(["Si", "No"]),
                        "herramientas": random.choice(["Si", "No"])
                    },
                    diagnostico=random.choice([
                        "Se requiere reemplazo de bujía y limpieza de carburador",
                        "Desgaste total de pastillas delanteras, requiere cambio",
                        "Kit de arrastre desgastado, dientes de catalina doblados",
                        "Falta lubricación y calibración de válvulas",
                        "Nivel de aceite extremadamente bajo, requiere cambio completo",
                        "Fuga en retenedores de barra, requiere cambio de retenedores y líquido de suspensión"
                    ]) if estado != 'PENDIENTE' else "",
                    mano_obra=Decimal(random.choice([10.00, 15.00, 20.00, 25.00, 35.00])) if estado != 'PENDIENTE' else Decimal('0.00'),
                    estado=estado
                )
                
                # Overwrite auto_now_add for historical accuracy
                OrdenTrabajo.objects.filter(id=ot.id).update(fecha_ingreso=fecha_ing)
                ot.refresh_from_db()
                
                # If state is not PENDIENTE, add parts
                if estado != 'PENDIENTE':
                    for _ in range(random.randint(1, 3)):
                        rep = random.choice(repuestos)
                        qty = random.randint(1, 2)
                        if rep.stock >= qty:
                            DetalleRepuestoOrden.objects.create(
                                orden=ot,
                                repuesto=rep,
                                cantidad=qty,
                                precio_historico=rep.precio_venta
                            )
                            if estado in ['TERMINADO', 'ENTREGADO']:
                                MovimientoInventario.objects.create(
                                    repuesto=rep,
                                    tipo='EGRESO_TALLER',
                                    cantidad=qty,
                                    fecha=fecha_ing + timedelta(hours=random.randint(2, 6)),
                                    usuario=creador,
                                    motivo=f"Egreso por orden de trabajo {ot.codigo_orden}"
                                )
                                rep.stock -= qty
                                rep.save()
                
                # If ENTREGADO, bill and invoice
                if estado == 'ENTREGADO':
                    ot.facturada = True
                    ot.fecha_entrega = ot.fecha_ingreso + timedelta(days=random.randint(1, 3))
                    ot.save()
                    
                    subtotal_iva = Decimal('0.00')
                    subtotal_0 = Decimal('0.00')
                    
                    subtotal_iva += ot.mano_obra
                    
                    for rep_utilizado in ot.repuestos_utilizados.all():
                        if rep_utilizado.repuesto.aplica_iva:
                            subtotal_iva += rep_utilizado.subtotal
                        else:
                            subtotal_0 += rep_utilizado.subtotal
                    
                    valor_iva = subtotal_iva * Decimal('0.15')
                    total_neto = subtotal_iva + subtotal_0 + valor_iva
                    
                    factura = Factura.objects.create(
                        cliente=ot.vehiculo.cliente,
                        orden_trabajo=ot,
                        vendedor=creador,
                        estado='PAGADA',
                        subtotal_15=subtotal_iva,
                        subtotal_0=subtotal_0,
                        total_descuento=Decimal('0.00'),
                        valor_iva=valor_iva,
                        total_pagar=total_neto,
                        clave_acceso=generar_clave_acceso(claves_generadas),
                        numero_autorizacion=f"{random.randint(10000000000000000000, 99999999999999999999)}",
                        fecha_autorizacion=ot.fecha_entrega,
                        estado_sri='AUTORIZADO',
                        ambiente='1'
                    )
                    
                    Factura.objects.filter(id=factura.id).update(fecha_emision=ot.fecha_entrega)
                    
                    if ot.mano_obra > 0:
                        DetalleFactura.objects.create(
                            factura=factura,
                            repuesto=None,
                            servicio_mano_obra=f"Mano de Obra: {ot.observaciones_recepcion}",
                            cantidad=1,
                            precio_unitario=ot.mano_obra
                        )
                    
                    for rep_utilizado in ot.repuestos_utilizados.all():
                        DetalleFactura.objects.create(
                            factura=factura,
                            repuesto=rep_utilizado.repuesto,
                            servicio_mano_obra="",
                            cantidad=rep_utilizado.cantidad,
                            precio_unitario=rep_utilizado.precio_historico
                        )
                    
                    MetodoPago.objects.create(
                        factura=factura,
                        metodo=random.choice(['01', '16', '19', '20']),
                        monto=total_neto
                    )

            # 11. Ventas Directas (Facturas Mostrador sin Orden)
            self.stdout.write("Creando ventas directas en mostrador (POS)...")
            for i in range(10):
                cli = random.choice(clientes)
                creador = random.choice(test_users)
                fecha_sale = timezone.now() - timedelta(days=random.randint(1, 45))
                
                subtotal_iva = Decimal('0.00')
                subtotal_0 = Decimal('0.00')
                
                detalles_compra = []
                for _ in range(random.randint(1, 3)):
                    rep = random.choice(repuestos)
                    qty = random.randint(1, 3)
                    if rep.stock >= qty:
                        detalles_compra.append((rep, qty))
                        if rep.aplica_iva:
                            subtotal_iva += rep.precio_venta * qty
                        else:
                            subtotal_0 += rep.precio_venta * qty
                
                if not detalles_compra:
                    continue
                    
                valor_iva = subtotal_iva * Decimal('0.15')
                total_neto = subtotal_iva + subtotal_0 + valor_iva
                
                factura = Factura.objects.create(
                    cliente=cli,
                    orden_trabajo=None,
                    vendedor=creador,
                    estado='PAGADA',
                    subtotal_15=subtotal_iva,
                    subtotal_0=subtotal_0,
                    total_descuento=Decimal('0.00'),
                    valor_iva=valor_iva,
                    total_pagar=total_neto,
                    clave_acceso=generar_clave_acceso(claves_generadas),
                    numero_autorizacion=f"{random.randint(10000000000000000000, 99999999999999999999)}",
                    fecha_autorizacion=fecha_sale,
                    estado_sri='AUTORIZADO',
                    ambiente='1'
                )
                
                Factura.objects.filter(id=factura.id).update(fecha_emision=fecha_sale)
                
                for rep, qty in detalles_compra:
                    DetalleFactura.objects.create(
                        factura=factura,
                        repuesto=rep,
                        servicio_mano_obra="",
                        cantidad=qty,
                        precio_unitario=rep.precio_venta
                    )
                    
                    MovimientoInventario.objects.create(
                        repuesto=rep,
                        tipo='EGRESO_VENTA',
                        cantidad=qty,
                        fecha=fecha_sale,
                        usuario=creador,
                        motivo=f"Venta en mostrador (Factura {factura.numero_factura})"
                    )
                    
                    rep.stock -= qty
                    rep.save()
                    
                MetodoPago.objects.create(
                    factura=factura,
                    metodo=random.choice(['01', '16', '19', '20']),
                    monto=total_neto
                )

            # 12. Nóminas
            self.stdout.write("Creando nóminas históricas...")
            for emp in Empleado.objects.all():
                for mes in [4, 5]:
                    Nomina.objects.create(
                        empleado=emp,
                        fecha_inicio=date(2026, mes, 1),
                        fecha_fin=date(2026, mes, 28 if mes==2 else (30 if mes in [4,6,9,11] else 31)),
                        sueldo_basico=emp.sueldo_base,
                        comisiones=Decimal(random.randint(20, 80)),
                        bonificaciones=Decimal(random.choice([0, 10, 20])),
                        deducciones=Decimal(random.randint(10, 40)),
                        pagado=True,
                        fecha_pago=timezone.now() - timedelta(days=(6-mes)*30)
                    )
            for mec in mecanicos:
                for mes in [4, 5]:
                    Nomina.objects.create(
                        mecanico=mec,
                        fecha_inicio=date(2026, mes, 1),
                        fecha_fin=date(2026, mes, 28 if mes==2 else (30 if mes in [4,6,9,11] else 31)),
                        sueldo_basico=Decimal(460.00),
                        comisiones=Decimal(random.randint(30, 100)),
                        bonificaciones=Decimal(random.choice([0, 15, 30])),
                        deducciones=Decimal(random.randint(10, 45)),
                        pagado=True,
                        fecha_pago=timezone.now() - timedelta(days=(6-mes)*30)
                    )

            # 13. Recomendaciones IA
            self.stdout.write("Creando recomendaciones de IA...")
            RecomendacionIA.objects.create(
                tipo='INVENTARIO',
                titulo='Alerta de Stock Mínimo - Bujías y Aceite',
                contenido='Se sugiere realizar compra preventiva de Bujías NGK D8TC y Aceite Motul 5100, dado que la tendencia histórica del taller muestra alta demanda de mantenimientos preventivos a inicios del próximo mes.'
            )
            RecomendacionIA.objects.create(
                tipo='MANTENIMIENTO',
                titulo='Sugerencia de Contacto para Mantenimiento Preventivo',
                contenido='El vehículo Honda CB190R de placa PA123B ingresó por última vez hace 90 días. Se sugiere enviar un correo de recordatorio al cliente para su próximo cambio de aceite.'
            )
            RecomendacionIA.objects.create(
                tipo='INVENTARIO',
                titulo='Optimización de Pedidos a Proveedor',
                contenido='El proveedor Importadora Castro ofrece un 5% de descuento en pedidos superiores a $500. Se recomienda agrupar la compra de repuestos de frenos y suspensiones con este proveedor para alcanzar el beneficio.'
            )

        self.stdout.write(self.style.SUCCESS("Base de datos poblada con éxito con registros realistas."))
