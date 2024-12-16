from django.db import models
from accounts.models import CustomUser


class Evento(models.Model):
    nombre = models.CharField(max_length=255)
    fecha = models.DateField()
    ubicacion = models.CharField(max_length=255)
    current = models.BooleanField(default=False)
    results_visible = models.BooleanField(default=False)
    ranking_visible = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre


class Ronda(models.Model):
    evento = models.ForeignKey(Evento, related_name='rondas', on_delete=models.CASCADE)
    numero = models.IntegerField()

    def __str__(self):
        return f'Ronda {self.numero} - Evento: {self.evento.nombre}'


class Pelea(models.Model):
    ronda = models.ForeignKey('Ronda', related_name='peleas', on_delete=models.CASCADE)
    equipo1 = models.CharField(max_length=255)
    equipo2 = models.CharField(max_length=255)
    RESULTADOS = [
        ('equipo1', 'Equipo 1 Ganó'),
        ('equipo2', 'Equipo 2 Ganó'),
        ('tie', 'Empate'),
    ]
    resultado = models.CharField(
        max_length=10,
        choices=RESULTADOS,
        default='',
        blank=True,
        help_text="Resultado del partido (Equipo 1, Equipo 2 o Empate)"
    )

    def __str__(self):
        return f"{self.equipo1} vs {self.equipo2} - Resultado: {self.get_resultado_display()}"

class Prediccion(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    pelea = models.ForeignKey(Pelea, related_name='predicciones', on_delete=models.CASCADE)
    prediccion = models.CharField(max_length=10, choices=[('equipo1', 'Equipo 1'), ('empate', 'Empate'), ('equipo2', 'Equipo 2')])

    def __str__(self):
        return f"Predicción de {self.user} para {self.pelea}"

class EventoUserResult(models.Model):
    user = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE, related_name='event_results')
    evento = models.ForeignKey('Evento', on_delete=models.CASCADE, related_name='user_results')
    total_points = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'evento')  # Prevent duplicate results for the same user and event.

    def __str__(self):
        return f"{self.user.user_id} - {self.evento.nombre}: {self.total_points} points"
