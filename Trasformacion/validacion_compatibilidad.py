import datetime
from decimal import Decimal
import pandas as pd
import numpy as np

def ejecutar_mapeo_y_validacion(df_source):
    """
    Realiza el Mapeo Estructural del dataset plano a las 14 tablas del DFR,
    y luego ejecuta el Control de Calidad mediante la Validación de Compatibilidad.
    
    Retorna:
        tablas_finales (dict): Diccionario con los 14 DataFrames relacionales modelados.
        todo_correcto (bool): True si el control de calidad es aprobado, False en caso contrario.
    """
    print("\n>>> EJECUTANDO FASE 1: MAPEO ESTRUCTURAL (Módulo: validacion_compatibilidad.py)...")

    # 1. tipo_promocion
    tipo_promocion_f3 = df_source[['Promotion Code', 'Promotion Type Name']].copy()
    tipo_promocion_f3 = tipo_promocion_f3.rename(columns={
        'Promotion Code': 'Id_Tipo',
        'Promotion Type Name': 'Nombre_Tipo'
    }).drop_duplicates(subset=['Id_Tipo'])

    # 2. promocion
    promocion_f3 = df_source[['Promotion Code', 'Promotion Status', 'Promotion Start Date', 'Discount', 'Promotion End Date']].copy()
    promocion_f3 = promocion_f3.rename(columns={
        'Promotion Code': 'Id_promocion',
        'Promotion Status': 'Estado_Promocion',
        'Promotion Start Date': 'Fecha_Inicio',
        'Promotion End Date': 'Fecha_Finalizacion',
        'Discount': 'Porcentaje_Descuento'
    })
    promocion_f3['Id_Tipo'] = promocion_f3['Id_promocion']
    promocion_f3 = promocion_f3.drop_duplicates(subset=['Id_promocion'])

    # 3. historial_comercial
    historial_comercial_f3 = df_source[['Promotion Code', 'Order Date', 'Order Quantity', 'Number of Records']].copy()
    historial_comercial_f3 = historial_comercial_f3.rename(columns={
        'Promotion Code': 'Id_promocion',
        'Order Date': 'Fecha_Registro',
        'Order Quantity': 'Cantidad_Productos_Vendidos',
        'Number of Records': 'Cantidad_Ventas_Afectadas'
    })
    historial_comercial_f3['Fecha_Registro'] = historial_comercial_f3['Fecha_Registro'].apply(lambda x: x.date() if isinstance(x, datetime.datetime) else x)
    historial_comercial_f3.insert(0, 'Id_Historial', range(1, len(historial_comercial_f3) + 1))

    # 4. categoria (definido antes para poder mapear id_categoria en producto)
    categorias_unicas = df_source['Product Category'].dropna().unique()
    categoria_f3 = pd.DataFrame({
        'id_categoria': range(1, len(categorias_unicas) + 1),
        'nombre_categoria': categorias_unicas
    })

    # 5. producto (relacionado directamente con categoria mediante id_categoria)
    producto_f3 = df_source[['Product Code', 'Product Name', 'Product Container', 'Product Expiration Indicator', 'Product Shelf Life', 'Product Category']].copy()
    producto_f3 = producto_f3.merge(categoria_f3, left_on='Product Category', right_on='nombre_categoria', how='left')
    producto_f3 = producto_f3.rename(columns={
        'Product Code': 'Codigo_de_Producto',
        'Product Name': 'Nombre',
        'Product Container': 'Unidad_de_Medida',
        'Product Expiration Indicator': 'Indicador_de_Caducidad',
        'Product Shelf Life': 'Vida_Util',
        'id_categoria': 'id_categoria'
    })
    
    # Asegurar que sea 0 o 1 (booleano/tinyint)
    producto_f3['Indicador_de_Caducidad'] = pd.to_numeric(producto_f3['Indicador_de_Caducidad']).fillna(0).astype(int)
    
    producto_f3 = producto_f3[['Codigo_de_Producto', 'id_categoria', 'Nombre', 'Unidad_de_Medida', 'Indicador_de_Caducidad', 'Vida_Util']].drop_duplicates(subset=['Codigo_de_Producto'])

    # 6. prod_prom
    prod_prom_f3 = df_source[['Product Code', 'Promotion Code', 'Promotion Start Date', 'Discount', 'Order Quantity']].copy()
    prod_prom_f3 = prod_prom_f3.rename(columns={
        'Product Code': 'Codigo_Producto',
        'Promotion Code': 'Codigo_Promocion',
        'Promotion Start Date': 'Fecha_Asignacion',
        'Order Quantity': 'Stock_Afectado',
        'Discount': 'Porcentaje_Descuento'
    })
    prod_prom_f3 = prod_prom_f3.groupby(['Codigo_Producto', 'Codigo_Promocion'], as_index=False).agg({
        'Fecha_Asignacion': 'first',
        'Porcentaje_Descuento': 'first',
        'Stock_Afectado': 'sum'
    })
    prod_prom_f3.insert(2, 'Id_prom_pro', range(1, len(prod_prom_f3) + 1))

    # 7. venta
    venta_f3 = df_source[['Order ID', 'Order Date', 'Sales']].copy()
    venta_f3 = venta_f3.rename(columns={
        'Order ID': 'Numero_Transaccion',
        'Order Date': 'Fecha_Hora_Emision',
        'Sales': 'Precio_venta'
    }).drop_duplicates(subset=['Numero_Transaccion'])

    # 8. detalleventa
    detalleventa_f3 = df_source[['Order ID', 'Product Code', 'Order Quantity', 'Unit Price', 'Profit']].copy()
    detalleventa_f3 = detalleventa_f3.rename(columns={
        'Order ID': 'Numero_Transaccion',
        'Product Code': 'Codigo_de_Producto',
        'Order Quantity': 'Cantidad_Adquirida',
        'Unit Price': 'Precio_Unitario',
        'Profit': 'Utilidad'
    })
    detalleventa_f3.insert(0, 'Id_Detalle', range(1, len(detalleventa_f3) + 1))

    # 9. compra
    compra_f3 = df_source[['Purchase Date', 'Purchase Total Cost']].copy()
    compra_f3['Id_Compra'] = df_source['Purchase ID'].astype(int)
    compra_f3 = compra_f3.rename(columns={
        'Purchase Date': 'Fecha_Compra',
        'Purchase Total Cost': 'Precio_Compra'
    })
    compra_f3 = compra_f3[['Id_Compra', 'Fecha_Compra', 'Precio_Compra']].drop_duplicates(subset=['Id_Compra'])

    # 10. lotes_de_inventario (definido antes de detalle_compra y almacen para el cálculo del espacio)
    lotes_de_inventario_f3 = df_source[['Lot Number', 'Warehouse Code', 'Lot Ingress Date', 'Lot Occupied Space']].copy()
    lotes_de_inventario_f3 = lotes_de_inventario_f3.rename(columns={
        'Lot Number': 'Numero_Lote',
        'Warehouse Code': 'Codigo_de_Almacen',
        'Lot Ingress Date': 'Fecha_ingreso',
        'Lot Occupied Space': 'Espacio_ocupado'
    }).drop_duplicates(subset=['Numero_Lote'])

    # 11. detalle_compra
    detalle_compra_f3 = df_source[['Purchase ID', 'Lot Number', 'Product Code', 'Purchase Quantity', 'Purchase Unit Cost']].copy()
    detalle_compra_f3['Id_Compra'] = detalle_compra_f3['Purchase ID'].astype(int)
    detalle_compra_f3 = detalle_compra_f3.rename(columns={
        'Lot Number': 'Numero_Lote',
        'Product Code': 'Codigo_de_Producto',
        'Purchase Quantity': 'Cantidad',
        'Purchase Unit Cost': 'Costo_Unitario'
    })
    detalle_compra_f3 = detalle_compra_f3[['Id_Compra', 'Numero_Lote', 'Codigo_de_Producto', 'Cantidad','Costo_Unitario']].copy()
    detalle_compra_f3.insert(0, 'Id_Detalle_Compra', range(1, len(detalle_compra_f3) + 1))

    # 12. ubicacion (se corrige Codigo_Almacen a id_Ubicación)
    ubicacion_f3 = df_source[['Warehouse Code', 'Warehouse Address', 'Warehouse District', 'Warehouse City']].copy()
    ubicacion_f3 = ubicacion_f3.rename(columns={
        'Warehouse Code': 'id_Ubicación',
        'Warehouse Address': 'Direccion',
        'Warehouse District': 'Distrito',
        'Warehouse City': 'Ciudad'
    }).drop_duplicates(subset=['id_Ubicación'])

    # 13. almacen (Id_Ubicación y porcentaje de Espacio_ocupado calculado a partir de Capacidad_Total y lotes)
    almacen_f3 = df_source[['Warehouse Code', 'Warehouse Name', 'Warehouse Capacity', 'Warehouse Type', 'Warehouse State']].copy()
    almacen_f3 = almacen_f3.rename(columns={
        'Warehouse Code': 'Codigo_Almacen',
        'Warehouse Name': 'Nombre',
        'Warehouse Capacity': 'Capacidad_Total',
        'Warehouse Type': 'Tipo',
        'Warehouse State': 'Estado'
    })
    almacen_f3['Id_Ubicación'] = almacen_f3['Codigo_Almacen']
    almacen_f3 = almacen_f3.drop_duplicates(subset=['Codigo_Almacen'])
    
    # Calcular porcentaje de espacio ocupado
    suma_espacio = lotes_de_inventario_f3.groupby('Codigo_de_Almacen')['Espacio_ocupado'].sum().reset_index()
    almacen_f3 = almacen_f3.merge(suma_espacio, left_on='Codigo_Almacen', right_on='Codigo_de_Almacen', how='left')
    almacen_f3['Espacio_ocupado'] = almacen_f3['Espacio_ocupado'].fillna(0.0)
    almacen_f3['Espacio_ocupado'] = (almacen_f3['Espacio_ocupado'] / almacen_f3['Capacidad_Total'].astype(float) * 100.0).apply(lambda x: f"{x:.2f}%")
    if 'Codigo_de_Almacen' in almacen_f3.columns:
        almacen_f3 = almacen_f3.drop(columns=['Codigo_de_Almacen'])

    print("Mapeo estructural completado.")

    tablas_finales = {
        "tipo_promocion": tipo_promocion_f3,
        "promocion": promocion_f3,
        "historial_comercial": historial_comercial_f3,
        "producto": producto_f3,
        "categoria": categoria_f3,
        "prod_prom": prod_prom_f3,
        "venta": venta_f3,
        "detalleventa": detalleventa_f3,
        "compra": compra_f3,
        "detalle_compra": detalle_compra_f3,
        "lotes_de_inventario": lotes_de_inventario_f3,
        "almacen": almacen_f3,
        "ubicacion": ubicacion_f3
    }

    print("\n" + "="*30 + " VISTA DE TABLAS TEMPORALES MODELADAS " + "="*30)
    for nombre, df in tablas_finales.items():
        print(f"\nTabla: {nombre}")
        print(f"  Dimensiones: {df.shape[0]} filas, {df.shape[1]} columnas")
        print("  Estructura de tipos (dtypes):")
        for col, dtype in zip(df.columns, df.dtypes):
            print(f"    - {col}: {dtype}")
        print("  Primeros 3 registros de muestra:")
        print(df.head(3).to_string(index=False))
        print("-" * 80)

    # Iniciar validación
    print("\n>>> INICIANDO VALIDACIÓN DE COMPATIBILIDAD (EL CONTROL DE CALIDAD)...")
    reporte_resultados = validar_esquema_compatibilidad(tablas_finales)

    print("\n" + "="*30 + " INFORME DE CONTROL DE CALIDAD Y COMPATIBILIDAD " + "="*30)
    todo_correcto = True

    for tabla_nombre, check in reporte_resultados.items():
        es_compatible = all([
            check["estructura_columnas"],
            check["nulos_no_permitidos"],
            check["unicidad_pk"],
            check["tipo_datos"],
            check["longitud_varchar"],
            check["clave_foranea"]
        ])
        
        if es_compatible:
            estado_label = "[APROBADO - COMPATIBLE]"
            print(f"Tabla: {tabla_nombre.ljust(25)} {estado_label}")
            print("  - Datos estructurados, tipados y relacionados de forma correcta.")
        else:
            todo_correcto = False
            estado_label = "[RECHAZADO - INCOMPATIBLE]"
            print(f"Tabla: {tabla_nombre.ljust(25)} {estado_label}")
            print("  Errores críticos de compatibilidad encontrados:")
            for msg in check["mensajes_error"]:
                print(f"    * {msg}")
        print("-" * 90)

    if todo_correcto:
        print("\n>>> RESULTADO FINAL: ¡EL DATASET HA SIDO TRANSFORMADO Y VALIDADO CON ÉXITO! Todos los datos son compatibles con el DFR.")
    else:
        print("\n>>> RESULTADO FINAL: CONTROL DE CALIDAD RECHAZADO. Existen inconsistencias en las tablas temporales.")
    print("="*96)

    return tablas_finales, todo_correcto

def validar_esquema_compatibilidad(tablas):
    #tablas del modelo DFR
    reglas_esquema = {
        "tipo_promocion": {
            "Id_Tipo": (int, None, True, True, None),
            "Nombre_Tipo": (str, 100, False, False, None)
        },
        "promocion": {
            "Id_promocion": (int, None, True, True, None),
            "Id_Tipo": (int, None, False, False, ("tipo_promocion", "Id_Tipo")),
            "Estado_Promocion": (str, 50, False, False, None),
            "Fecha_Inicio": (datetime.date, None, False, False, None),
            "Porcentaje_Descuento": (float, None, False, False, None),
            "Fecha_Finalizacion": (datetime.date, None, False, False, None)
        },
        "historial_comercial": {
            "Id_Historial": (int, None, True, True, None),
            "Id_promocion": (int, None, False, False, ("promocion", "Id_promocion")),
            "Fecha_Registro": (datetime.date, None, False, False, None),
            "Cantidad_Productos_Vendidos": (int, None, False, False, None),
            "Cantidad_Ventas_Afectadas": (int, None, False, False, None)
        },
        "producto": {
            "Codigo_de_Producto": (str, 50, True, True, None),
            "id_categoria": (int, None, True, False, ("categoria", "id_categoria")),
            "Nombre": (str, 150, True, False, None),
            "Unidad_de_Medida": (str, 50, False, False, None),
            "Indicador_de_Caducidad": (int, None, True, False, None),
            "Vida_Util": (str, 50, False, False, None)
        },
        "categoria": {
            "id_categoria": (int, None, True, True, None),
            "nombre_categoria": (str, 100, False, False, None)
        },
        "prod_prom": {
            "Id_prom_pro": (int, None, True, True, None),
            "Codigo_Producto": (str, 50, False, False, ("producto", "Codigo_de_Producto")),
            "Codigo_Promocion": (int, None, False, False, ("promocion", "Id_promocion")),
            "Fecha_Asignacion": (datetime.date, None, False, False, None),
            "Porcentaje_Descuento": (float, None, False, False, None),
            "Stock_Afectado": (int, None, False, False, None)
        },
        "venta": {
            "Numero_Transaccion": (int, None, True, True, None),
            "Fecha_Hora_Emision": (datetime.datetime, None, False, False, None),
            "Precio_venta": (float, None, False, False, None)
        },
        "detalleventa": {
            "Id_Detalle": (int, None, True, True, None),
            "Numero_Transaccion": (int, None, True, False, ("venta", "Numero_Transaccion")),
            "Codigo_de_Producto": (str, 50, False, False, ("producto", "Codigo_de_Producto")),
            "Cantidad_Adquirida": (int, None, True, False, None),
            "Precio_Unitario": (float, None, False, False, None),
            "Utilidad": (float, None, False, False, None)
        },
        "compra": {
            "Id_Compra": (int, None, True, True, None),
            "Fecha_Compra": (datetime.date, None, False, False, None),
            "Precio_Compra": (float, None, False, False, None)
        },
        "detalle_compra": {
            "Id_Detalle_Compra": (int, None, True, True, None),
            "Id_Compra": (int, None, False, False, ("compra", "Id_Compra")),
            "Numero_Lote": (str, 50, False, False, ("lotes_de_inventario", "Numero_Lote")),
            "Codigo_de_Producto": (str, 50, False, False, ("producto", "Codigo_de_Producto")),
            "Cantidad": (int, None, False, False, None),
            "Costo_Unitario": (float, None, False, False, None)
        },
        "lotes_de_inventario": {
            "Numero_Lote": (str, 50, True, True, None),
            "Codigo_de_Almacen": (str, 50, False, False, ("almacen", "Codigo_Almacen")),
            "Fecha_ingreso": (datetime.date, None, False, False, None),
            "Espacio_ocupado": (float, None, False, False, None)
        },
        "almacen": {
            "Codigo_Almacen": (str, 50, True, True, None),
            "Id_Ubicación": (str, 50, False, False, ("ubicacion", "id_Ubicación")),
            "Nombre": (str, 150, False, False, None),
            "Tipo": (str, 50, False, False, None),
            "Capacidad_Total": (int, None, False, False, None),
            "Estado": (str, 50, False, False, None),
            "Espacio_ocupado": (str, 50, False, False, None)
        },
        "ubicacion": {
            "id_Ubicación": (str, 50, True, True, None),
            "Direccion": (str, 255, False, False, None),
            "Distrito": (str, 100, False, False, None),
            "Ciudad": (str, 100, False, False, None)
        }
    }

    reporte = {}
    for tabla, esquema in reglas_esquema.items():
        df = tablas[tabla]
        reporte_tabla = {
            "estructura_columnas": True,
            "nulos_no_permitidos": True,
            "unicidad_pk": True,
            "tipo_datos": True,
            "longitud_varchar": True,
            "clave_foranea": True,
            "mensajes_error": []
        }

        # 1. Estructura de columnas
        cols_esperadas = set(esquema.keys())
        cols_actuales = set(df.columns)
        if cols_esperadas != cols_actuales:
            reporte_tabla["estructura_columnas"] = False
            faltantes = cols_esperadas - cols_actuales
            sobrantes = cols_actuales - cols_esperadas
            if faltantes:
                reporte_tabla["mensajes_error"].append(f"Falta(n) columna(s) en esquema: {list(faltantes)}")
            if sobrantes:
                reporte_tabla["mensajes_error"].append(f"Columna(s) sobrante(s) no esperada(s): {list(sobrantes)}")
            reporte[tabla] = reporte_tabla
            continue

        # 2. Validación de registros
        campos_pk = []
        for campo, specs in esquema.items():
            tipo_esperado, max_len, no_null, es_pk, fk_ref = specs
            col_series = df[campo]

            if es_pk:
                campos_pk.append(campo)

            # A. Control de Nulos
            if no_null:
                nulos_cnt = col_series.isna().sum()
                if nulos_cnt > 0:
                    reporte_tabla["nulos_no_permitidos"] = False
                    reporte_tabla["mensajes_error"].append(
                        f"Columna '{campo}' tiene {nulos_cnt} nulo(s) no permitido(s)."
                    )

            # B. Control de Tipo de Datos
            errores_tipo = 0
            for val in col_series.dropna():
                if tipo_esperado == datetime.date:
                    if not isinstance(val, datetime.date) or isinstance(val, datetime.datetime):
                        if val in ['0000-00-00', '00:00:00']:
                            pass
                        else:
                            errores_tipo += 1
                elif tipo_esperado == datetime.datetime:
                    if not isinstance(val, (datetime.datetime, pd.Timestamp)):
                        errores_tipo += 1
                elif tipo_esperado == int:
                    if not (isinstance(val, (int, np.integer)) or (isinstance(val, float) and val.is_integer())):
                        errores_tipo += 1
                elif tipo_esperado == float:
                    if not isinstance(val, (int, float, np.floating, Decimal)):
                        errores_tipo += 1
                elif tipo_esperado == str:
                    if not isinstance(val, str):
                        errores_tipo += 1

            if errores_tipo > 0:
                reporte_tabla["tipo_datos"] = False
                reporte_tabla["mensajes_error"].append(
                    f"Columna '{campo}' contiene {errores_tipo} valor(es) con tipo de dato incorrecto (se esperaba {tipo_esperado.__name__})."
                )

            # C. Control de longitud de VARCHAR
            if max_len is not None:
                longitudes = col_series.dropna().astype(str).str.len()
                sobrepasados = (longitudes > max_len).sum()
                if sobrepasados > 0:
                    reporte_tabla["longitud_varchar"] = False
                    reporte_tabla["mensajes_error"].append(
                        f"Columna '{campo}' tiene {sobrepasados} registro(s) que superan el límite VARCHAR({max_len})."
                    )

            # D. Control de Claves Foráneas (FK)
            if fk_ref is not None:
                tabla_padre, campo_padre = fk_ref
                df_padre = tablas[tabla_padre]
                valores_hijos = set(col_series.dropna().unique())
                valores_padres = set(df_padre[campo_padre].dropna().unique())
                
                huerfanos = valores_hijos - valores_padres
                if huerfanos:
                    reporte_tabla["clave_foranea"] = False
                    reporte_tabla["mensajes_error"].append(
                        f"Clave Foránea huérfana en '{campo}' -> '{tabla_padre}.{campo_padre}'. Valores no existentes: {list(huerfanos)[:5]}"
                    )

        # E. Control de Unicidad de Clave Primaria (compuesta o simple)
        if campos_pk:
            duplicados = df.duplicated(subset=campos_pk).sum()
            if duplicados > 0:
                reporte_tabla["unicidad_pk"] = False
                reporte_tabla["mensajes_error"].append(
                    f"Clave Primaria {campos_pk} tiene {duplicados} registro(s) duplicado(s)."
                )

        reporte[tabla] = reporte_tabla

    return reporte
