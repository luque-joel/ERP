import sqlite3
import re
import os

def exportar_a_postgres_sql(sqlite_path, sql_output_path):
    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()

    # Tablas en el orden correcto de inserción para respetar claves foráneas
    tablas = [
        ('taller_modelocompatibilidad', 'taller_modelocompatibilidad_id_seq'),
        ('taller_repuesto', 'taller_repuesto_id_seq'),
        ('taller_repuesto_compatibilidades', None),  # Join table, no sequence
        ('taller_mecanico', 'taller_mecanico_id_seq'),
        ('taller_cliente', 'taller_cliente_id_seq'),
        ('taller_vehiculo', 'taller_vehiculo_id_seq'),
        ('taller_proveedor', 'taller_proveedor_id_seq'),
        ('auth_user', 'auth_user_id_seq'),
        ('taller_empleado', 'taller_empleado_id_seq'),
        ('taller_horario', 'taller_horario_id_seq'),
        ('taller_compraproveedor', 'taller_compraproveedor_id_seq'),
        ('taller_detallecompraproveedor', 'taller_detallecompraproveedor_id_seq'),
        ('taller_ordentrabajo', 'taller_ordentrabajo_id_seq'),
        ('taller_detallerepuestoorden', 'taller_detallerepuestoorden_id_seq'),
        ('taller_factura', 'taller_factura_id_seq'),
        ('taller_detallefactura', 'taller_detallefactura_id_seq'),
        ('taller_metodopago', 'taller_metodopago_id_seq'),
        ('taller_movimientoinventario', 'taller_movimientoinventario_id_seq'),
        ('taller_nomina', 'taller_nomina_id_seq'),
        ('taller_recomendacionia', 'taller_recomendacionia_id_seq'),
    ]

    sql_statements = []
    sql_statements.append("-- ============================================================")
    sql_statements.append("-- SCRIPT DE INSERCIÓN DE DATOS COMPLETO (POSTGRESQL)")
    sql_statements.append("-- ============================================================")
    sql_statements.append("BEGIN;")
    sql_statements.append("")
    sql_statements.append("-- Limpieza de datos previos (opcional, sin tocar superusuario ID 1)")
    sql_statements.append("DELETE FROM taller_detallefactura;")
    sql_statements.append("DELETE FROM taller_metodopago;")
    sql_statements.append("DELETE FROM taller_factura;")
    sql_statements.append("DELETE FROM taller_detallerepuestoorden;")
    sql_statements.append("DELETE FROM taller_ordentrabajo;")
    sql_statements.append("DELETE FROM taller_movimientoinventario;")
    sql_statements.append("DELETE FROM taller_detallecompraproveedor;")
    sql_statements.append("DELETE FROM taller_compraproveedor;")
    sql_statements.append("DELETE FROM taller_nomina;")
    sql_statements.append("DELETE FROM taller_horario;")
    sql_statements.append("DELETE FROM taller_empleado;")
    sql_statements.append("DELETE FROM auth_user WHERE id > 1;")
    sql_statements.append("DELETE FROM taller_mecanico;")
    sql_statements.append("DELETE FROM taller_vehiculo;")
    sql_statements.append("DELETE FROM taller_cliente;")
    sql_statements.append("DELETE FROM taller_proveedor;")
    sql_statements.append("DELETE FROM taller_repuesto_compatibilidades;")
    sql_statements.append("DELETE FROM taller_repuesto;")
    sql_statements.append("DELETE FROM taller_modelocompatibilidad;")
    sql_statements.append("DELETE FROM taller_recomendacionia;")
    sql_statements.append("")

    for tabla, _ in tablas:
        # Obtener columnas de la tabla
        cur.execute(f"PRAGMA table_info({tabla})")
        columnas_info = cur.fetchall()
        col_names = [col[1] for col in columnas_info]
        
        # Consultar datos
        query = f"SELECT * FROM {tabla}"
        # Para auth_user, excluir el superusuario (ID 1)
        if tabla == 'auth_user':
            query += " WHERE id > 1"
            
        cur.execute(query)
        rows = cur.fetchall()
        
        if not rows:
            continue
            
        sql_statements.append(f"-- Datos para la tabla: {tabla}")
        
        for row in rows:
            valores_sql = []
            for val in row:
                if val is None:
                    valores_sql.append("NULL")
                elif isinstance(val, bool):
                    valores_sql.append("true" if val else "false")
                elif isinstance(val, int):
                    valores_sql.append(str(val))
                elif isinstance(val, float):
                    valores_sql.append(str(val))
                else:
                    # Es un string (texto, fecha, json, etc.)
                    # Duplicar las comillas simples para escapar en SQL
                    val_str = str(val).replace("'", "''")
                    # Manejar booleanos representados como 1 o 0 en SQLite para campos booleanos
                    valores_sql.append(f"'{val_str}'")
                    
            cols_joined = ", ".join(col_names)
            vals_joined = ", ".join(valores_sql)
            
            # Reemplazar valores específicos si son booleanos que SQLite guardó como enteros
            # En Django SQLite, los booleanos a veces se guardan como 1/0. Vamos a corregirlos según el tipo de columna.
            for idx, col in enumerate(columnas_info):
                col_type = col[2].upper()
                if 'BOOL' in col_type or col[1] in ['activo', 'aplica_iva', 'facturada', 'pagado', 'is_superuser', 'is_staff', 'is_active']:
                    if valores_sql[idx] == '1':
                        valores_sql[idx] = 'true'
                    elif valores_sql[idx] == '0':
                        valores_sql[idx] = 'false'
            
            vals_joined = ", ".join(valores_sql)
            sql_statements.append(f"INSERT INTO {tabla} ({cols_joined}) VALUES ({vals_joined});")
        sql_statements.append("")

    sql_statements.append("-- ============================================================")
    sql_statements.append("-- ACTUALIZAR LOS SECUENCIALES DE LAS TABLAS EN POSTGRESQL")
    sql_statements.append("-- ============================================================")
    for tabla, seq in tablas:
        if seq:
            sql_statements.append(f"SELECT setval('{seq}', (SELECT COALESCE(MAX(id), 1) FROM {tabla}));")
            
    sql_statements.append("")
    sql_statements.append("COMMIT;")

    with open(sql_output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(sql_statements))
    
    print(f"Exportación a SQL completada con éxito en {sql_output_path}")

if __name__ == '__main__':
    exportar_a_postgres_sql('db.sqlite3', 'poblar_postgres.sql')
