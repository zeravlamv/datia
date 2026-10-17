import os
import sys
import time
import subprocess
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = "Arranca dos servidores Django: 8000 (config.settings) y 8001 (config.settings_mobile)"

    def add_arguments(self, parser):
        parser.add_argument('--port-desktop', type=int, default=8000, help='Puerto escritorio (default 8000)')
        parser.add_argument('--port-mobile', type=int, default=8001, help='Puerto móvil (default 8001)')

    def handle(self, *args, **opts):
        port_desktop = int(opts.get('port_desktop', 8000))
        port_mobile = int(opts.get('port_mobile', 8001))

        base_dir = settings.BASE_DIR
        py = sys.executable
        manage = os.path.join(base_dir, "manage.py")

        self.stdout.write(self.style.NOTICE(f"Iniciando escritorio en 0.0.0.0:{port_desktop} (config.settings)"))
        p_desktop = subprocess.Popen([py, manage, "runserver", f"0.0.0.0:{port_desktop}", "--settings=config.settings"], cwd=base_dir)
        time.sleep(0.8)  # pequeña holgura

        self.stdout.write(self.style.NOTICE(f"Iniciando móvil en 0.0.0.0:{port_mobile} (config.settings_mobile)"))
        p_mobile = subprocess.Popen([py, manage, "runserver", f"0.0.0.0:{port_mobile}", "--settings=config.settings_mobile"], cwd=base_dir)

        self.stdout.write(self.style.SUCCESS(f"Escritorio PID={p_desktop.pid} | Móvil PID={p_mobile.pid}"))
        self.stdout.write("Finaliza con CTRL+C para cerrar ambos procesos.")

        try:
            # Mantener proceso padre vivo mientras los hijos corren
            while True:
                # Si cualquiera termina, salimos para limpiar
                if p_desktop.poll() is not None or p_mobile.poll() is not None:
                    break
                time.sleep(1.0)
        except KeyboardInterrupt:
            self.stdout.write("\nDeteniendo servidores...")
        finally:
            for p in (p_desktop, p_mobile):
                try:
                    if p.poll() is None:
                        p.terminate()
                        time.sleep(0.5)
                except Exception:
                    pass
            self.stdout.write(self.style.SUCCESS("Servidores detenidos"))
