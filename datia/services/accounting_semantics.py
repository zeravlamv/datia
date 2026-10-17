"""Definiciones semánticas de las tablas contables de Sage y su copia local."""

from django.db import connection

from datia.models.semantic import DataField, DataSource


def _row(field_name, data_type, usage, business_name, description, is_key=False):
    return {
        "field_name": field_name,
        "data_type": data_type,
        "usage_type": usage,
        "business_name": business_name,
        "description": description,
        "is_key": is_key,
    }


_NO = "En Sage, -1 significa sí y 0 significa no."

ACUMULADOS = [
    _row("CodigoEmpresa", "smallint", "dimension", "Empresa", "Empresa Sage a la que pertenece el acumulado.", True),
    _row("Ejercicio", "smallint", "dimension", "Ejercicio", "Año contable del acumulado.", True),
    _row("CodigoCuenta", "varchar", "dimension", "Cuenta contable", "Código de la cuenta del plan a la que pertenecen el debe y el haber.", True),
    _row("CodigoCanal", "varchar", "data", "Canal", "Canal analítico del acumulado. No forma parte de la copia local usada para entrenar."),
    _row("NumeroPeriodo", "smallint", "dimension", "Periodo", "Período contable, del 1 al 12. Es un número de mes, no una fecha.", True),
    _row("IdDelegacion", "varchar", "data", "Delegacion", "Delegación del acumulado. No forma parte de la copia local usada para entrenar."),
    _row("DebeAcum", "decimal", "metric", "Debe acumulado", "Suma del debe de la cuenta en el período."),
    _row("HaberAcum", "decimal", "metric", "Haber acumulado", "Suma del haber de la cuenta en el período."),
    _row("DebePresu", "decimal", "metric", "Debe presupuestado", "Importe de presupuesto cargado en el debe de la cuenta y el período."),
    _row("HaberPresu", "decimal", "metric", "Haber presupuestado", "Importe de presupuesto cargado en el haber de la cuenta y el período."),
    _row("TipoPlanCuenta", "smallint", "data", "Tipo de plan", "Tipo de plan de cuentas de Sage. No forma parte de la copia local usada para entrenar."),
    _row("CodigoCuentaANT_", "varchar", "data", "Cuenta anterior", "Código que tenía la cuenta antes del último cambio de codificación."),
]

PLAN = [
    _row("CodigoEmpresa", "smallint", "dimension", "Empresa", "Empresa Sage a la que pertenece la cuenta.", True),
    _row("CodigoCuenta", "varchar", "dimension", "Codigo cuenta", "Código de la cuenta contable. Es la clave con la que se enlazan asientos, acumulados y efectos.", True),
    _row("Cuenta", "varchar", "dimension", "Nombre cuenta", "Título o descripción de la cuenta contable."),
    _row("ClienteOProveedor", "varchar", "data", "Cliente o proveedor", "Indica si la cuenta es de cliente, de proveedor o de otro tipo. No está en la copia local del plan."),
    _row("CodigoDivisa", "varchar", "data", "Divisa", "Divisa de la cuenta cuando no opera en la divisa habitual de la empresa."),
    _row("IndicadorProrrata", "smallint", "data", "Indicador prorrata", "Marca si la cuenta interviene en el cálculo de la prorrata de IVA."),
    _row("IdCuentaGuid", "uniqueidentifier", "data", "Identificador cuenta", "Identificador interno de Sage para la cuenta."),
    _row("Bloqueo", "smallint", "data", "Cuenta bloqueada", f"Indica si la cuenta está bloqueada y no admite nuevos apuntes. {_NO}"),
]

MOVIMIENTOS = [
    _row("MovPosicion", "uniqueidentifier", "data", "Identificador apunte", "Identificador único de la línea del asiento.", True),
    _row("Ejercicio", "smallint", "dimension", "Ejercicio", "Año contable del apunte.", True),
    _row("CodigoEmpresa", "smallint", "dimension", "Empresa", "Empresa Sage del apunte.", True),
    _row("TipoMov", "smallint", "data", "Tipo de movimiento", "Tipo de movimiento que Sage asigna a la línea del diario."),
    _row("Asiento", "int", "dimension", "Numero de asiento", "Número del asiento dentro del diario y el ejercicio."),
    _row("CargoAbono", "varchar", "dimension", "Debe o haber", "Sentido del apunte: D es debe y H es haber."),
    _row("CodigoCuenta", "varchar", "dimension", "Cuenta contable", "Cuenta del plan en la que se anota el apunte.", True),
    _row("Contrapartida", "varchar", "dimension", "Contrapartida", "Cuenta de contrapartida informada en el apunte."),
    _row("FechaAsiento", "datetime", "date", "Fecha asiento", "Fecha contable del asiento."),
    _row("TipoDocumento", "varchar", "dimension", "Tipo de documento", "Clase de documento que originó el apunte, por ejemplo factura o efecto."),
    _row("DocumentoConta", "varchar", "data", "Documento contable", "Número o referencia del documento contable asociado al apunte."),
    _row("Comentario", "varchar", "data", "Comentario", "Texto libre del apunte."),
    _row("ImporteAsiento", "decimal", "metric", "Importe asiento", "Importe del apunte en la divisa de la empresa. El sentido lo da el campo Debe o haber."),
    _row("StatusAcumulacion", "smallint", "data", "Acumulado", f"Indica si el apunte ya se ha volcado a los acumulados de la cuenta. {_NO}"),
    _row("CodigoDiario", "smallint", "dimension", "Diario", "Código del diario en el que está registrado el asiento."),
    _row("CodigoCanal", "varchar", "dimension", "Canal", "Canal analítico del apunte."),
    _row("CodigoActividad", "varchar", "data", "Actividad", "Actividad analítica del apunte."),
    _row("Previsiones", "varchar", "data", "Prevision", "Marca si el apunte es una previsión y no un movimiento real."),
    _row("FechaVencimiento", "datetime", "date", "Fecha vencimiento", "Fecha de vencimiento cuando el apunte está ligado a un efecto."),
    _row("NumeroPeriodo", "smallint", "dimension", "Periodo", "Período contable del apunte, del 1 al 12."),
    _row("StatusConciliacion", "smallint", "data", "Conciliado", f"Indica si el apunte está conciliado con banca. {_NO}"),
    _row("StatusSaldo", "smallint", "data", "Entra en saldo", f"Indica si el apunte entra en el cálculo del saldo de la cuenta. {_NO}"),
    _row("StatusTraspaso", "smallint", "data", "Traspasado", f"Indica si el apunte ya se traspasó a otro proceso de Sage. {_NO}"),
    _row("CodigoUsuario", "smallint", "data", "Usuario", "Usuario de Sage que grabó el apunte."),
    _row("FechaGrabacion", "datetime", "date", "Fecha grabacion", "Fecha y hora en que se grabó el apunte."),
    _row("TipoEntrada", "varchar", "data", "Tipo de entrada", "Forma en que entró el apunte: manual, factura, cartera u otro proceso."),
    _row("StatusImpagado", "smallint", "data", "Impagado", f"Indica si el apunte corresponde a un efecto impagado. {_NO}"),
    _row("Diseño", "int", "data", "Diseno de entrada", "Diseño de entrada de asientos usado al grabar el movimiento."),
    _row("CodigoDepartamento", "varchar", "dimension", "Departamento", "Departamento analítico del apunte."),
    _row("CodigoSeccion", "varchar", "data", "Seccion", "Sección analítica del apunte."),
    _row("CodigoDivisa", "varchar", "data", "Divisa", "Divisa original del apunte cuando no es la de la empresa."),
    _row("ImporteCambio", "decimal", "metric", "Importe de cambio", "Diferencia de cambio asociada al apunte."),
    _row("ImporteDivisa", "decimal", "metric", "Importe en divisa", "Importe del apunte en la divisa original."),
    _row("FactorCambio", "decimal", "data", "Factor de cambio", "Tipo de cambio aplicado para pasar el importe a la divisa de la empresa."),
    _row("CodigoConcepto", "smallint", "dimension", "Concepto", "Concepto contable del apunte."),
    _row("CodigoConciliacion", "int", "data", "Codigo conciliacion", "Número del grupo de conciliación bancaria al que pertenece el apunte."),
    _row("FechaConciliacion", "datetime", "date", "Fecha conciliacion", "Fecha en que el apunte quedó conciliado."),
    _row("CodigoProyecto", "varchar", "data", "Proyecto", "Proyecto analítico imputado al apunte."),
    _row("StatusAnalitica", "smallint", "data", "Analitica", f"Indica si el apunte tiene distribución analítica. {_NO}"),
    _row("LibreN1", "int", "data", "Libre numerico 1", "Campo numérico libre definido por la empresa."),
    _row("LibreN2", "int", "data", "Libre numerico 2", "Segundo campo numérico libre definido por la empresa."),
    _row("LibreA1", "varchar", "data", "Libre texto 1", "Campo de texto libre definido por la empresa."),
    _row("LibreA2", "varchar", "data", "Libre texto 2", "Segundo campo de texto libre definido por la empresa."),
    _row("IdDelegacion", "varchar", "dimension", "Delegacion", "Delegación a la que se imputa el apunte."),
    _row("EnEuros_", "smallint", "data", "En euros", f"Indica si el importe está expresado en euros. {_NO}"),
    _row("StatusExportado", "smallint", "data", "Exportado", f"Indica si el apunte ya se exportó a otro sistema. {_NO}"),
    _row("DocumentoConciliacion", "varchar", "data", "Documento conciliacion", "Referencia del documento bancario con el que se concilió el apunte."),
    _row("OrdenMovimientos", "int", "data", "Orden del apunte", "Orden de la línea dentro del asiento."),
    _row("ForzarSaldoVivo", "smallint", "data", "Forzar saldo vivo", f"Fuerza que el apunte se tenga en cuenta en el saldo vivo. {_NO}"),
    _row("MovCartera", "uniqueidentifier", "data", "Efecto de cartera", "Identificador del efecto de cartera que generó este apunte, si existe."),
    _row("ControlBorrado", "smallint", "data", "Control de borrado", f"Marca interna de borrado lógico del apunte. {_NO}"),
    _row("AgrupacionCuadre", "int", "data", "Agrupacion de cuadre", "Grupo usado para cuadrar el apunte con su contrapartida."),
    _row("IdDiseñoEntrada", "uniqueidentifier", "data", "Identificador diseno", "Identificador del diseño de entrada de asientos."),
    _row("NivelIntegridad", "smallint", "data", "Nivel de integridad", "Nivel de control de integridad que Sage aplica al apunte."),
    _row("sysTraspasoLWG", "smallint", "data", "Traspaso interno", "Marca interna de Sage para el traspaso entre módulos."),
    _row("EmpresaOrigen", "smallint", "data", "Empresa origen", "Empresa desde la que se originó el apunte cuando hay intercompañía."),
    _row("TipoPlanCuenta", "smallint", "data", "Tipo de plan", "Tipo de plan de cuentas usado en el apunte."),
    _row("CodigoCuentaANT_", "varchar", "data", "Cuenta anterior", "Código de la cuenta antes del último cambio de codificación."),
    _row("ContrapartidaANT_", "varchar", "data", "Contrapartida anterior", "Código de la contrapartida antes del último cambio de codificación."),
    _row("Metalico347", "smallint", "data", "Metalico 347", f"Indica si el apunte se declara como metálico en el modelo 347. {_NO}"),
    _row("IdAsientoExterno", "varchar", "data", "Asiento externo", "Identificador del asiento en el sistema que lo originó."),
    _row("CodigoElemento", "varchar", "data", "Elemento", "Elemento de inmovilizado u otra clave asociada al apunte."),
]

CARTERA = [
    _row("CodigoEmpresa", "smallint", "dimension", "Empresa", "Empresa Sage del efecto.", True),
    _row("IdDelegacion", "varchar", "data", "Delegacion", "Delegación a la que pertenece el efecto."),
    _row("MovCartera", "uniqueidentifier", "data", "Identificador efecto", "Identificador único del efecto en la cartera.", True),
    _row("MovPosicion", "uniqueidentifier", "data", "Apunte contable", "Identificador del apunte de diario ligado al efecto."),
    _row("TipoMov", "smallint", "data", "Tipo de movimiento", "Tipo de movimiento de cartera que Sage asigna al efecto."),
    _row("Prevision", "varchar", "dimension", "Cobro o pago", "Sentido del efecto: C es cobro y P es pago."),
    _row("NumeroEfecto", "int", "data", "Numero de efecto", "Número del efecto dentro de la cartera."),
    _row("NumeroOrdenEfecto", "smallint", "data", "Orden del efecto", "Orden del efecto cuando una factura se divide en varios vencimientos."),
    _row("NumEfectoAgrupacion_", "uniqueidentifier", "data", "Efecto de agrupacion", "Efecto resultante cuando este vencimiento se agrupó con otros."),
    _row("NumEfectoDivision_", "uniqueidentifier", "data", "Efecto de division", "Efecto del que procede este vencimiento si se dividió."),
    _row("NumeroRemesa", "int", "data", "Numero de remesa", "Número de la remesa bancaria en la que se incluyó el efecto."),
    _row("NumeroTalon", "int", "data", "Numero de talon", "Número de talón o pagaré asociado al efecto."),
    _row("Aceptado", "smallint", "data", "Aceptado", f"Indica si el efecto está aceptado. {_NO}"),
    _row("Domiciliado", "smallint", "data", "Domiciliado", f"Indica si el efecto está domiciliado en una cuenta bancaria. {_NO}"),
    _row("Timbres", "smallint", "data", "Timbres", f"Indica si el efecto lleva timbres. {_NO}"),
    _row("StatusBorrado", "smallint", "data", "Borrado", f"Borrado lógico del efecto. La sincronización de cartera no copia los efectos borrados. {_NO}"),
    _row("StatusContabilizado", "smallint", "data", "Contabilizado", f"Indica si el efecto ya generó su asiento. {_NO}"),
    _row("StatusAnalitica", "smallint", "data", "Analitica", f"Indica si el efecto tiene distribución analítica. {_NO}"),
    _row("StatusRemesado", "smallint", "data", "Remesado", f"Indica si el efecto ya se incluyó en una remesa. La copia local lo usa para marcar el efecto como cobrado. {_NO}"),
    _row("StatusRecibo", "smallint", "data", "Recibo emitido", f"Indica si se emitió el recibo del efecto. {_NO}"),
    _row("StatusRiesgo", "smallint", "data", "En riesgo", f"Indica si el efecto está dentro del período de riesgo bancario. {_NO}"),
    _row("StatusImpagado", "smallint", "data", "Impagado", f"Indica si el efecto está marcado como impagado. {_NO}"),
    _row("StatusReclamacionImpagado_", "smallint", "data", "Reclamacion impagado", f"Indica si el impagado ya se reclamó. {_NO}"),
    _row("StatusExportado", "smallint", "data", "Exportado", f"Indica si el efecto se exportó a otro sistema. {_NO}"),
    _row("StatusListadoAgrupacion_", "smallint", "data", "Listado agrupacion", f"Indica si el efecto salió en el listado de agrupación. {_NO}"),
    _row("StatusListadoDivision_", "smallint", "data", "Listado division", f"Indica si el efecto salió en el listado de división. {_NO}"),
    _row("StatusCSB", "smallint", "data", "Norma bancaria", f"Indica si el efecto se generó en el fichero de la norma bancaria. {_NO}"),
    _row("StatusReclamado", "smallint", "data", "Reclamado", f"Indica si el efecto se reclamó al cliente o proveedor. {_NO}"),
    _row("StatusRecibido", "smallint", "data", "Recibido", f"Indica si el efecto se dio por recibido. {_NO}"),
    _row("Ejercicio", "smallint", "dimension", "Ejercicio", "Año contable del efecto.", True),
    _row("SerieFactura", "varchar", "data", "Serie de factura", "Serie de la factura que originó el efecto."),
    _row("Factura", "int", "data", "Numero de factura", "Número de la factura que originó el efecto."),
    _row("DocumentoConta", "varchar", "data", "Documento contable", "Documento contable asociado al efecto."),
    _row("Comentario", "varchar", "data", "Comentario", "Texto libre del efecto."),
    _row("CargoEmpresaOcliente", "varchar", "data", "Cargo empresa o cliente", "Indica si los gastos del efecto los asume la empresa o el cliente."),
    _row("CodigoClienteProveedor", "varchar", "dimension", "Cliente proveedor", "Código del cliente o del proveedor titular del efecto.", True),
    _row("CodigoCuenta", "varchar", "data", "Cuenta contable", "Cuenta del plan donde se contabiliza el efecto. No está en la copia local de cartera."),
    _row("Contrapartida", "varchar", "data", "Contrapartida", "Cuenta de contrapartida del efecto."),
    _row("CodigoDefinicion_", "varchar", "data", "Definicion", "Definición de asiento usada para contabilizar el efecto."),
    _row("CodigoDomicilioRecibo", "smallint", "data", "Domicilio del recibo", "Domicilio del cliente o proveedor al que se envía el recibo."),
    _row("CodigoComisionista", "int", "data", "Comisionista", "Comisionista asociado al efecto."),
    _row("CodigoCobrador", "int", "data", "Cobrador", "Cobrador asignado al efecto."),
    _row("CodigoCanal", "varchar", "data", "Canal", "Canal comercial del efecto."),
    _row("ClaseEfecto", "smallint", "data", "Clase de efecto", "Clase interna del efecto en Sage."),
    _row("CodigoTipoEfecto", "smallint", "data", "Codigo tipo efecto", "Código numérico del tipo de efecto."),
    _row("TipoEfecto", "varchar", "data", "Tipo de efecto", "Descripción del tipo de efecto: recibo, pagaré, transferencia u otro."),
    _row("TipoRemesa", "varchar", "data", "Tipo de remesa", "Tipo de remesa bancaria en la que entra el efecto."),
    _row("BancoRemesa", "varchar", "data", "Banco de remesa", "Banco por el que se remesa el efecto."),
    _row("CodigoBanco", "varchar", "data", "Banco", "Código del banco de la domiciliación."),
    _row("CodigoAgencia", "varchar", "data", "Agencia", "Código de la agencia de la domiciliación."),
    _row("DC", "varchar", "data", "Digito de control", "Dígito de control de la cuenta de domiciliación."),
    _row("CCC", "varchar", "data", "Cuenta bancaria", "Número de cuenta de la domiciliación."),
    _row("IBAN", "varchar", "data", "IBAN", "IBAN de la domiciliación del efecto."),
    _row("FechaEmision", "datetime", "data", "Fecha emision", "Fecha de emisión del efecto. No está en la copia local; el entrenamiento por mes usa la fecha de factura."),
    _row("FechaFactura", "datetime", "date", "Fecha factura", "Fecha de la factura que originó el efecto. En la copia local es la fecha de emisión guardada."),
    _row("FechaRemesa", "datetime", "data", "Fecha remesa", "Fecha en que el efecto se incluyó en la remesa."),
    _row("FechaVencimiento", "datetime", "date", "Fecha vencimiento", "Fecha de vencimiento del efecto."),
    _row("FechaInicioRiesgo", "datetime", "data", "Inicio de riesgo", "Fecha en que empieza el riesgo bancario del efecto."),
    _row("FechaFinalRiesgo", "datetime", "data", "Fin de riesgo", "Fecha en que termina el riesgo bancario del efecto."),
    _row("FechaCobroEfecto_", "datetime", "data", "Fecha de cobro", "Fecha en que se cobró o pagó el efecto."),
    _row("FechaDivision", "datetime", "data", "Fecha de division", "Fecha en que el efecto se dividió en varios vencimientos."),
    _row("FechaAgrupacion", "datetime", "data", "Fecha de agrupacion", "Fecha en que el efecto se agrupó con otros."),
    _row("FechaImpagado", "datetime", "data", "Fecha impagado", "Fecha en que el efecto se marcó como impagado."),
    _row("EnEuros_", "smallint", "data", "En euros", f"Indica si los importes están en euros. {_NO}"),
    _row("CodigoDivisa", "varchar", "data", "Divisa", "Divisa del efecto cuando no es la de la empresa."),
    _row("FactorCambio", "decimal", "data", "Factor de cambio", "Tipo de cambio aplicado al efecto."),
    _row("ImporteCambio", "decimal", "data", "Importe de cambio", "Diferencia de cambio del efecto."),
    _row("%IvaImpagado_", "decimal", "data", "Porcentaje IVA impagado", "Porcentaje de IVA aplicado a los gastos del impagado."),
    _row("ImporteEfecto", "decimal", "metric", "Importe efecto", "Importe total del efecto, gastos incluidos."),
    _row("ImporteEfectoSinGastos", "decimal", "data", "Importe sin gastos", "Importe del efecto antes de sumar los gastos."),
    _row("ImporteDivisa", "decimal", "data", "Importe en divisa", "Importe del efecto en la divisa original."),
    _row("ImporteDivisaSinGastos", "decimal", "data", "Importe divisa sin gastos", "Importe en divisa antes de los gastos."),
    _row("ImporteCobrado", "decimal", "metric", "Importe cobrado", "Importe ya cobrado o pagado del efecto."),
    _row("ImportePendiente", "decimal", "data", "Importe pendiente", "Importe que todavía está pendiente. La copia local no guarda esta columna; se puede obtener restando lo cobrado del importe del efecto."),
    _row("ImportePendienteDivisa", "decimal", "data", "Pendiente en divisa", "Importe pendiente expresado en la divisa del efecto."),
    _row("ImporteGastos", "decimal", "data", "Gastos", "Gastos cargados sobre el efecto."),
    _row("GastosImpagado_", "decimal", "data", "Gastos de impagado", "Gastos repercutidos por el impagado."),
    _row("GastosImpagadoDivisa_", "decimal", "data", "Gastos impagado divisa", "Gastos del impagado en la divisa del efecto."),
    _row("GtoImpagado_", "decimal", "data", "Gasto impagado", "Importe de gasto del impagado, distinto de la comisión y del correo."),
    _row("GtoImpagadoDivisa_", "decimal", "data", "Gasto impagado divisa", "Gasto del impagado en divisa."),
    _row("GastoCorreoImpagado_", "decimal", "data", "Gasto de correo", "Gasto de correo de la reclamación del impagado."),
    _row("GastoCorreoImpagadoDivisa_", "decimal", "data", "Gasto de correo divisa", "Gasto de correo del impagado en divisa."),
    _row("CuotaIvaImpagado_", "decimal", "data", "IVA del impagado", "Cuota de IVA de los gastos del impagado."),
    _row("CuotaIvaImpagadoDivisa_", "decimal", "data", "IVA impagado divisa", "Cuota de IVA del impagado en divisa."),
    _row("MascaraRecibo_", "varchar", "data", "Mascara del recibo", "Máscara con la que se imprimió el recibo."),
    _row("TipoDocumento", "varchar", "data", "Tipo de documento", "Tipo de documento de origen del efecto."),
    _row("Bloqueo", "smallint", "data", "Bloqueado", f"Indica si el efecto está bloqueado y no se puede remesar. {_NO}"),
    _row("Remesable", "smallint", "data", "Remesable", f"Indica si el efecto se puede incluir en una remesa. {_NO}"),
    _row("DocumentoConciliacion", "varchar", "data", "Documento conciliacion", "Referencia bancaria con la que se concilió el efecto."),
    _row("CodigoCuentaFactura", "varchar", "data", "Cuenta de la factura", "Cuenta contable de la factura que originó el efecto."),
    _row("ContrapartidaOrigen", "varchar", "data", "Contrapartida origen", "Contrapartida original antes de sustituir el efecto."),
    _row("MovPosicionOrigen", "uniqueidentifier", "data", "Apunte origen", "Apunte contable del que procede el efecto."),
    _row("ControlTalones", "smallint", "data", "Control de talones", f"Indica si el talón está controlado. {_NO}"),
    _row("SuFacturaNo", "varchar", "data", "Su factura", "Número de factura del cliente o del proveedor."),
    _row("CodigoRetencion", "smallint", "data", "Codigo de retencion", "Código de la retención aplicada al efecto."),
    _row("BaseRetencion", "decimal", "data", "Base de retencion", "Base sobre la que se calcula la retención."),
    _row("AgrupacionCuadre", "int", "data", "Agrupacion de cuadre", "Grupo usado para cuadrar el efecto con su asiento."),
    _row("RemesaHabitual", "varchar", "data", "Remesa habitual", "Remesa habitual del cliente o proveedor para este efecto."),
    _row("Proceso", "uniqueidentifier", "data", "Proceso", "Identificador del proceso de Sage que generó el efecto."),
    _row("NumeroCaja", "smallint", "data", "Caja", "Caja en la que se cobró o pagó el efecto."),
    _row("NumeroInterno", "int", "data", "Numero interno", "Número interno de cartera."),
    _row("NumeroCobro", "int", "data", "Numero de cobro", "Número de la operación de cobro o pago."),
    _row("CamposControlCartera", "varchar", "data", "Control de cartera", "Cadena interna de Sage con marcas de control del efecto."),
    _row("StatusGeneradoImpagado_", "smallint", "data", "Impagado generado", f"Indica si ya se generó el efecto de impagado. {_NO}"),
    _row("sysTraspasoLWG", "smallint", "data", "Traspaso interno", "Marca interna de Sage para el traspaso entre módulos."),
    _row("FechaVencimientoOrigenLc", "datetime", "data", "Vencimiento original", "Fecha de vencimiento original antes de una modificación."),
    _row("NumeroTalonLc", "varchar", "data", "Talon", "Número de talón en formato de texto."),
    _row("Status431", "smallint", "data", "Cuenta 431", f"Indica si el efecto pasó por la cuenta de efectos en gestión. {_NO}"),
    _row("NumeroPagoNorma", "int", "data", "Pago de norma", "Número de pago dentro del fichero de la norma bancaria."),
    _row("FechaEmisionTalon", "datetime", "data", "Fecha del talon", "Fecha de emisión del talón o pagaré."),
    _row("BancoImpagado", "varchar", "data", "Banco del impagado", "Banco que devolvió el efecto impagado."),
    _row("IdImpagado", "varchar", "data", "Identificador impagado", "Identificador del impagado."),
    _row("IdUnicoImp", "uniqueidentifier", "data", "Impagado unico", "Identificador único interno del impagado."),
    _row("sysDispositivo", "varchar", "data", "Dispositivo", "Dispositivo o puesto desde el que se grabó el efecto."),
    _row("EmpresaOrigen", "smallint", "data", "Empresa origen", "Empresa de origen cuando el efecto viene de otra sociedad."),
    _row("NEfectoGlobal", "int", "data", "Efecto global", "Número global del efecto cuando se agrupan vencimientos."),
    _row("ImporteEfectoOriginal", "decimal", "data", "Importe original", "Importe del efecto antes de divisiones, agrupaciones o diferencias de cambio."),
    _row("DiferenciaCambioPos", "decimal", "data", "Diferencia de cambio positiva", "Diferencia de cambio a favor al liquidar el efecto."),
    _row("DiferenciaCambioNeg", "decimal", "data", "Diferencia de cambio negativa", "Diferencia de cambio en contra al liquidar el efecto."),
    _row("ImporteCobradoLiquidacion", "decimal", "data", "Cobrado en liquidacion", "Importe cobrado o pagado en la liquidación de la remesa."),
    _row("TraspasoLWGComisiones", "smallint", "data", "Traspaso de comisiones", "Marca interna del traspaso de comisiones."),
    _row("EjercicioProvision", "smallint", "data", "Ejercicio de provision", "Ejercicio de la provisión ligada al efecto."),
    _row("SerieProvision", "varchar", "data", "Serie de provision", "Serie del documento de provisión."),
    _row("NumeroProvision", "int", "data", "Numero de provision", "Número del documento de provisión."),
    _row("CodigoCuentaANT_", "varchar", "data", "Cuenta anterior", "Cuenta contable antes del último cambio de codificación."),
    _row("ContrapartidaANT_", "varchar", "data", "Contrapartida anterior", "Contrapartida antes del último cambio de codificación."),
    _row("RemesaHabitualANT_", "varchar", "data", "Remesa habitual anterior", "Remesa habitual antes del último cambio de codificación."),
    _row("CodigoCuentaFacturaANT_", "varchar", "data", "Cuenta factura anterior", "Cuenta de la factura antes del último cambio de codificación."),
    _row("ContrapartidaOrigenANT_", "varchar", "data", "Contrapartida origen anterior", "Contrapartida de origen antes del último cambio de codificación."),
    _row("BancoRemesaANT_", "varchar", "data", "Banco remesa anterior", "Banco de remesa antes del último cambio de codificación."),
    _row("BancoImpagadoANT_", "varchar", "data", "Banco impagado anterior", "Banco del impagado antes del último cambio de codificación."),
    _row("TipoDocumentoOrigen", "varchar", "data", "Documento origen", "Tipo del documento que originó el efecto."),
    _row("EjercicioOrigen", "smallint", "data", "Ejercicio origen", "Ejercicio del documento de origen."),
    _row("SerieOrigen", "varchar", "data", "Serie origen", "Serie del documento de origen."),
    _row("NumeroOrigen", "int", "data", "Numero origen", "Número del documento de origen."),
    _row("GastoComisionImpagado_", "decimal", "data", "Comision de impagado", "Comisión cargada por la devolución del efecto."),
    _row("GastoComisionImpagadoDivisa_", "decimal", "data", "Comision impagado divisa", "Comisión del impagado en la divisa del efecto."),
    _row("ReferenciaMandato", "varchar", "data", "Mandato", "Referencia del mandato SEPA de domiciliación."),
    _row("MedioCobro", "varchar", "data", "Medio de cobro", "Medio con el que se cobra o se paga el efecto."),
    _row("CriterioIva", "smallint", "data", "Criterio de IVA", "Criterio de IVA aplicado al efecto."),
    _row("PagoInmediato", "smallint", "data", "Pago inmediato", f"Indica si el efecto se paga al contado. {_NO}"),
    _row("ComisionCobro", "decimal", "data", "Comision de cobro", "Comisión aplicada al cobro del efecto."),
]

TABLES = {
    "AcumuladosConta": {
        "description": "Acumulados de debe, haber y presupuesto por cuenta, ejercicio y período.",
        "table_context": "Saldos de **acumulados contables** por cuenta y período, con el presupuesto del debe y del haber.",
        "keywords": ["acumulados", "debe", "haber", "presupuesto contable"],
        "fields": ACUMULADOS,
        "view": """
            CREATE OR REPLACE VIEW public.datiadb_acumuladosconta AS
            SELECT
                empresa AS empresa,
                ejercicio AS ejercicio,
                cuenta AS cuenta_contable,
                periodo AS periodo,
                debe AS debe_acumulado,
                haber AS haber_acumulado,
                debe_presupuesto AS debe_presupuestado,
                haber_presupuesto AS haber_presupuestado
            FROM public.datia_financial_acumulados
        """,
    },
    "PlanCuentas": {
        "description": "Plan de cuentas. Cada fila es una cuenta contable con su código y su nombre.",
        "table_context": "Plan contable. Cada fila es una **cuenta contable**.",
        "keywords": ["plan de cuentas", "plan contable", "cuentas contables"],
        "fields": PLAN,
        "view": """
            CREATE OR REPLACE VIEW public.datiadb_plancuentas AS
            SELECT
                empresa AS empresa,
                codigo AS codigo_cuenta,
                descripcion AS nombre_cuenta
            FROM public.datia_financial_plan
        """,
    },
    "CarteraEfectos": {
        "description": "Efectos de cobro y de pago, con vencimiento, importe y lo ya cobrado.",
        "table_context": "Cartera de **efectos de cobro y pago**, con vencimiento e importe.",
        "keywords": ["cartera", "efectos", "vencimientos", "cobros", "pagos"],
        "fields": CARTERA,
        "view": """
            CREATE OR REPLACE VIEW public.datiadb_carteraefectos AS
            SELECT
                empresa AS empresa,
                ejercicio AS ejercicio,
                codigo_titular AS cliente_proveedor,
                fecha_vencimiento AS fecha_vencimiento,
                fecha_emision AS fecha_factura,
                importe AS importe_efecto,
                importe_cobrado AS importe_cobrado,
                tipo_efecto AS cobro_o_pago
            FROM public.datia_financial_cartera
        """,
    },
    "Movimientos": {
        "description": "Líneas del diario. Cada fila es un apunte de un asiento. Todavía no hay copia local, así que el reentrenamiento no puede validarse hasta que se sincronice.",
        "table_context": "Diario contable. Cada fila es un **apunte** de un asiento.",
        "keywords": ["diario", "asientos", "apuntes", "movimientos contables"],
        "fields": MOVIMIENTOS,
        "view": None,
    },
}


def apply_accounting_semantics():
    """Crea las vistas locales y aplica el mapeo semántico en cada empresa que ya tiene fuentes."""
    with connection.cursor() as cursor:
        for spec in TABLES.values():
            if spec["view"]:
                cursor.execute(spec["view"])

    empresas = list(DataSource.objects.order_by().values_list("empresa_id", flat=True).distinct())
    summary = []
    for empresa_id in empresas:
        for table_name, spec in TABLES.items():
            source = DataSource.objects.filter(empresa_id=empresa_id, source_table=table_name).order_by("id").first()
            if source is None:
                source = DataSource.objects.create(
                    empresa_id=empresa_id,
                    name=table_name,
                    source_table=table_name,
                    description=spec["description"],
                    table_context=spec["table_context"],
                    keywords=spec["keywords"],
                    is_active=False,
                    is_virtual=False,
                    sync_mode="full",
                )
            else:
                source.description = spec["description"]
                source.table_context = spec["table_context"]
                if not source.keywords:
                    source.keywords = spec["keywords"]
                source.save(update_fields=["description", "table_context", "keywords", "updated_at"])

            for field in spec["fields"]:
                obj, created = DataField.objects.get_or_create(
                    source=source,
                    field_name=field["field_name"],
                    defaults={
                        "source_table_name": table_name,
                        "business_name": field["business_name"],
                        "description": field["description"],
                        "data_type": field["data_type"],
                        "usage_type": field["usage_type"],
                        "metadata_tag": "Finanzas",
                        "is_active": True,
                        "is_key": field["is_key"],
                    },
                )
                if not created:
                    obj.source_table_name = table_name
                    obj.business_name = field["business_name"]
                    obj.description = field["description"]
                    obj.data_type = field["data_type"]
                    obj.usage_type = field["usage_type"]
                    obj.metadata_tag = "Finanzas"
                    obj.is_active = True
                    obj.is_key = field["is_key"]
                    obj.save()
            summary.append((empresa_id, table_name, source.id, len(spec["fields"])))
    return summary
