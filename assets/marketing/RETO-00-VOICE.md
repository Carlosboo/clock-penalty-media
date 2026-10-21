# Generacion privada de voz para Reto .00

El workflow manual `Generate private gameplay commentator` genera locucion en
ElevenLabs sin publicar contenido. Requiere el secreto `ELEVENLABS_API_KEY` en
el repositorio de marketing. El guion esta en
`scripts/gameplay-commentator-request.json`; no contiene datos personales.

El resultado se cifra con la clave publica de esta sesion y se entrega como un
artefacto de Actions con retencion de dos dias. La clave privada no se guarda
en el repositorio. No relanzar una ejecucion fallida si una llamada de voz
pudo haberse procesado: primero inspeccionar el artefacto cifrado y confirmar
el consumo, ya que no hay reintento automatico.
El paquete cifrado se actualiza antes y despues de cada peticion. Actions
intenta conservarlo incluso si falla la generacion; una cancelacion abrupta
puede impedir su subida. No considerar la ausencia del artefacto prueba de
que no se consumieron creditos.

Descifrar el artefacto en un directorio privado:

```sh
node scripts/unpack-gameplay-voice-preview.mjs \
  /ruta/privada/voice-preview.enc.json \
  /ruta/privada/private.pem \
  /ruta/privada/narration
```

Si la ejecucion falla, inspeccionar primero el checkpoint cifrado sin extraer
audio:

```sh
node scripts/unpack-gameplay-voice-preview.mjs \
  /ruta/privada/voice-preview.enc.json \
  /ruta/privada/private.pem \
  --inspect
```

Con las grabaciones de gameplay disponibles, generar el MP4 de revision:

```sh
python assets/marketing/render_commentated_reto00.py \
  --source /ruta/grabaciones \
  --narration /ruta/privada/narration \
  --output /ruta/privada/reto-00
```

El renderer valida hashes y alineaciones de voz, reemplaza los datos privados
del partido antes de escalar, comprueba formato vertical, duracion de 20-25
segundos y audio, y genera portada, storyboard y fotogramas de revision.
Preparar el borrador no autoriza publicarlo.

La version narrada exportada dura 24,3 segundos a 1080x1920 y 30 fps, con AAC
estereo. La parada y la repeticion se temporizan con los clips de la locucion;
la repeticion se identifica expresamente. Mantiene el CTA solicitado:
«Invita a tu amigo a jugar ahora en clockpenalty.com».
El reproductor HTML y los medios quedan en el directorio privado de salida,
no en el repositorio publico.

Pruebas directamente relacionadas:

```sh
node --test scripts/gameplay-voice-preview.test.mjs
python -m unittest discover -s assets/marketing -p 'test_*reto00.py'
python -m unittest discover -s assets/marketing -p test_gameplay_preview.py
```
