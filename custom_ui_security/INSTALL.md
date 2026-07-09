# Guía de Instalación Rápida - Custom UI Security

## ✅ Paso 1: Verificar que el módulo está en el directorio correcto

```bash
ls -la /opt/odoo18/odoo18-custom-addons/custom_ui_security/
```

**Resultado esperado:** Debes ver todos los archivos del módulo con propietario `odoo18:odoo18`

---

## ✅ Paso 2: Reiniciar Odoo

```bash
sudo systemctl restart odoo18
sudo systemctl status odoo18
```

**Verificar que Odoo arrancó correctamente**

---

## ✅ Paso 3: Actualizar lista de aplicaciones en Odoo

1. Abrir Odoo en el navegador
2. Ir a **Aplicaciones**
3. Activar **Modo Desarrollador**:
   - Click en **Configuración** (menú superior)
   - Scroll hasta el final
   - Click en **Activar modo desarrollador**
4. Volver a **Aplicaciones**
5. Click en el menú **⋮** (tres puntos)
6. Seleccionar **Actualizar lista de aplicaciones**
7. Confirmar la actualización

---

## ✅ Paso 4: Instalar el módulo

1. En **Aplicaciones**, usar el buscador
2. Escribir: **Custom UI Security**
3. Click en **Instalar**

**Esperar a que termine la instalación (puede tomar unos segundos)**

---

## ✅ Paso 5: Verificar instalación

### Verificar que el grupo se creó:

1. Ir a: **Configuración → Usuarios y Compañías → Grupos**
2. Buscar la categoría: **UI Security**
3. Debe aparecer el grupo: **Puede ver costos de producto**

### Verificar que las vistas se heredaron:

1. Ir a: **Inventario → Productos → Productos**
2. Abrir cualquier producto
3. Si eres **Administrador**, debes ver el campo **Costo**
4. Esto es correcto porque los administradores tienen el grupo automáticamente

---

## ✅ Paso 6: Probar la funcionalidad

### Crear un usuario de prueba SIN el grupo:

1. Ir a: **Configuración → Usuarios y Compañías → Usuarios**
2. Click en **Crear**
3. Completar:
   - **Nombre:** Test Vendedor
   - **Login:** testvendedor
   - **Contraseña:** (establecer una contraseña)
4. Pestaña **Derechos de acceso**:
   - **Ventas:** Seleccionar "Vendedor"
   - **Inventario:** Seleccionar "Usuario"
5. Pestaña **Otros**:
   - En sección **UI Security**
   - ☐ **NO** marcar "Puede ver costos de producto"
6. **Guardar**

### Probar con el usuario de prueba:

1. **Logout** de Odoo
2. **Login** con:
   - Usuario: `testvendedor`
   - Contraseña: (la que estableciste)
3. Ir a: **Ventas → Productos → Productos**
4. Abrir cualquier producto
5. **Resultado esperado:** El campo **Costo** NO debe aparecer ✅

### Probar con administrador:

1. **Logout**
2. **Login** con tu usuario administrador
3. Ir a productos
4. **Resultado esperado:** El campo **Costo** SÍ debe aparecer ✅

---

## ✅ Paso 7: Asignar el grupo a usuarios que lo necesiten

Para cada usuario que **debe ver costos**:

1. Ir a: **Configuración → Usuarios y Compañías → Usuarios**
2. Seleccionar el usuario
3. Pestaña **Otros**
4. Sección **UI Security**
5. ☑ Marcar: **Puede ver costos de producto**
6. **Guardar**

---

## 🚨 Solución de Problemas

### Problema: No aparece el módulo en Aplicaciones

**Solución:**

```bash
# Verificar que está en el directorio correcto
ls /opt/odoo18/odoo18-custom-addons/ | grep custom_ui_security

# Verificar permisos
sudo chown -R odoo18:odoo18 /opt/odoo18/odoo18-custom-addons/custom_ui_security

# Reiniciar Odoo
sudo systemctl restart odoo18

# Actualizar lista de aplicaciones desde línea de comandos (opcional)
sudo -u odoo18 /opt/odoo18/odoo18-venv/bin/python3 /opt/odoo18/odoo/odoo-bin \
  -d tu_base_de_datos \
  --addons-path=/opt/odoo18/odoo/addons,/opt/odoo18/odoo18-custom-addons \
  --update=base \
  --stop-after-init
```

### Problema: Error al instalar el módulo

**Verificar logs:**

```bash
sudo tail -f /var/log/odoo18/odoo.log
```

**Buscar errores relacionados con `custom_ui_security`**

### Problema: El campo Costo sigue visible para usuarios sin grupo

**Verificaciones:**

1. Verificar que el usuario **NO** tiene el grupo:
   - Configuración → Usuarios → [Usuario]
   - Pestaña **Otros** → Sección **UI Security**
   - Debe estar **desmarcado**

2. Verificar que el usuario **NO** es administrador:
   - Los administradores tienen todos los grupos automáticamente

3. Hacer **logout y login** nuevamente con el usuario

4. Si persiste, verificar la herencia de vista:
   - Ir al producto
   - Activar modo desarrollador
   - Click en **Debug** (icono de bug) → **Ver Metadatos**
   - Click en **Vista XML**
   - Buscar: `standard_price`
   - Debe tener: `groups="custom_ui_security.group_view_product_cost"`

---

## 📊 Verificación de Estado

### Checklist de instalación exitosa:

- ✅ Módulo aparece en lista de Aplicaciones
- ✅ Instalación sin errores
- ✅ Grupo "Puede ver costos de producto" existe
- ✅ Administradores ven el campo Costo
- ✅ Usuarios sin grupo NO ven el campo Costo
- ✅ Usuarios con grupo asignado SÍ ven el campo Costo

---

## 🚀 Siguientes Pasos

Una vez instalado y probado:

1. **Asignar el grupo** a los usuarios correspondientes
2. **Documentar** qué usuarios deben tener acceso
3. **Evaluar** si necesitas activar la Fase 2 para reglas dinámicas
4. **Leer** el [README.md](README.md) para conocer todas las capacidades

---

## 📞 Soporte

Si tienes problemas, revisa:

1. **Logs de Odoo:** `/var/log/odoo18/odoo.log`
2. **README.md:** Documentación completa
3. **Código fuente:** Todos los archivos tienen comentarios explicativos

---

## 📝 Notas Finales

- Este módulo **solo oculta visualmente** el campo Costo
- **NO modifica** la lógica de negocio
- **NO afecta** cálculos contables ni de inventario
- Para **seguridad real** de datos, combinar con `ir.rule` o validaciones Python

---

**¡Instalación completada!** 🎉
