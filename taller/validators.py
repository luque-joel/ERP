import re
from django.core.exceptions import ValidationError

def validar_cedula_ruc_ecuador(value):
    """
    Valida cédulas y RUCs de Ecuador (Personas Naturales, Sociedades Privadas y Públicas).
    Lanza ValidationError si el formato o el dígito verificador es incorrecto.
    """
    if not value:
        return

    # Limpiar espacios y caracteres no numéricos
    value = re.sub(r'\D', '', value)

    # Permitir Consumidor Final de forma directa sin validar algoritmo
    if value in ("9999999999999", "9999999999"):
        return

    # Validar longitud (10 para cédula, 13 para RUC)
    if len(value) not in (10, 13):
        raise ValidationError("La identificación debe tener 10 dígitos (cédula) o 13 dígitos (RUC).")

    provincia = int(value[0:2])
    if not (1 <= provincia <= 24 or provincia == 30):
        raise ValidationError("El código de provincia (primeros dos dígitos) es inválido.")

    tercer_digito = int(value[2])

    # Caso 1: RUC de Persona Natural (termina en 001 y los primeros 10 son cédula válida)
    # Caso 2: Cédula de Identidad (10 dígitos)
    if tercer_digito < 6:
        # Validar últimos dígitos si es RUC de persona natural
        if len(value) == 13 and value[10:13] != "001":
            raise ValidationError("El RUC de persona natural debe terminar en '001'.")
        
        # Algoritmo de validación de Cédula (Módulo 10)
        coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        suma = 0
        for i in range(9):
            valor = int(value[i]) * coeficientes[i]
            if valor >= 10:
                valor -= 9
            suma += valor
        
        verificador = int(value[9])
        residuo = suma % 10
        digito_esperado = 10 - residuo if residuo != 0 else 0
        
        if verificador != digito_esperado:
            raise ValidationError("La cédula o RUC ingresado es inválido (error en dígito verificador).")

    # Caso 3: RUC de Sociedades Privadas y Extranjeros sin cédula (tercer dígito = 9)
    elif tercer_digito == 9:
        if len(value) != 13:
            raise ValidationError("El RUC de sociedades debe tener 13 dígitos.")
        if value[10:13] != "001":
            raise ValidationError("El RUC de sociedades debe terminar en '001'.")

        coeficientes = [4, 3, 2, 5, 4, 3, 2, 0, 0] # Coeficientes para el módulo 11
        suma = 0
        for i in range(9):
            suma += int(value[i]) * coeficientes[i]
            
        verificador = int(value[9])
        residuo = suma % 11
        digito_esperado = 11 - residuo if residuo != 0 else 0
        if digito_esperado == 11:
            digito_esperado = 0
            
        if verificador != digito_esperado:
            raise ValidationError("El RUC de sociedad privada es inválido.")

    # Caso 4: RUC de Instituciones Públicas (tercer dígito = 6)
    elif tercer_digito == 6:
        if len(value) != 13:
            raise ValidationError("El RUC público debe tener 13 dígitos.")
        if value[10:13] != "001":
            raise ValidationError("El RUC público debe terminar en '001'.")

        coeficientes = [3, 2, 7, 6, 5, 4, 3, 2, 0] # Coeficientes para el módulo 11
        suma = 0
        for i in range(8):
            suma += int(value[i]) * coeficientes[i]
            
        verificador = int(value[8])
        residuo = suma % 11
        digito_esperado = 11 - residuo if residuo != 0 else 0
        if digito_esperado == 11:
            digito_esperado = 0
            
        if verificador != digito_esperado:
            raise ValidationError("El RUC de institución pública es inválido.")
            
    else:
        raise ValidationError("La identificación ingresada no tiene una estructura válida.")
