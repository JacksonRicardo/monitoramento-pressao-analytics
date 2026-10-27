from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Perfil


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_perfil(sender, instance, created, **kwargs):
    """Garante que todo usuário tenha um perfil."""
    if created:
        Perfil.objects.get_or_create(usuario=instance)

