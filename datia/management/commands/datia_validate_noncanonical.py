from django.core.management.base import BaseCommand, CommandError
import os
import re


class Command(BaseCommand):
    help = "Valida que el repositorio no contenga nombres canónicos prohibidos en el código."

    BANNED_PATTERNS = [
        r"\bCabeceraAlbaranCliente\b",
        r"\bLineasAlbaranCliente\b",
        r"\bCabeceraAlbaranProveedor\b",
        r"\bLineasAlbaranProveedor\b",
        r"\bCabeceraCompras\b",
        r"\bLineasCompras\b",
        r"\bComprasLineas\b",
        r"\bCabeceraPedidoProveedor\b",
        r"\bLineasPedidoProveedor\b",
    ]

    CODE_EXTS = (".py", ".js", ".ts", ".tsx")

    def add_arguments(self, parser):
        parser.add_argument(
            "--root",
            default=None,
            help="Directorio raíz a escanear (por defecto settings.BASE_DIR/datia).",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        root = options.get("root") or os.path.join(settings.BASE_DIR, "datia")
        banned_regex = [re.compile(p) for p in self.BANNED_PATTERNS]

        ignored_dirs = {
            "templates",
            "patterns",
            "static",
            "migrations",
            "__pycache__",
            "node_modules",
            ".git",
        }
        # Ignorar este propio archivo
        self_path = os.path.realpath(__file__)
        matches = []

        for dirpath, dirnames, filenames in os.walk(root):
            # Filtra directorios ignorados
            dirnames[:] = [d for d in dirnames if d not in ignored_dirs]
            for fname in filenames:
                if not fname.endswith(self.CODE_EXTS):
                    continue
                fpath = os.path.join(dirpath, fname)
                if os.path.realpath(fpath) == self_path:
                    continue
                # Whitelist de rutas permitidas para referencias explícitas controladas
                whitelist = {
                    os.path.normpath(os.path.join(root, "datia", "services", "etl_service.py")),
                    os.path.normpath(os.path.join(root, "datia", "services", "financial_service.py")),
                    os.path.normpath(os.path.join(root, "datia", "management", "commands", "seed_sales_semantics.py")),
                }
                if os.path.normpath(fpath) in whitelist:
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        for idx, line in enumerate(fh, start=1):
                            for rx in banned_regex:
                                if rx.search(line):
                                    snippet = line.strip()
                                    matches.append((fpath, idx, snippet))
                except Exception:
                    # Si un archivo no puede leerse, lo omitimos
                    continue

        if matches:
            self.stdout.write(self.style.ERROR("Se han encontrado nombres canónicos prohibidos:"))
            for fpath, idx, snippet in matches[:100]:
                self.stdout.write(f"- {fpath}:{idx} → {snippet}")
            raise CommandError(f"Validación fallida: {len(matches)} coincidencias.")

        self.stdout.write(self.style.SUCCESS("Validación OK: no se detectaron nombres canónicos en el código."))
