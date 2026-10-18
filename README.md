# Clock Penalty: marketing y contenido publico

## Publicaciones actuales con portada

El 18/10/2026 se sustituyeron los reels archivados por el usuario:

- [Presentacion a 1,15x con portada](https://www.instagram.com/reel/DepUeYLGiA0/) (52,4 s).
- [Tutorial a velocidad original con portada](https://www.instagram.com/reel/DepUpVfASZ5/) (58,3 s).

Se enviaron `cover_url` explicitas y se comprobaron las dos portadas en la
cuadricula del perfil. No se republicaron historias. Recibo independiente:
`reels-covers-v2.json` en la rama `instagram-relaunch-state`.
El workflow `Publish two reels with covers` queda manual y en `hold`.
La campaña anterior y sus recibos se conservan como historial.

Repositorio independiente del juego para generadores de contenido, pruebas,
publicaciones y medios publicos de [Clock Penalty](https://clockpenalty.com).
El codigo del juego sigue en `Carlosboo/penalty`.

## Seguridad y alcance

Este repositorio es **publico**, incluidos su codigo, sus ramas y los logs de
Actions. No subir grabaciones personales sin aprobar, archivos `.env`, claves,
tokens, historiales de proveedor ni estados privados del repositorio del juego.
Los MP4 de `relaunch/` son exportaciones finales aprobadas para publicacion.
Las imagenes anteriores de la raiz conservan URLs inmutables para referencias
historicas; el contenido nuevo utiliza `clockpenalty.com`.

Los generadores estan en `assets/marketing/`; los publicadores y sus pruebas,
en `scripts/`. Las rutas de grabaciones Windows de los generadores son rutas
locales: no incluyen las grabaciones. Ajustarlas a tu entorno antes de renderizar.
Ver [la documentacion de produccion](assets/marketing/README.md).

## Actions: no se publica automaticamente

- **Marketing tests**: ejecuta tests sin secretos cuando cambia codigo de
  marketing, no cuando se sube un MP4 o se guarda un checkpoint.
- **Check Instagram access**: manual y de solo lectura.
- **Publish Clock Penalty marketing**: manual; ademas exige cambiar `mode`
  de `hold` a `publish` en `scripts/instagram-relaunch-operation.json`.
  Mientras esta en `hold`, no consulta la API, no publica y no genera voz.

Las ramas `instagram-relaunch-state` contienen solo checkpoints de esta
campaña (IDs publicos, estados y errores saneados), no secretos.
Antes de activar una campaña futura hay que conservar/reconciliar los IDs
publicados: no reinicializar el estado para reintentar una publicacion incierta.

## Configuracion pendiente de Instagram

Los secretos de un repositorio **no se trasladan automaticamente** ni pueden
leerse para copiarlos. Guarda el token renovado en:

https://github.com/Carlosboo/clock-penalty-media/settings/secrets/actions

Nombre: `INSTAGRAM_ACCESS_TOKEN`.

Despues ejecuta **Check Instagram access**. El intento anterior en el repositorio del juego fallo antes de crear
contenedores: `API access blocked`. El 18/10/2026, tras restablecer el acceso
de Meta y configurar el token aqui, la comprobacion y publicacion terminaron
correctamente:

- [Comprobacion de acceso](https://github.com/Carlosboo/clock-penalty-media/actions/runs/39152423620).
- [Publicacion verificada](https://github.com/Carlosboo/clock-penalty-media/actions/runs/39152469296).
- [Presentacion](https://www.instagram.com/reel/DepSNgNFcgh/).
- [Tutorial](https://www.instagram.com/reel/DepSUsBCowq/).
- Historias iPhone `18117134008954918` y Android `18110122307099601`.

El recibo durable esta en `instagram-relaunch-state/relaunch.json` (rama de
estado); `complete: true` y las cuatro entradas verificadas confirman la entrega.
La campaña ha vuelto a `hold` y los disparadores temporales de comprobacion y
publicacion se han retirado. No hay trabajos de publicacion en curso.
La creacion del destacado sigue pendiente: el selector web de historias
no mostro elementos seleccionables inmediatamente despues de publicarlas.

## ElevenLabs

Los scripts de generacion y sus pruebas estan aqui, pero no se han copiado las
ramas privadas de audio ni se ha habilitado un workflow de generacion en este
repositorio publico. No hace falta generar voz para publicar los MP4 terminados.
La automatizacion anterior del juego queda retirada; configurar una nueva
generacion exige elegir almacenamiento apropiado y aportar la clave mediante
secretos, nunca dentro del codigo. No se han consumido creditos por esta migracion.

## Validacion local

```sh
node --test scripts/*.test.mjs assets/marketing/creator-remotion/src/timeline.test.mjs
```

Las pruebas Python del tutorial requieren Pillow, NumPy e imageio-ffmpeg:

```sh
python -m unittest discover -s assets/marketing -p test_beta_install_video.py
```

Los scripts historicos `instagram-beta-publish.mjs` se conservan como referencia,
sin workflow de ejecucion. No usarlos para la campaña nueva.
