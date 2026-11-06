# Guía de contribución

## Ramas

- `main`: versión estable. Aquí solo llegan las entregas.
- `develop`: integración. Todo el trabajo se junta aquí.
- `feature/HU-nn-tema`: una rama por historia de usuario. Siempre sale de `develop`.

Nunca se sube directo a `main` ni a `develop`.

## Flujo de trabajo

1. `git switch develop && git pull`
2. `git switch -c feature/HU-12-login` (usa el número de tu historia)
3. Haz commits pequeños y claros.
4. `git push -u origin feature/HU-12-login` y abre un PR hacia `develop`.
5. El PR necesita 1 aprobación y el CI en verde. Se integra con **squash merge**.
6. Borra la rama después de integrar.

Al cerrar cada sprint se crea la etiqueta `sprint-n` (por ejemplo `sprint-1`).

## Mensajes de commit (Conventional Commits)

Formato: `tipo(alcance): descripción`

Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

Ejemplos:

- `feat(pedidos): crear endpoint para listar pedidos`
- `fix(usuarios): corregir validación del correo`
- `docs: actualizar README`

## Migraciones

- El modelo y su migración van en el mismo PR.
- Antes de generar una migración: `git pull` y `python manage.py migrate`.
- Una migración ya integrada en `develop` no se edita ni se borra.
- Cada app tiene una persona responsable.

## Pruebas

- `pytest` debe pasar antes de abrir el PR.
- Nunca correr las pruebas contra la base de Supabase. Cada integrante usa su propia base Postgres local.

## Secretos

- El archivo `.env` nunca se sube. Usa `.env.example` como guía.
- Las credenciales se comparten por el gestor de contraseñas del equipo, no por chat ni por el repositorio.
