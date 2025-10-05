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


class Historico_socios(models.Model):
    fecha = models.DateField(primary_key=True)
    familiar = models.IntegerField()
    individual = models.IntegerField()
    total = models.IntegerField()
    personas = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'historico_socios'


class Pagos(models.Model):
    id = models.IntegerField(primary_key=True)
    id_socio = models.IntegerField(null=True, blank=True)
    fecha = models.DateField()
    cantidad = models.IntegerField(null=True, blank=True)
    monto = models.IntegerField()

    class Meta:
        db_table = 'pagos'


class Personas(models.Model):
    Cedula = models.CharField(max_length=11, primary_key=True)
    numeroSocio = models.IntegerField()
    PrimerNombre = models.CharField(max_length=100)
    SegundoNombre = models.CharField(max_length=100, null=True, blank=True)
    PrimerApellido = models.CharField(max_length=100)
    SegundoApellido = models.CharField(max_length=100, null=True, blank=True)
    FechaNacimiento = models.DateField(null=True, blank=True)
    Edad = models.IntegerField(null=True, blank=True)
    Direccion = models.CharField(max_length=100, null=True, blank=True)
    Telefono = models.CharField(max_length=9, null=True, blank=True)
    Celular = models.CharField(max_length=12, null=True, blank=True)
    Correo = models.CharField(max_length=100, null=True, blank=True)
    relacionTitular = models.CharField(max_length=20, null=True, blank=True)
    salud = models.CharField(max_length=20, null=True, blank=True)
    llave = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'personas'

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


class Recibos(models.Model):
    id = models.IntegerField(primary_key=True)
    fecha = models.DateField()
    estado = models.IntegerField()
    monto = models.IntegerField()
    id_socio = models.CharField(max_length=8)
    id_pago = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'recibos'


class Socios(models.Model):
    numero = models.IntegerField(primary_key=True)
    activo = models.IntegerField(null=True, blank=True)
    fechaAlta = models.DateField()
    fechaBaja = models.DateField(null=True, blank=True)
    tipo = models.TextField()
    cedulaTitular = models.CharField(max_length=11)
    comentarios = models.CharField(max_length=40, null=True, blank=True)
    lugarPago = models.CharField(max_length=20, null=True, blank=True)
    cobroEspecial = models.IntegerField(null=True, blank=True)
    percha = models.IntegerField(null=True, blank=True)
    Habilitado = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'socios'

    def __str__(self):
        try:
            persona = Personas.objects.get(Cedula=self.cedulaTitular)
            return f"Titular: {persona.nombre_completo()}"
        except Personas.DoesNotExist:
            return f"Socio object ({self.numero})"


class Socios_cambios(models.Model):
    id = models.IntegerField(primary_key=True)
    fecha = models.DateField()
    accion = models.TextField()
    comentario = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'socios_cambios'
