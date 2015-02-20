=========================================================
Stock. Generación de pedidos de compra a partir de ventas
=========================================================

Genera pedidos de compra a partir de las ventas de un determinado periodo.

Funcionamiento
==============

Para acceder al asistente abra el menú Compras > Solicitudes de compra > Crear solicitudes de compra desde ventas.

El asistente muestra los siguientes campos:
  * Días para calcular la media: Número de días sobre los que se desea realizar
    el cálculo de media de productos vendidos.
  * Mínimo de días: Mínimo número de días para los que se desea tener
    existencias.
  * Cantidad media: Filtra los productos que no llegan a la cantidad media de
    productos vendidos para el período que se ha indicado anteriormente.
  * Almacén: El almacén para el que se realizará el cálculo.

El asistente toma el primer proveedor de la lista de proveedores que tiene cada
producto que cumple las condiciones de venta indicadas en el asistente, y
modifica o crea un pedido de compra para el mismo, poniendo la cantidad
resultante de la siguiente operación redondeado al entero superior:

                              Q = M · D - S

Donde:

  * Q: es la cantidad de producto que propone comprar,
  * M: es la media de productos vendidos en el periodo indicado,
  * D: es el mínimo de días para los cuales desea tener existencias, y
  * S: son las existencias virtuales en la actualidad.

Para que el asistente cree la solicitud de compra de un producto en concreto, éste
debe tener asignado como mínimo un proveedor en la lista de proveedores
(pestaña proveedores de la ficha del producto).

Cuando hay más de un proveedor en la lista de proveedores de un determinado
producto, el asistente toma el primero de la lista.

Una vez finaliza el cálculo, se listaran todas las solicitudes de compra en borrador,
tanto las que se han generado con el asistente como las solicitudes de compra
que ya estaban creadas. Ahora es el paso de crear solicitudes de compra a compras
mediante el asistente.
