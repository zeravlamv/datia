---
name: sincronizar-github
description: >-
  Sincroniza el proyecto con su repositorio de GitHub mediante commit y push.
  Usar cuando el mensaje del usuario es la palabra CORRECTO, o cuando indica
  esa palabra para dar por bueno el trabajo y subirlo a GitHub.
---

# Sincronizar con GitHub

La palabra **CORRECTO** es la orden de subir el proyecto a GitHub. No pidas el código 111 para esta sincronización.

Si el mensaje trae más trabajo además de CORRECTO, termina ese trabajo y después sincroniza.

Responde en español. En PowerShell ejecuta un comando cada vez, sin `&&`.

## No hacer

- No cambies la configuración de git.
- No uses `--no-verify`, `--no-gpg-sign`, `push --force` ni `reset --hard`.
- No hagas force push a `main` o `master`.
- No hagas `git init` ni `gh repo create`.
- No añadas un remoto a un repositorio que el usuario no haya nombrado.
- No hagas un commit vacío.
- No incluyas secretos: `.env`, credenciales, llaves, tokens ni ficheros de contraseñas.

## Pasos

1. Comprueba que la carpeta es un repositorio:

```powershell
git rev-parse --is-inside-work-tree
```

Si no lo es, detente y pide la URL de GitHub. No inicialices el repositorio.

2. Lee el estado, el remoto y el estilo de los commits, cada comando por separado:

```powershell
git status -sb
git remote -v
git diff
git log -8 --oneline
```

Si no existe `origin`, detente y pide la URL. No elijas otro repositorio de la cuenta.

3. Si no hay cambios y la rama no está por delante del remoto, dilo y termina.

4. Si hay cambios, prepara solo los ficheros del trabajo. Deja fuera secretos y ficheros temporales. Revisa el diff preparado.

5. Crea el commit con un mensaje de una o dos frases centrado en el porqué. En PowerShell:

```powershell
git commit -m @"
Mensaje del commit.

"@
```

6. Sube la rama actual:

```powershell
git push -u origin HEAD
```

Usa `-u` solo cuando la rama todavía no sigue a un remoto. Si el push falla por autenticación o porque el remoto no existe, muestra el error y no reintentes con otro destino.

7. Comprueba el resultado:

```powershell
git status -sb
```

Responde con la rama, el commit y la URL del remoto.
