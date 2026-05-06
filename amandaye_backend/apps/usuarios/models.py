from django.db import models # type: ignore
from django.contrib.auth.models import User

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


class Personas(models.Model):
    Cedula = models.CharField(max_length=11, primary_key=True, verbose_name="Cédula")
    numeroSocio = models.IntegerField(verbose_name="Número de socio")
    PrimerNombre = models.CharField(max_length=100, verbose_name="Primer nombre")
    SegundoNombre = models.CharField(max_length=100, null=True, blank=True, verbose_name="Segundo nombre")
    PrimerApellido = models.CharField(max_length=100, verbose_name="Primer apellido")
    SegundoApellido = models.CharField(max_length=100, null=True, blank=True, verbose_name="Segundo apellido")
    FechaNacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de nacimiento")
    Direccion = models.CharField(max_length=100, null=True, blank=True, verbose_name="Dirección")
    Telefono = models.CharField(max_length=9, null=True, blank=True, verbose_name="Teléfono")
    Celular = models.CharField(max_length=12, null=True, blank=True, verbose_name="Celular")
    Correo = models.CharField(max_length=100, null=True, blank=True, verbose_name="Correo electrónico")
    relacionTitular = models.CharField(max_length=20, null=True, blank=True, verbose_name="Relación titular")
    salud = models.CharField(max_length=20, null=True, blank=True, verbose_name="Salud")
    llave = models.IntegerField(null=True, blank=True, verbose_name="Llave")

    ESTADO_HABILITACION = [
        ('NO_HABILITADO', 'No habilitado'),
        ('HABILITADO', 'Habilitado'),
        ('SUSPENDIDO', 'Suspendido'),
        ('REVOCADO', 'Revocado'),
    ]

    estado_habilitacion = models.CharField(
        max_length=20,
        choices=ESTADO_HABILITACION,
        default='NO_HABILITADO',
        editable=False,
        verbose_name='Estado de habilitación'
    )

    fecha_ultimo_calculo_habilitacion = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name='Último cálculo de habilitación'
    )

    class Meta:
        db_table = 'personas'
        verbose_name_plural = 'Personas'

    def __str__(self):
        return self.nombre_completo()

    def nombre_completo(self):
        return f"{self.PrimerNombre} {self.SegundoNombre or ''} {self.PrimerApellido} {self.SegundoApellido or ''}".strip()


class AprobacionProfesor(models.Model):
    persona = models.ForeignKey(
        Personas,
        on_delete=models.CASCADE,
        related_name='aprobaciones_profesor'
    )
    numero_socio_momento = models.IntegerField(
        verbose_name='Número de socio al momento de la aprobación',
        null=True, blank=True
    )
    nombre_profesor = models.CharField(max_length=100)
    fecha = models.DateField()
    observaciones = models.TextField(null=True, blank=True)
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aprobación de profesor'
        verbose_name_plural = 'Aprobaciones de profesor'
        ordering = ['-fecha']

    def save(self, *args, **kwargs):
        if not self.numero_socio_momento and self.persona_id:
            self.numero_socio_momento = self.persona.numeroSocio
        super().save(*args, **kwargs)
        from apps.usuarios.services.habilitacion import recalcular_habilitacion_persona
        recalcular_habilitacion_persona(self.persona)


class AvalComisionDirectiva(models.Model):
    persona = models.ForeignKey(
        Personas,
        on_delete=models.CASCADE,
        related_name='avales_cd'
    )
    usuario_cd = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='avales_otorgados'
    )
    fecha_aval = models.DateField()
    observaciones = models.TextField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    fecha_revocacion = models.DateTimeField(null=True, blank=True)
    motivo_revocacion = models.TextField(null=True, blank=True)
    usuario_revocacion = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='avales_revocados'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Aval de Comisión Directiva'
        verbose_name_plural = 'Avales de Comisión Directiva'
        ordering = ['-fecha_aval']
        permissions = [
            ('puede_revocar_aval', 'Puede revocar avales de CD'),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from apps.usuarios.services.habilitacion import recalcular_habilitacion_persona
        recalcular_habilitacion_persona(self.persona)

    def revocar(self, usuario, motivo):
        from django.utils import timezone
        self.activo = False
        self.fecha_revocacion = timezone.now()
        self.motivo_revocacion = motivo
        self.usuario_revocacion = usuario
        self.save() # The save method above will trigger the recalculation


class Socios(models.Model):
    ACTIVO_CHOICES = (
        (1, 'ALTA'),
        (0, 'BAJA'),
        (2, 'PENDIENTE'),
        (3, 'RECHAZADO'),
    )
    numero = models.IntegerField(primary_key=True, verbose_name="Número")
    activo = models.IntegerField(choices=ACTIVO_CHOICES, null=True, blank=True, verbose_name="Activo")
    fechaSolicitud = models.DateField(null=True, blank=True, verbose_name="Fecha de solicitud")
    fechaAprobacion = models.DateField(null=True, blank=True, verbose_name="Fecha de aprobación")
    fechaAlta = models.DateField(null=True, blank=True, verbose_name="Fecha de alta")
    fechaBaja = models.DateField(null=True, blank=True, verbose_name="Fecha de baja")
    tipo_socio = models.CharField(
        max_length=20,
        choices=[('INDIVIDUAL', 'Individual'), ('FAMILIAR', 'Familiar')],
        verbose_name='Tipo de socio',
        default='INDIVIDUAL'
    )
    tipo_cuota = models.CharField(
        max_length=20,
        choices=[
            ('ANUAL', 'Anual'),
            ('TEMPORADA', 'Temporada'),
            ('BECA', 'Beca'),
            ('EXONERADO', 'Exonerado'),
        ],
        verbose_name='Tipo de cuota',
        default='ANUAL'
    )
    cedulaTitular = models.CharField(max_length=11, verbose_name="Cédula del titular")
    comentarios = models.CharField(max_length=40, null=True, blank=True, verbose_name="Comentarios")
    percha = models.IntegerField(null=True, blank=True, verbose_name="Percha")

    class Meta:
        db_table = 'socios'
        verbose_name_plural = 'Socios'
        permissions = [
            ("puede_aprobar_socio", "Puede aprobar socios nuevos"),
            ("puede_rechazar_socio", "Puede rechazar solicitudes de socios"),
            ("puede_dar_baja_socio", "Puede dar de baja socios activos"),
        ]
        verbose_name = 'Socio'

    def __str__(self):
        try:
            persona = Personas.objects.get(Cedula=self.cedulaTitular)
            return f"{persona.nombre_completo()}"
        except Personas.DoesNotExist:
            return f"Socio N° {self.numero}"

    @property
    def esta_activo(self):
        return self.activo == 1

    @property
    def esta_de_baja(self):
        return self.activo == 0

    @property
    def esta_pendiente(self):
        return self.activo == 2

    @property
    def esta_rechazado(self):
        return self.activo == 3


class Socios_cambios(models.Model):
    id = models.IntegerField(primary_key=True)
    fecha = models.DateField()
    accion = models.TextField()
    comentario = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'socios_cambios'
        verbose_name_plural = 'Historial de cambios'
