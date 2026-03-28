from django.db import models # type: ignore

class Embarcaciones(models.Model):
    numero = models.IntegerField(primary_key=True)
    nombre = models.CharField(max_length=50)
    descripcion = models.TextField(null=True, blank=True)
    tipo = models.TextField()
    id_socio = models.IntegerField()
    marca = models.CharField(max_length=20, null=True, blank=True)
    modelo = models.CharField(max_length=20, null=True, blank=True)
    color = models.CharField(max_length=30)
    prestamo = models.IntegerField()

    class Meta:
        db_table = 'embarcaciones'
        verbose_name_plural = 'Embarcaciones'


class Historico_socios(models.Model):
    fecha = models.DateField(primary_key=True)
    familiar = models.IntegerField()
    individual = models.IntegerField()
    total = models.IntegerField()
    personas = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'historico_socios'
        verbose_name_plural = 'Historico Socios'


class Pagos(models.Model):
    id = models.IntegerField(primary_key=True)
    id_socio = models.IntegerField(null=True, blank=True)
    fecha = models.DateField()
    cantidad = models.IntegerField(null=True, blank=True)
    monto = models.IntegerField()

    class Meta:
        db_table = 'pagos'
        verbose_name_plural = 'Pagos'


class Personas(models.Model):
    Cedula = models.CharField(max_length=11, primary_key=True, verbose_name="Cédula")
    numeroSocio = models.IntegerField(verbose_name="Número de socio")
    PrimerNombre = models.CharField(max_length=100, verbose_name="Primer nombre")
    SegundoNombre = models.CharField(max_length=100, null=True, blank=True, verbose_name="Segundo nombre")
    PrimerApellido = models.CharField(max_length=100, verbose_name="Primer apellido")
    SegundoApellido = models.CharField(max_length=100, null=True, blank=True, verbose_name="Segundo apellido")
    FechaNacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de nacimiento")
    Edad = models.IntegerField(null=True, blank=True, verbose_name="Edad")
    Direccion = models.CharField(max_length=100, null=True, blank=True, verbose_name="Dirección")
    Telefono = models.CharField(max_length=9, null=True, blank=True, verbose_name="Teléfono")
    Celular = models.CharField(max_length=12, null=True, blank=True, verbose_name="Celular")
    Correo = models.CharField(max_length=100, null=True, blank=True, verbose_name="Correo electrónico")
    relacionTitular = models.CharField(max_length=20, null=True, blank=True, verbose_name="Relación titular")
    salud = models.CharField(max_length=20, null=True, blank=True, verbose_name="Salud")
    llave = models.IntegerField(null=True, blank=True, verbose_name="Llave")

    class Meta:
        db_table = 'personas'
        verbose_name_plural = 'Personas'

    def __str__(self):
        return self.nombre_completo()

    def nombre_completo(self):
        return f"{self.PrimerNombre} {self.SegundoNombre or ''} {self.PrimerApellido} {self.SegundoApellido or ''}".strip()



class Precios(models.Model):
    id = models.IntegerField(primary_key=True)
    monto = models.IntegerField()
    tipo = models.TextField()
    vigente = models.IntegerField()
    fecha = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'precios'
        verbose_name_plural = 'Precios'


class Recibos(models.Model):
    id = models.IntegerField(primary_key=True)
    fecha = models.DateField()
    estado = models.IntegerField()
    monto = models.IntegerField()
    id_socio = models.CharField(max_length=8)
    id_pago = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'recibos'
        verbose_name_plural = 'Recibos'


class Socios(models.Model):
    ACTIVO_CHOICES = (
        (1, 'ALTA'),
        (0, 'BAJA'),
        (2, 'PENDIENTE'),
    )
    numero = models.IntegerField(primary_key=True, verbose_name="Número")
    activo = models.IntegerField(choices=ACTIVO_CHOICES, null=True, blank=True, verbose_name="Activo")
    fechaAlta = models.DateField(verbose_name="Fecha de alta")
    fechaBaja = models.DateField(null=True, blank=True, verbose_name="Fecha de baja")
    tipo = models.TextField(verbose_name="Tipo de socio")
    cedulaTitular = models.CharField(max_length=11, verbose_name="Cédula del titular")
    comentarios = models.CharField(max_length=40, null=True, blank=True, verbose_name="Comentarios")
    lugarPago = models.CharField(max_length=20, null=True, blank=True, verbose_name="Lugar de pago")
    cobroEspecial = models.IntegerField(null=True, blank=True, verbose_name="Cobro especial")
    percha = models.IntegerField(null=True, blank=True, verbose_name="Percha")
    Habilitado = models.IntegerField(null=True, blank=True, verbose_name="Habilitado")

    class Meta:
        db_table = 'socios'
        verbose_name_plural = 'Socios'

    def __str__(self):
        try:
            persona = Personas.objects.get(Cedula=self.cedulaTitular)
            return f"{persona.nombre_completo()}"
        except Personas.DoesNotExist:
            return f"Socio object ({self.numero})"


class Socios_cambios(models.Model):
    id = models.IntegerField(primary_key=True)
    fecha = models.DateField()
    accion = models.TextField()
    comentario = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'socios_cambios'
        verbose_name_plural = 'Historial de cambios'
