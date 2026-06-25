from django.apps import AppConfig


class ServicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'services'

    def ready(self):
        from django.db.utils import ProgrammingError, OperationalError
        from .models import Gender

        try:
            # Ensure Male & Female always exist
            if not Gender.objects.filter(name='male').exists():
                Gender.objects.create(name='male')
            if not Gender.objects.filter(name='female').exists():
                Gender.objects.create(name='female')
        except (ProgrammingError, OperationalError):
            # Tables don't exist yet (e.g. during initial migrate) — skip silently
            pass