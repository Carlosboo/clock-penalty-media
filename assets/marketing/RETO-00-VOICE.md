# Generacion privada de voz para Reto .00

El workflow manual `Generate private gameplay commentator` genera locucion en
ElevenLabs sin publicar contenido. Requiere los secretos
`ELEVENLABS_API_KEY` y `GAMEPLAY_COMMENTATOR_REQUEST` en el repositorio de
marketing. El guion se mantiene como secreto y no se copia al repo publico.

El resultado se cifra con la clave publica de esta sesion y se entrega como un
artefacto de Actions con retencion de dos dias. La clave privada no se guarda
en el repositorio. No relanzar una ejecucion fallida si una llamada de voz
pudo haberse procesado: primero inspeccionar el artefacto cifrado y confirmar
el consumo, ya que no hay reintento automatico.

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
