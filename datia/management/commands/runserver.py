import os
import sys
import time
import subprocess
from django.core.management.commands.runserver import Command as DjangoRunserverCommand
from django.conf import settings

class Command(DjangoRunserverCommand):
    help = "Ejecuta servidor dual: 8000 (config.settings) y 8001 (config.settings_mobile)"

    def handle(self, *args, **options):
        single_env = os.environ.get('DATIA_RUNSERVER_SINGLE', '').lower() in ('1', 'true', 'yes')
        is_mobile = getattr(settings, 'ROOT_URLCONF', '') == 'config.urls_mobile' or os.environ.get('DJANGO_SETTINGS_MODULE', '') == 'config.settings_mobile'
        if single_env or is_mobile:
            return super().handle(*args, **options)

        addrport = options.get('addrport')
        if not addrport:
            options['addrport'] = '0.0.0.0:8000'

        base_dir = settings.BASE_DIR
        py = sys.executable
        manage = os.path.join(base_dir, "manage.py")

        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = 'config.settings_mobile'
        env['DATIA_RUNSERVER_SINGLE'] = '1'

        p_mobile = subprocess.Popen([py, manage, "runserver", "0.0.0.0:8001"], cwd=base_dir, env=env)
        self.stdout.write(self.style.NOTICE(f"Iniciando móvil en 0.0.0.0:8001 (PID={p_mobile.pid})"))

        try:
            super().handle(*args, **options)
        finally:
            try:
                if p_mobile.poll() is None:
                    p_mobile.terminate()
                    time.sleep(0.5)
            except Exception:
                pass
            self.stdout.write(self.style.SUCCESS("Servidor móvil detenido"))
