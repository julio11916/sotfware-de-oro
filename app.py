import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, Response
from datetime import datetime

app = Flask(__name__)
app.secret_key = "clave"  # Necesario para manejar sesiones

# Si no existe detalle_pedido.xlsx, crear uno vacío
if not os.path.exists('bd/detalle_pedido.xlsx'):
    detalle_pedido = pd.DataFrame(columns=['id_detalle','id_pedido','id_producto','cantidad','subtotal'])
    detalle_pedido.to_excel('bd/detalle_pedido.xlsx', index=False)

@app.route('/')
def home():
    productos = pd.read_excel('bd/producto.xlsx')
    lista_productos = productos.to_dict(orient='records')
    return render_template('login.html', productos=lista_productos)

@app.route('/login', methods=['POST'])
def login():
    usuarios = pd.read_excel('bd/usuarios.xlsx')  # leer cada vez
    email = request.form['email']
    password = request.form['password']

    usuario = usuarios[(usuarios['email'] == email) & (usuarios['password_hash'] == password)]

    if not usuario.empty:
        rol = usuario.iloc[0]['rol']
        session['usuario'] = email
        session['rol'] = rol

        if rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    else:
        return "Credenciales inválidas. Intenta de nuevo."

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = request.form['password']
        rol = 'normal'

        if os.path.exists('bd/usuarios.xlsx'):
            usuarios = pd.read_excel('bd/usuarios.xlsx')
        else:
            usuarios = pd.DataFrame(columns=['id_usuario', 'nombre', 'email', 'password_hash', 'rol', 'fecha_registro'])

        if email in usuarios['email'].values:
            return "Este correo ya está registrado."

        nuevo_id = len(usuarios) + 1
        nuevo_usuario = {
            'id_usuario': nuevo_id,
            'nombre': nombre,
            'email': email,
            'password_hash': password,
            'rol': rol,
            'fecha_registro': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        usuarios = pd.concat([usuarios, pd.DataFrame([nuevo_usuario])], ignore_index=True)
        usuarios.to_excel('bd/usuarios.xlsx', index=False)

        return redirect(url_for('home'))

    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin')
def admin_dashboard():
    if session.get('rol') == 'admin':
        productos = pd.read_excel('bd/producto.xlsx')

        # Asegurar que la columna 'eliminado' existe y es booleana
        if 'eliminado' not in productos.columns:
            productos['eliminado'] = False
        productos['eliminado'] = productos['eliminado'].fillna(False).astype(bool)

        productos = productos[productos['eliminado'] == False]
        lista_productos = productos.to_dict(orient='records')
        return render_template('admin_dashboard.html', productos=lista_productos)
    return "Acceso denegado"


@app.route('/admin/orders')
def admin_orders():
    if session.get('rol') == 'admin':
        pedidos = pd.read_excel('bd/pedidos.xlsx')
        pagos = pd.read_excel('bd/pagos.xlsx')

        lista_pedidos = pedidos.to_dict(orient='records')
        lista_pagos = pagos.to_dict(orient='records')

        return render_template('admin_orders.html',
                               pedidos=lista_pedidos,
                               pagos=lista_pagos)
    return "Acceso denegado"

@app.route('/admin/agregar_producto', methods=['POST'])
def agregar_producto():
    if session.get('rol') == 'admin':
        productos = pd.read_excel('bd/producto.xlsx')

        nuevo_id = len(productos) + 1
        nuevo_producto = {
            'id_producto': nuevo_id,
            'nombre': request.form['nombre'],
            'descripcion': request.form['descripcion'],
            'precio': float(request.form['precio']),
            'stock': int(request.form['stock']),
            'id_categoria': 1  # Puedes ajustar esto si manejas categorías
        }

        productos = pd.concat([productos, pd.DataFrame([nuevo_producto])], ignore_index=True)
        productos.to_excel('bd/producto.xlsx', index=False)

        # Registrar acción en registros.xlsx
        if os.path.exists('bd/registros.xlsx'):
            registros = pd.read_excel('bd/registros.xlsx')
        else:
            registros = pd.DataFrame(columns=['id_registro', 'id_usuario', 'accion', 'fecha_accion'])

        nuevo_registro = {
            'id_registro': len(registros) + 1,
            'id_usuario': session['usuario'],
            'accion': f"Agregó producto: {request.form['nombre']}",
            'fecha_accion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        registros = pd.concat([registros, pd.DataFrame([nuevo_registro])], ignore_index=True)
        registros.to_excel('bd/registros.xlsx', index=False)

        return redirect(url_for('admin_dashboard'))
    return "Acceso denegado"

@app.route('/admin/logs', methods=['GET', 'POST'])
def admin_logs():
    if session.get('rol') != 'admin':
        return "Acceso denegado"

    registros = pd.read_excel('bd/registros.xlsx') if os.path.exists('bd/registros.xlsx') else pd.DataFrame(columns=['id_registro', 'id_usuario', 'accion', 'fecha_accion'])

    if request.method == 'POST':
        usuario = request.form.get('usuario')
        fecha = request.form.get('fecha')

        if usuario:
            registros = registros[registros['id_usuario'].astype(str).str.contains(usuario, case=False, na=False)]
        if fecha:
            registros = registros[registros['fecha_accion'].astype(str).str.startswith(fecha)]

    registros = registros.to_dict(orient='records')
    return render_template('admin_logs.html', registros=registros)


#admin dashboard
from flask import flash

@app.route('/admin/imagen/<int:id_producto>', methods=['POST'])
def subir_imagen(id_producto):
    if session.get('rol') != 'admin':
        return "Acceso denegado"

    imagen = request.files.get('imagen')
    if imagen:
        # Validar extensión
        extensiones_permitidas = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        extension = imagen.filename.rsplit('.', 1)[-1].lower()
        if extension not in extensiones_permitidas:
            flash("Formato de imagen no permitido. Usa .jpg, .jpeg, .png, .gif o .webp.")
            return redirect(url_for('admin_dashboard'))

        # Validar tamaño (máx. 2MB)
        imagen.seek(0, os.SEEK_END)
        tamaño = imagen.tell()
        imagen.seek(0)
        if tamaño > 2 * 1024 * 1024:
            flash("La imagen excede el tamaño máximo permitido (2MB).")
            return redirect(url_for('admin_dashboard'))

        # Guardar imagen
        carpeta_destino = os.path.join('static', 'img')
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta = os.path.join(carpeta_destino, f'producto_{id_producto}.jpg')
        imagen.save(ruta)

        # Registrar ruta en el Excel
        productos = pd.read_excel('bd/producto.xlsx')
        idx = productos[productos['id_producto'] == id_producto].index
        if not idx.empty:
            productos.at[idx[0], 'imagen_url'] = f'img/producto_{id_producto}.jpg'
            productos.to_excel('bd/producto.xlsx', index=False)

        flash("Imagen subida correctamente.")

    else:
        flash("No se seleccionó ninguna imagen.")

    return redirect(url_for('admin_dashboard'))



@app.route('/admin/eliminar/<int:id_producto>', methods=['POST'])
def eliminar_producto(id_producto):
    if session.get('rol') != 'admin':
        return "Acceso denegado"

    productos = pd.read_excel('bd/producto.xlsx')

    # Asegurar que la columna 'eliminado' existe y es del tipo correcto
    if 'eliminado' not in productos.columns:
        productos['eliminado'] = False
    productos['eliminado'] = productos['eliminado'].astype(object)

    idx = productos[productos['id_producto'] == id_producto].index

    if not idx.empty:
        productos.at[idx[0], 'eliminado'] = True
        productos.to_excel('bd/producto.xlsx', index=False)

        # Registrar acción
        nombre = productos.at[idx[0], 'nombre']
        if os.path.exists('bd/registros.xlsx'):
            registros = pd.read_excel('bd/registros.xlsx')
        else:
            registros = pd.DataFrame(columns=['id_registro', 'id_usuario', 'accion', 'fecha_accion'])

        nuevo_registro = {
            'id_registro': len(registros) + 1,
            'id_usuario': session['usuario'],
            'accion': f"Eliminó producto: {nombre} (ID {id_producto})",
            'fecha_accion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        registros = pd.concat([registros, pd.DataFrame([nuevo_registro])], ignore_index=True)
        registros.to_excel('bd/registros.xlsx', index=False)

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/eliminar_definitivo/<int:id_producto>', methods=['POST'])
def eliminar_definitivo(id_producto):
    if session.get('rol') != 'admin':
        return "Acceso denegado"

    productos = pd.read_excel('bd/producto.xlsx')
    idx = productos[productos['id_producto'] == id_producto].index

    if not idx.empty:
        nombre = productos.at[idx[0], 'nombre']
        productos = productos.drop(index=idx)
        productos.to_excel('bd/producto.xlsx', index=False)

        # Registrar acción
        if os.path.exists('bd/registros.xlsx'):
            registros = pd.read_excel('bd/registros.xlsx')
        else:
            registros = pd.DataFrame(columns=['id_registro', 'id_usuario', 'accion', 'fecha_accion'])

        nuevo_registro = {
            'id_registro': len(registros) + 1,
            'id_usuario': session['usuario'],
            'accion': f"Eliminó definitivamente el producto: {nombre} (ID {id_producto})",
            'fecha_accion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        registros = pd.concat([registros, pd.DataFrame([nuevo_registro])], ignore_index=True)
        registros.to_excel('bd/registros.xlsx', index=False)

    return redirect(url_for('admin_papelera'))

@app.route('/admin/restaurar/<int:id_producto>', methods=['POST'])
def restaurar_producto(id_producto):
    if session.get('rol') != 'admin':
        return "Acceso denegado"

    productos = pd.read_excel('bd/producto.xlsx')
    idx = productos[productos['id_producto'] == id_producto].index

    if not idx.empty:
        productos['eliminado'] = productos['eliminado'].astype(object)
        productos.at[idx[0], 'eliminado'] = False
        productos.to_excel('bd/producto.xlsx', index=False)

        # Registrar restauración
        nombre = productos.at[idx[0], 'nombre']
        if os.path.exists('bd/registros.xlsx'):
            registros = pd.read_excel('bd/registros.xlsx')
        else:
            registros = pd.DataFrame(columns=['id_registro', 'id_usuario', 'accion', 'fecha_accion'])

        nuevo_registro = {
            'id_registro': len(registros) + 1,
            'id_usuario': session['usuario'],
            'accion': f"Restauró producto: {nombre} (ID {id_producto})",
            'fecha_accion': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        registros = pd.concat([registros, pd.DataFrame([nuevo_registro])], ignore_index=True)
        registros.to_excel('bd/registros.xlsx', index=False)

    return redirect(url_for('admin_papelera'))


@app.route('/admin/papelera')
def admin_papelera():
    if session.get('rol') != 'admin':
        return "Acceso denegado"

    productos = pd.read_excel('bd/producto.xlsx')

    # Asegurar que la columna 'eliminado' existe y es del tipo correcto
    if 'eliminado' not in productos.columns:
        productos['eliminado'] = False
    productos['eliminado'] = productos['eliminado'].astype(object)

    eliminados = productos[productos['eliminado'] == True].to_dict(orient='records')
    return render_template('admin_papelera.html', productos=eliminados)


@app.route('/admin/editar/<int:id_producto>', methods=['GET', 'POST'])
def editar_producto(id_producto):
    if session.get('rol') != 'admin':
        return "Acceso denegado"

    productos = pd.read_excel('bd/producto.xlsx')
    producto = productos[productos['id_producto'] == id_producto]

    if producto.empty:
        return "Producto no encontrado."

    if request.method == 'POST':
        idx = producto.index[0]
        productos.at[idx, 'nombre'] = request.form['nombre']
        productos.at[idx, 'descripcion'] = request.form['descripcion']
        productos.at[idx, 'precio'] = float(request.form['precio'])
        productos.at[idx, 'stock'] = int(request.form['stock'])
        productos.to_excel('bd/producto.xlsx', index=False)
        return redirect(url_for('admin_dashboard'))

    return render_template('editar_producto.html', producto=producto.iloc[0])

    # Filtros por usuario y fecha
    usuario = request.form.get('usuario')
    fecha = request.form.get('fecha')

    if usuario:
        registros = registros[registros['id_usuario'].astype(str).str.contains(usuario, case=False, na=False)]
    if fecha:
        registros = registros[registros['fecha_accion'].astype(str).str.startswith(fecha)]

    registros = registros.to_dict(orient='records')
    return render_template('admin_logs.html', registros=registros)

@app.route('/user')
def user_dashboard():
    if session.get('rol') == 'normal':
        productos = pd.read_excel('bd/producto.xlsx')

        if 'eliminado' not in productos.columns:
            productos['eliminado'] = False
        productos['eliminado'] = productos['eliminado'].fillna(False).astype(bool)

        productos = productos[productos['eliminado'] == False]
        lista_productos = productos.to_dict(orient='records')
        return render_template('user_dashboard.html', productos=lista_productos)
    return "Acceso denegado"


@app.route('/add_to_cart/<int:id_producto>', methods=['POST'])
def add_to_cart(id_producto):
    productos = pd.read_excel('bd/producto.xlsx')
    detalle_pedido = pd.read_excel('bd/detalle_pedido.xlsx')

    cantidad = int(request.form['cantidad'])
    producto = productos[productos['id_producto'] == id_producto].iloc[0]

    subtotal = producto['precio'] * cantidad

    nuevo_id = len(detalle_pedido) + 1
    nuevo_pedido = {
        'id_detalle': nuevo_id,
        'id_pedido': 1,  # por ahora pedido fijo
        'id_producto': id_producto,
        'cantidad': cantidad,
        'subtotal': subtotal
    }

    detalle_pedido = pd.concat([detalle_pedido, pd.DataFrame([nuevo_pedido])], ignore_index=True)
    detalle_pedido.to_excel('bd/detalle_pedido.xlsx', index=False)

    return redirect(url_for('user_dashboard'))

@app.route('/cart')
def cart():
    if session.get('rol') == 'normal':
        detalle_pedido = pd.read_excel('bd/detalle_pedido.xlsx')
        carrito = detalle_pedido.to_dict(orient='records')
        total = detalle_pedido['subtotal'].sum() if not detalle_pedido.empty else 0
        return render_template('cart.html', carrito=carrito, total=total)
    return "Acceso denegado"

@app.route('/pay', methods=['POST'])
def pay():
    if session.get('rol') == 'normal':
        detalle_pedido = pd.read_excel('bd/detalle_pedido.xlsx')
        total = detalle_pedido['subtotal'].sum() if not detalle_pedido.empty else 0

        if total == 0:
            return "No hay productos en el carrito."

        if os.path.exists('bd/pagos.xlsx'):
            pagos = pd.read_excel('bd/pagos.xlsx')
        else:
            pagos = pd.DataFrame(columns=['id_pago','id_pedido','monto','metodo_pago','fecha_pago','estado_pago'])

        if os.path.exists('bd/pedidos.xlsx'):
            pedidos = pd.read_excel('bd/pedidos.xlsx')
        else:
            pedidos = pd.DataFrame(columns=['id_pedido','id_usuario','fecha_pedido','estado'])

        nuevo_id_pedido = len(pedidos) + 1
        nuevo_pedido = {
            'id_pedido': nuevo_id_pedido,
            'id_usuario': session['usuario'],
            'fecha_pedido': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'estado': 'pagado'
        }
        pedidos = pd.concat([pedidos, pd.DataFrame([nuevo_pedido])], ignore_index=True)
        pedidos.to_excel('bd/pedidos.xlsx', index=False)

        nuevo_id_pago = len(pagos) + 1
        nuevo_pago = {
            'id_pago': nuevo_id_pago,
            'id_pedido': nuevo_id_pedido,
            'monto': total,
            'metodo_pago': request.form['metodo_pago'],
            'fecha_pago': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'estado_pago': 'aprobado'
        }
        pagos = pd.concat([pagos, pd.DataFrame([nuevo_pago])], ignore_index=True)
        pagos.to_excel('bd/pagos.xlsx', index=False)

        return f"Pedido #{nuevo_id_pedido} creado y pago registrado con éxito. Total: {total}"
    return "Acceso denegado"

@app.route('/admin/charts')
def admin_charts():
    if session.get('rol') == 'admin':
        detalle = pd.read_excel('bd/detalle_pedido.xlsx')
        productos = pd.read_excel('bd/producto.xlsx')
        pedidos = pd.read_excel('bd/pedidos.xlsx')

        ventas_por_producto = detalle.groupby('id_producto')['cantidad'].sum().reset_index()
        ventas_por_producto = pd.merge(ventas_por_producto, productos[['id_producto','nombre']], on='id_producto')

        pedidos['fecha_pedido'] = pd.to_datetime(pedidos['fecha_pedido'])
        pedidos['mes'] = pedidos['fecha_pedido'].dt.to_period('M').astype(str)
        ventas_por_mes = detalle.groupby('id_pedido')['subtotal'].sum().reset_index()
        ventas_por_mes = pd.merge(ventas_por_mes, pedidos[['id_pedido','mes']], on='id_pedido')
        ventas_por_mes = ventas_por_mes.groupby('mes')['subtotal'].sum().reset_index()

        return render_template('admin_charts.html',
                               ventas_producto=ventas_por_producto.to_dict(orient='records'),
                               ventas_mes=ventas_por_mes.to_dict(orient='records'))
    return "Acceso denegado"

if __name__ == '__main__':
    app.run(debug=True)