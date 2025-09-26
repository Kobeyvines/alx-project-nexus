from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, Cart

@receiver(post_save, sender=User)
def create_or_update_user_related_models(sender, instance, created, **kwargs):
    Profile.objects.get_or_create(user=instance)
    Cart.objects.get_or_create(user=instance)   # ✅ safe even on repeated saves

    if not created and hasattr(instance, "profile"):
        instance.profile.save()
