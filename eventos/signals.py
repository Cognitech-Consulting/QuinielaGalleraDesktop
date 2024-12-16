from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Evento

@receiver(pre_save, sender=Evento)
def ensure_single_current_event(sender, instance, **kwargs):
    if instance.current:  # If an event is marked as current
        sender.objects.filter(current=True).exclude(pk=instance.pk).update(current=False)
