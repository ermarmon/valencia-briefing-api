#!/usr/bin/env sh
set -e

# Copiar feeds.yaml de /config a /data si no existe ya en /data
# Esto permite que el usuario edite el archivo desde el File Editor de HA
# sin necesidad de reconstruir el add-on.
if [ -f /config/valencia_briefing_feeds.yaml ]; then
    echo "[vb2] Cargando feeds.yaml desde /config..."
    cp /config/valencia_briefing_feeds.yaml /data/feeds.yaml

# Si tampoco está en /config, usar el feeds.yaml empaquetado en la imagen
elif [ ! -f /data/feeds.yaml ]; then
    echo "[vb2] Usando feeds.yaml por defecto empaquetado en la imagen..."
    cp /app/src/feeds_default.yaml /data/feeds.yaml
fi

echo "[vb2] Valencia Briefing API v2.1.1 arrancando en puerto 8099..."
exec python3 -m uvicorn src.app:app \
    --host 0.0.0.0 \
    --port 8099 \
    --log-level info
