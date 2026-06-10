from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.contrib.auth.models import User
from .validators import validar_cedula_ruc_ecuador
from .models import Cliente, Vehiculo, Repuesto, Mecanico, OrdenTrabajo, DetalleRepuestoOrden, Empleado

class CedulaRucValidatorTest(TestCase):
    def test_valid_cedula(self):
        # Cédula real válida (ejemplo real de Ecuador)
        try:
            validar_cedula_ruc_ecuador("1710034065")
        except ValidationError:
            self.fail("validar_cedula_ruc_ecuador lanzó ValidationError para una cédula válida!")

    def test_invalid_cedula(self):
        # Cédula inválida (dígito verificador incorrecto)
        with self.assertRaises(ValidationError):
            validar_cedula_ruc_ecuador("1710034061")
            
    def test_invalid_length(self):
        with self.assertRaises(ValidationError):
            validar_cedula_ruc_ecuador("1234")

    def test_valid_ruc_persona_natural(self):
        try:
            validar_cedula_ruc_ecuador("1710034065001")
        except ValidationError:
            self.fail("validar_cedula_ruc_ecuador lanzó ValidationError para un RUC de persona natural válido!")

class TallerModelsTest(TestCase):
    def setUp(self):
        # Configurar datos básicos de prueba
        self.cliente = Cliente.objects.create(
            cedula_ruc="1710034065",
            nombre="Ismael Test",
            telefono="0999999999"
        )
        self.vehiculo = Vehiculo.objects.create(
            tipo="MOTO",
            marca="Honda",
            modelo="XR 150",
            cliente=self.cliente
        )
        self.mecanico = Mecanico.objects.create(
            nombre="Mecánico Pedro",
            estado="DISPONIBLE"
        )
        self.repuesto = Repuesto.objects.create(
            sku="TEST-SKU-1",
            nombre="Filtro de Aire XR",
            categoria="MOTOR",
            stock=10,
            stock_minimo=2,
            precio_compra=Decimal("4.00"),
            precio_venta=Decimal("8.00")
        )

    def test_orden_trabajo_autocode(self):
        # Probar generación de código secuencial
        orden = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            mecanico=self.mecanico,
            mano_obra=Decimal("15.00")
        )
        self.assertEqual(orden.codigo_orden, "OT-00001")
        
        orden2 = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            mecanico=self.mecanico
        )
        self.assertEqual(orden2.codigo_orden, "OT-00002")

    def test_orden_trabajo_totals_calculation(self):
        # Crear orden
        orden = OrdenTrabajo.objects.create(
            vehiculo=self.vehiculo,
            mecanico=self.mecanico,
            mano_obra=Decimal("20.00")
        )
        
        # Añadir repuesto
        DetalleRepuestoOrden.objects.create(
            orden=orden,
            repuesto=self.repuesto,
            cantidad=2,
            precio_historico=self.repuesto.precio_venta
        )
        
        # Totales
        self.assertEqual(orden.total_repuestos, Decimal("16.00")) # 8 * 2
        self.assertEqual(orden.total_general, Decimal("36.00"))   # 20 (mano obra) + 16 (repuestos)

class ReportesViewsTest(TestCase):
    def setUp(self):
        # Crear usuarios para distintos roles
        self.gerente_user = User.objects.create_user(username='gerente', password='password123')
        self.vendedor_user = User.objects.create_user(username='vendedor', password='password123')
        self.bodeguero_user = User.objects.create_user(username='bodeguero', password='password123')
        
        self.cliente = Cliente.objects.create(
            cedula_ruc="1710034065",
            nombre="Ismael Test",
            telefono="0999999999"
        )
        
        Empleado.objects.create(user=self.gerente_user, cedula="1710034065", cargo="GERENTE")
        Empleado.objects.create(user=self.vendedor_user, cedula="0999999991", cargo="VENDEDOR")
        Empleado.objects.create(user=self.bodeguero_user, cedula="0999999992", cargo="BODEGUERO")

    def test_reportes_dashboard_access(self):
        # Usuario no autenticado es redirigido
        response = self.client.get('/reportes/')
        self.assertRedirects(response, '/login/?next=/reportes/')
        
        # Bodeguero no tiene acceso
        self.client.login(username='bodeguero', password='password123')
        response = self.client.get('/reportes/')
        self.assertEqual(response.status_code, 302) # Redireccionado por falta de permisos
        self.client.logout()
        
        # Gerente tiene acceso
        self.client.login(username='gerente', password='password123')
        response = self.client.get('/reportes/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reportes y Exportación")
        self.client.logout()

        # Vendedor tiene acceso
        self.client.login(username='vendedor', password='password123')
        response = self.client.get('/reportes/')
        self.assertEqual(response.status_code, 200)
        self.client.logout()

    def test_export_ventas_excel_access(self):
        # Gerente puede descargar excel
        self.client.login(username='gerente', password='password123')
        response = self.client.get('/reportes/ventas/excel/?fecha_inicio=2026-06-01&fecha_fin=2026-06-30')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.client.logout()

    def test_ia_decisiones_access(self):
        # Gerente puede acceder al modulo de decisiones
        self.client.login(username='gerente', password='password123')
        response = self.client.get('/ia/decisiones/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Toma de Decisiones con IA")
        
        # Test chat AJAX POST request
        response_post = self.client.post('/ia/decisiones/', {'query': 'proyeccion de repuestos'})
        self.assertEqual(response_post.status_code, 200)
        self.assertIn('response', response_post.json())
        self.client.logout()
        
        # Bodeguero no tiene acceso
        self.client.login(username='bodeguero', password='password123')
        response = self.client.get('/ia/decisiones/')
        self.assertEqual(response.status_code, 302)
        self.client.logout()
