import { readFileSync, writeFileSync, appendFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const token = process.env.INSTAGRAM_ACCESS_TOKEN?.trim();
const stateDir = process.env.PUBLISH_STATE_DIR;
const accountId = '17841459544818975';
const base =
  'https://raw.githubusercontent.com/Carlosboo/clock-penalty-media/4cd94cd34507c616de3066604f4fb51fcbadb671';
const caption =
  'Estoy dejando aquí cómo instalar la beta en iPhone y Android. ' +
  'No hace falta bajarla de una tienda: es la web de prueba añadida a la pantalla de inicio.\n\n' +
  'iPhone: Safari → Compartir → Añadir a pantalla de inicio.\n' +
  'Android: Chrome → ⋮ → Instalar aplicación o Añadir a pantalla de inicio.\n\n' +
  'Abre https://clock-penalty.pages.dev/ en tu navegador, no dentro de Instagram. ' +
  'Los nombres de las opciones pueden variar un poco según el móvil.\n\n' +
  'Después abre Penalty desde el icono y prueba la demo. ' +
  'Si algo no te funciona, escríbeme qué móvil y navegador usas.';

if (!token || !stateDir) {
  throw new Error('Required secret or publishing-state directory is missing.');
}
const stateFile = resolve(stateDir, 'beta-install.json');
const state = JSON.parse(readFileSync(stateFile, 'utf8'));

function save() {
  writeFileSync(stateFile, `${JSON.stringify(state, null, 2)}\n`);
  for (const args of [
    ['add', 'beta-install.json'],
    [
      'commit',
      '-m',
      'chore(marketing): checkpoint beta publication [skip ci]',
      '-m',
      'Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>',
    ],
    ['push', 'origin', 'HEAD:instagram-publishing-state'],
  ]) {
    execFileSync('git', args, { cwd: stateDir, stdio: 'pipe' });
  }
}

async function api(path, params = {}, method = 'GET') {
  const url = new URL(`https://graph.instagram.com/v25.0/${path}`);
  const options = {
    method,
    headers: { Authorization: `Bearer ${token}` },
    redirect: 'error',
    signal: AbortSignal.timeout(30000),
  };
  if (method === 'GET') url.search = new URLSearchParams(params).toString();
  else {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(params);
  }
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok || body.error) {
    const code = Number.isInteger(body.error?.code) ? body.error.code : 'unknown';
    const subcode = Number.isInteger(body.error?.error_subcode) ? body.error.error_subcode : 'none';
    throw new Error(`Instagram HTTP ${response.status}, code ${code}, subcode ${subcode}.`);
  }
  return body;
}

async function ready(id) {
  for (let attempt = 0; attempt < 6; attempt++) {
    const result = await api(id, { fields: 'status_code' });
    if (result.status_code === 'FINISHED') return;
    if (result.status_code !== 'IN_PROGRESS') {
      throw new Error('Instagram container is not eligible for publication.');
    }
    if (attempt < 5) await new Promise((resolve) => setTimeout(resolve, 60000));
  }
  throw new Error('Instagram container processing timed out; resume later.');
}

async function container(key, params) {
  if (state[key]?.container) return state[key].container;
  const result = await api(`${accountId}/media`, params, 'POST');
  if (!/^\d+$/.test(result.id)) throw new Error('Instagram returned an invalid container ID.');
  state[key] = { container: result.id };
  save();
  return result.id;
}

async function publish(key, id) {
  if (state[key].published) {
    console.log(`${key}: already published; skipped.`);
    return;
  }
  if (state[key].attempted) {
    const status = await api(id, { fields: 'status_code' });
    if (status.status_code === 'PUBLISHED') {
      state[key].published = true;
      save();
      console.log(`${key}: confirmed previously published.`);
      return;
    }
    throw new Error(
      'Previous publish attempt is uncertain; inspect state before retrying. No duplicate sent.',
    );
  }
  await ready(id);
  state[key].attempted = new Date().toISOString();
  save();
  const result = await api(`${accountId}/media_publish`, { creation_id: id }, 'POST');
  if (!/^\d+$/.test(result.id))
    throw new Error('Instagram returned an invalid published media ID.');
  state[key].published = true;
  state[key].mediaId = result.id;
  save();
  console.log(`${key}: published, media ID ${result.id}.`);
  if (key === 'carousel') {
    const media = await api(result.id, { fields: 'permalink' });
    if (
      typeof media.permalink !== 'string' ||
      !media.permalink.startsWith('https://www.instagram.com/')
    ) {
      throw new Error('Instagram returned an unexpected permalink.');
    }
    state[key].permalink = media.permalink;
    save();
  }
}

try {
  const account = await api('me', { fields: 'user_id,username,account_type' });
  if (account.username !== 'clock.penalty' || String(account.user_id) !== accountId) {
    throw new Error('Unexpected Instagram account; refusing to publish.');
  }
  // Preflight every image before creating any media containers.
  for (const [directory, count] of [
    ['carousel', 6],
    ['story', 5],
  ]) {
    for (let index = 1; index <= count; index++) {
      const url = `${base}/${directory}-${String(index).padStart(2, '0')}.jpg`;
      const response = await fetch(url, { method: 'HEAD', signal: AbortSignal.timeout(20000) });
      if (!response.ok || !response.headers.get('content-type')?.includes('image/jpeg')) {
        throw new Error('Public tutorial image unavailable; refusing to publish.');
      }
    }
  }
  if (!state.carousel?.published) {
    const children = [];
    for (let index = 1; index <= 6; index++) {
      const id = await container(`slide-${index}`, {
        image_url: `${base}/carousel-${String(index).padStart(2, '0')}.jpg`,
        is_carousel_item: true,
      });
      await ready(id);
      children.push(id);
    }
    const id = await container('carousel', { media_type: 'CAROUSEL', children, caption });
    await publish('carousel', id);
  }
  for (let index = 1; index <= 5; index++) {
    const key = `story-${index}`;
    if (state[key]?.published) continue;
    const id = await container(key, {
      image_url: `${base}/story-${String(index).padStart(2, '0')}.jpg`,
      media_type: 'STORIES',
    });
    await publish(key, id);
  }
  appendFileSync(
    process.env.GITHUB_STEP_SUMMARY,
    `## Tutorial beta publicado\n\nCarrusel: ${state.carousel.permalink ?? state.carousel.mediaId}\n\n` +
      'Cinco historias publicadas en orden. El fijado y el destacado requieren Instagram.\n',
  );
} catch (error) {
  // Transport errors and API response bodies may contain credentials.
  const message =
    error instanceof Error &&
    /^(Instagram |Unexpected Instagram |Public tutorial |Previous publish )/.test(error.message)
      ? error.message.replaceAll(token, '[REDACTED]')
      : 'Publishing stopped due to a network, state or validation error. Inspect the persisted state before retrying.';
  console.error(message);
  process.exitCode = 1;
}
