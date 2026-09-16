# Valencia Briefing API

Aplicación de Home Assistant que recoge noticias y eventos de Valencia desde
feeds RSS/Atom, los filtra, deduplica y prioriza, y publica el resultado por
HTTP para el briefing matutino.

Este repositorio es una copia inicial del código que está ejecutándose en Home
Assistant. No incluye la caché, las opciones de ejecución ni datos personales.

## Estructura

- `repository.yaml`: metadatos del repositorio para la Store de Home Assistant.
- `valencia-briefing-api/`: la aplicación instalable.

## API

- `GET /`: estado y opciones activas.
- `GET /valencia_briefing`: noticias y eventos usando caché persistente.
- `GET /refresh`: invalida la caché y vuelve a generar el resultado.
- `GET /debug`: ejecuta el pipeline e incluye información por fuente.

## Datos persistentes

La App guarda la caché en `/data/briefing_cache.json` y admite un archivo de
feeds de usuario en `/config/valencia_briefing_feeds.yaml`. Ambos quedan fuera
del control de versiones.
