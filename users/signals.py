import logging
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

@receiver(user_logged_in)
def log_user_logged_in(sender, request, user, **kwargs):
    logger.info(f'User logged in: {user.username}')

@receiver(user_logged_out)
def log_user_logged_out(sender, request, user, **kwargs):
    logger.info(f'User logged out: {user.username}')

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    logger.warning(f'User login failed for: {credentials.get("username", None)}')

@receiver(post_save, sender=User)
def log_user_created_or_updated(sender, instance, created, **kwargs):
    if created:
        logger.info(f'New user created: {instance.username}')
    else:
        logger.info(f'User updated: {instance.username}')