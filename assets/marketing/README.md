# Pilotos de Clock Penalty

> Migrado a `Carlosboo/clock-penalty-media`. Las menciones al repositorio del
> juego y a workflows/ramas de audio mas abajo son historial de produccion,
> no instrucciones para activar esas automatizaciones. La configuracion actual
> y el unico flujo de publicacion habilitado se describen en el README raiz.
> No se han trasladado secretos ni ramas privadas de audio.

## Relanzamiento con clockpenalty.com (18 de octubre de 2026)

El dominio publico del contenido nuevo es `https://clockpenalty.com/`.
Se han regenerado el anuncio inicial en video con voz ElevenLabs, el tutorial
completo, las dos historias de instalacion, los carruseles de presentacion e
instalacion, el anuncio de gameplay y las dos ediciones del video del creador.
Las capturas originales de iPhone no se modifican: sus copias ilustradas
actualizan solo las areas de direccion del navegador antes del montaje.
Las copias archivadas de versiones anteriores no son contenido para publicar.

El anuncio narrado se genera con `render_intro_video.py --narration /ruta/audio`.
Reutiliza las validaciones de guion, hashes y alineaciones de la voz del tutorial.
La nueva locucion usa una rama independiente `elevenlabs-intro-audio`, sin
invalidar ni volver a consumir creditos de los audios del tutorial aprobado.
El video muestra gameplay de desarrollo y no promete ligas ya disponibles.

El manifiesto de publicacion es `scripts/instagram-relaunch-operation.json`.
Solo contiene medios publicos, textos y tamaños: dos reels y dos historias.
Los MP4 publicos se alojan bajo un commit inmutable de `clock-penalty-media`.
El publicador comprueba identidad, disponibilidad, tipo y tamaño de los medios.
Guarda un checkpoint durable antes de cada publicacion y nunca reintenta
automaticamente una publicacion de resultado incierto.
Los secretos solo se usan dentro de Actions. La rama privada
`instagram-relaunch-state` conserva el recibo o error saneado.

La primera comprobacion real fallo antes de crear medios:
`Instagram HTTP 400; code 200; endpoint me; API access blocked.`
El token requiere revisar su autorizacion/estado en Meta. Una sesion iniciada
en Instagram web no reautoriza automaticamente la API. No considerar esta
campaña publicada sin recibos de publicacion verificados.
La alternativa web tambien indico `Video has no audio`, incluso con una copia
AAC-LC estereo; no se confirmo una publicacion con ese aviso.

Pruebas: `node --test scripts/instagram-relaunch.test.mjs scripts/elevenlabs-beta-voice.test.mjs`.
Las acciones de archivar y crear destacados son manuales o mediante interfaz
de Instagram; el publicador no pretende implementarlas con la API.

## Presentacion del creador para Reels/TikTok

### Segunda edicion: Remotion y subtitulos por palabra

`creator-pilot-v2/clock-penalty-presentacion-creador-v2.mp4` adapta tecnicas de
la [guia de @itsmarbuilds](https://marbuilds.dev/resources/efectos-video-claude-code):
checklist con entradas de muelle, iconos SVG propios, contador y progreso,
subtitulos de 1-3 palabras con resaltado sincronizado, pequeños golpes de
reencuadre, gameplay y cierre animado. No copia su video ni utiliza sus marcas.
La variante `-sin-subtitulos.mp4` conserva los rotulos y elimina los subtitulos.

Mantiene los cortes limpios y la voz original de la primera edicion. No usa
ElevenLabs ni sube la grabacion a servicios externos. No se aplican orbitas,
recorte del presentador, fondos generados o zoom 2x: no son necesarios para el
guion y el original solo tiene 576 x 1024 pixeles. La composicion se realiza con
Remotion/React; FFmpeg prepara cortes, color y mezcla con sonoridad objetivo
-14 LUFS y pico real inferior a -1 dBTP. Los tiempos proceden de faster-whisper
local y las tecnologias se anclan a palabras de la transcripcion.

Proyecto aislado: `creator-remotion/` (dependencias locales, sin instalaciones
globales). Necesita tambien el generador anterior y su entorno Python.
Flujo reproducible, desde la raiz del repositorio:

```sh
python assets/marketing/prepare_creator_remotion.py --transcript /ruta/transcript.json
cd assets/marketing/creator-remotion
npm ci
npm test
npm run render
npx remotion render src/index.jsx CreatorClean public/clean-silent.mp4 --concurrency=2 --crf=17 --codec=h264 --pixel-format=yuv420p
cd ../../..
python assets/marketing/prepare_creator_remotion.py --finish
```

Los medios de trabajo quedan ignorados en `creator-remotion/public/`.
La entrega valida decodificacion, formato, duracion, sonoridad, integridad del
bruto y copia identica en `Clock-Penalty-Anuncios/presentacion-creador-v2`.
No sobrescribe la primera edicion ni publica en redes. Revisar reproduccion y
subtitulos antes de publicar.

### Primera edicion

`creator-pilot/clock-penalty-presentacion-creador.mp4` monta la grabacion
`prueba pilot generacion de contenido.mp4` de Descargas en una pieza de unos
27 segundos. Conserva voz, rostro y ropa originales; elimina repeticiones,
ensayos y peticiones de produccion. No se ha publicado.

Incluye reencuadre y planos alternos, tarjetas e iconos animados, gameplay con
presentador en ventana, subtitulos con resaltado, limpieza y normalizacion de
audio y acentos musicales originales discretos. Turnstile se presenta como
filtro antibots, no como sustituto de la validacion de jugadas en servidor.
El gameplay es de desarrollo. La exportacion 1080 x 1920, 30 fps, H.264/AAC
escala una grabacion de 576 x 1024; no es detalle nativo Full HD.

Generador: `render_creator_pilot.py --transcript /ruta/transcript.json`.
Con `--transcribe` crea primero la transcripcion local mediante Whisper small
(requiere faster-whisper y descargar el modelo; no envia audio a un servicio).
Necesita tambien Pillow, NumPy e imageio-ffmpeg. Usa las grabaciones de Descargas
sin duplicar los originales en el repositorio.

Incluye SRT, copy, portada, storyboard y manifiesto con cortes, hash y medicion
de sonoridad/pico real. Verifica decodificacion, formato, duracion, limites de
audio y copia identica a `Clock-Penalty-Anuncios/presentacion-creador` en
Descargas. Revisar los subtitulos automaticos y escuchar antes de publicar.

## Comprobar el acceso a Instagram

El workflow manual `Check Instagram access`
(`.github/workflows/instagram-check.yml`) usa el secreto de repositorio
`INSTAGRAM_ACCESS_TOKEN`. Se ejecuta desde GitHub Actions y comprueba la
identidad de `clock.penalty` y el limite de publicacion mediante consultas GET.
Ese endpoint exige `instagram_business_basic` e
`instagram_business_content_publish`. No publica, no renueva el token y no
imprime credenciales. Una prueba correcta no sustituye a validar una
publicacion real ni configura un calendario automatico.

## Publicar el tutorial beta

El workflow manual `Publish Instagram beta tutorial` ejecuta
`scripts/instagram-beta-publish.mjs` con `INSTAGRAM_ACCESS_TOKEN`. Publica un
carrusel de seis laminas y cinco historias, en orden. Las once imagenes publicas
estan en el repositorio separado `Carlosboo/clock-penalty-media`; el script
usa una revision fija, no publica el codigo del juego.

El estado durable vive en `beta-install.json` en la rama aislada
`instagram-publishing-state`. Cada contenedor, intento y resultado se guarda
antes de continuar. La concurrencia esta serializada y las publicaciones
confirmadas no se repiten. Un intento con resultado incierto se detiene:
inspeccionar el contenedor y el perfil antes de cualquier reintento manual.
No borrar el estado para forzar una repeticion. Los contenedores no publicados
caducan a las 24 horas; su sustitucion requiere revisar primero ese estado.

Fijar publicaciones y crear el destacado se hace desde Instagram con una sesion
autenticada, no desde esta API. Las historias publicadas duran 24 horas si no se
guardan en un destacado. No se añaden stickers de enlace mediante esta API.
No hay calendario recurrente ni renovacion automatica de tokens.

Pruebas dirigidas: `node --test scripts/instagram-beta-publish.test.mjs`.

Publicacion del 16/10/2026 confirmada por la API:
https://www.instagram.com/p/DekRlwOFnJ8/ y cinco historias en orden.
Registro en `beta-install/published.json` y ejecucion
https://github.com/Carlosboo/penalty/actions/runs/38954415255.
Pendientes por falta de sesion autenticada: fijar el tutorial y la presentacion
inicial, y crear el destacado. No se ha modificado la presentacion inicial.

## Anuncio con grabaciones reales

`gameplay-ad/clock-penalty-gameplay-30s.mp4`: montaje vertical de 30 segundos
con gol, penalti fallado, club, avatar y clasificacion de liga. Textos en primera
persona; musica y efectos originales sintetizados localmente. Sin publicacion
automatica ni subida a servicios externos.

Exporta H.264/AAC, 1080 x 1920, 30 fps. Las grabaciones originales tienen
464/480 pixeles de ancho: se escalan sin recortar la interfaz, no son Full HD
nativo. La demo publica puede ir por detras de las funciones grabadas.
`caption.txt` contiene el pie sugerido y `manifest.json` los cortes y hash.
Las fuentes se leen desde Windows y no se duplican en el repositorio.

```sh
python assets/marketing/render_gameplay_ad.py \
  --source "/mnt/c/Users/juan.crugeiras/Downloads/Clock-Penalty-Anuncios/videos aplicacion"
```

El script verifica decodificacion, duracion, dimensiones, audio y copia identica
en la carpeta `promocional-gameplay` junto a las grabaciones originales.

## Imagen de perfil

`clock-penalty-social-avatar.png` (1024 x 1024) y su variante
`clock-penalty-social-avatar-320.png` usan la paleta del icono de la app,
con margen para recorte circular. Se regeneran con
`python assets/marketing/render_social_avatar.py` (Pillow y NumPy).

## Primera publicacion de Instagram

`social-intro/` contiene cuatro imagenes 1080 x 1350, el texto de la
publicacion y la bio con la URL de la demo. El tono es el del creador en primera
persona, sin anunciar multijugador publico ni inventar testimonios.
Se regenera con `python assets/marketing/render_intro_post.py` (Pillow).
El manifiesto generado es un borrador: no publica ni programa contenido.
El enlace clicable del perfil debe configurarse desde la app de Instagram;
incluir la URL en la bio no equivale a configurar ese enlace.

## Guia de instalacion beta para Instagram

`beta-install/pinned-carousel/` contiene seis laminas 1080 x 1350 para publicar
como un carrusel pineable; `beta-install/stories/` contiene cinco historias
1080 x 1920 para publicar en orden y guardar en el destacado «Instalacion Beta».
Incluye `highlight-cover-instalacion-beta.jpg`, `caption.txt` y `README.txt`.
La guia usa las capturas iPhone aportadas por el usuario; las pantallas Android
son ilustraciones, no capturas literales de Chrome. La opcion de instalacion
puede variar por navegador y dispositivo.

Se regenera con `python assets/marketing/render_beta_install.py` (Pillow).
El script busca las capturas en `contenido aplicacion` y copia los resultados
a `instagram-beta-install` en la carpeta de anuncios de Windows cuando esta
disponible. Comprueba la validez de los JPG y la igualdad de bytes copiados.
La generacion no publica ni programa contenido.

### Tutorial en video con voz y animaciones

`beta-install-video/clock-penalty-instalacion-beta-voz.mp4` es una version
vertical con locucion de ElevenLabs en español de España
(`Pedro - Spanish Clear Narrator`, modelo `eleven_multilingual_v2`),
subtitulos integrados, entradas animadas, zoom del logo, transiciones e
indicadores pulsantes sobre las opciones de instalacion.
Es voz sintetica neuronal de catalogo; no se ha clonado la voz del creador.

Incluye `historia-iphone.mp4`, `historia-android.mp4`, `subtitulos.srt`,
`locucion.txt`, `storyboard.jpg` y `manifest.json` con duraciones y hashes.
Android sigue siendo una ilustracion orientativa. La salida es 1080 x 1920,
30 fps, H.264/AAC; las capturas originales escaladas no ganan detalle nativo.
No sustituye ni vuelve a publicar las piezas ya subidas.

Se genera con `python assets/marketing/render_beta_install_video.py --narration
/ruta/audio`, usando las historias JPG y el avatar existentes.
Necesita Pillow, NumPy e imageio-ffmpeg. No tiene fallback a eSpeak.
Comprueba hashes de audio, guion y alineacion de caracteres de ElevenLabs
para recalcular subtitulos y duracion de cada escena. Tambien verifica
decodificacion completa, dimensiones, duracion, sonoridad y pico real,
y copia los resultados con verificacion de bytes a `instagram-beta-video`
en la carpeta de anuncios de Windows. Incluye la locucion en MP3.

La generacion de voz ocurre solo en Actions, con `ELEVENLABS_API_KEY` como
secreto, mediante `scripts/elevenlabs-beta-voice.mjs`. El texto del tutorial
se envia a ElevenLabs; no se envian capturas, videos ni credenciales de otros
servicios. Las doce frases se generan una vez y los audios/alineaciones quedan
en la rama privada `elevenlabs-beta-audio`; el render local no requiere la clave.
Se guarda un checkpoint antes de cada solicitud: un resultado incierto no
se repite automaticamente, para evitar cargos duplicados. No hay musica ni
efectos de pago, publicacion social o clonacion de voces.
La rama `elevenlabs-beta-narration` activa el workflow acotado; la operacion
`discover` solo consulta voces y `generate` consume los creditos autorizados.

Pruebas: `node --test scripts/elevenlabs-beta-voice.test.mjs` y
`python -m unittest discover -s assets/marketing -p test_beta_install_video.py`.
Las versiones roboticas anteriores se conservan en `version-anterior-robotica`.

## Pilotos de video

- `clock-penalty-pilot.mp4`: primer piloto, 28 segundos.
- `clock-penalty-pilot-enhanced.mp4`: nueva direccion visual del primer piloto,
  28 segundos, exportado a 1080 x 1920 y 30 fps. Redibuja iluminacion del
  estadio, sombreado de personajes y balon, atmosfera, movimiento de camara
  y deformacion de la red. Conserva los tiempos 89:01/90:00, el audio original
  sintetizado y el marcador J1/J2. No incluye rotulos internos.
  El render base sigue siendo de 720 x 1280 y se escala con Lanczos al exportar:
  no es detalle nativo Full HD ni regeneracion mediante IA.
- `clock-penalty-pilot-v2.mp4`: montaje de 38 segundos alternando amigos con ropa
  de calle y el partido imaginado. Cada amigo sostiene un cronómetro redondo
  de mano con botón físico arriba a la derecha, sin móviles. Azul pulsa y para
  en 89:01; después falla.
  Rojo arranca en 89:01, el reloj avanza en cámara lenta durante la jugada,
  toca y para en 90:00. Gol, celebración de rodillas y cierre.

Son animaciones promocionales originales 2D, no capturas del juego.
La música, los efectos y las voces se sintetizan localmente. El sonido de voz
es sintético, no una grabación de público real.

## Regenerar

En un entorno virtual de Python instala `pillow`, `numpy`, `imageio-ffmpeg`
y `espeakng-loader`. Se necesitan las fuentes DejaVu en la ruta indicada en
`render_pilot.py`. No se utilizan servicios de IA externos ni claves.

```sh
python assets/marketing/render_pilot_v2.py \
  --output assets/marketing/clock-penalty-pilot-v2.mp4
python assets/marketing/render_pilot_enhanced.py \
  --output assets/marketing/clock-penalty-pilot-enhanced.mp4
```

`--preview-only` genera la hoja de fotogramas sin codificar el vídeo. Ambos
modos comprueban continuidad de escenas, estados del reloj y forma de los
fotogramas. El render final verifica la decodificación completa del MP4.

Los relojes 89:01 y 90:00 son recursos narrativos solicitados para el anuncio,
no una modificación de las reglas ni del límite de posesión del juego.

## Serie de cuatro anuncios

Los originales anteriores se conservan. Los nuevos vídeos están en `campaign/`:

| Archivo | Duración | Concepto |
|---|---|---|
| `01-clock-penalty-v3.mp4` | 38 s | Versión corregida: J1/J2, cronómetros de mano, sin rótulos internos |
| `02-clock-penalty-descenso.mp4` | 40 s | Última jornada: PLAYER1 marca el penalti en 92:12, pero el empate salva a PLAYER2 |
| `03-clock-penalty-un-toque.mp4` | 38 s | Remontada en arena de neón, palo, penalti y último intento; percusión y sintetizadores |
| `04-clock-penalty-no-es-un-reloj.mp4` | 38 s | Concepto minimalista monocromático: el cronómetro se transforma en estadio y portería |

La historia de descenso parte de PLAYER1 con 7 puntos y PLAYER2 con 8.
La victoria provisional de PLAYER2 lo lleva a 11; el empate final deja
PLAYER2 en 9 y PLAYER1 en 8. El resto de resultados deja el corte entre
las posiciones 7 y 8. Así PLAYER2 celebra salvarse aunque haya recibido
el gol del empate. Los puntos de la tabla son provisionales durante el partido.

Los tres anuncios nuevos tienen música original sintetizada diferente.
No incorporan música, escenas ni personajes de otras franquicias.
No se publican automáticamente ni se suben a servicios externos.

```sh
python assets/marketing/render_campaign.py --all
python assets/marketing/render_campaign.py --all --preview-only
python assets/marketing/render_campaign.py --campaign league
```

Cada render incluye una hoja de fotogramas y un póster. El generador valida
el relato y la forma de la imagen; FFmpeg comprueba la decodificación completa.
Las versiones para público no incluyen «piloto visual» ni «animación promocional».
