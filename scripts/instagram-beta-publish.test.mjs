import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(
  new URL('./instagram-beta-publish.mjs', import.meta.url),
  'utf8',
).replace(/^import .*;\n/gm, '');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

async function simulate({
  initial = {},
  failPublish = false,
  checkpointFailure = false,
  wrongAccount = false,
  recovered = false,
  unavailable = false,
} = {}) {
  let saved = JSON.stringify(initial);
  const logs = [];
  const calls = [];
  const process = {
    env: {
      INSTAGRAM_ACCESS_TOKEN: 'test-secret',
      PUBLISH_STATE_DIR: '/state',
      GITHUB_STEP_SUMMARY: '/summary',
    },
    exitCode: 0,
  };
  const run = new AsyncFunction(
    'process',
    'readFileSync',
    'writeFileSync',
    'appendFileSync',
    'execFileSync',
    'resolve',
    'fetch',
    'console',
    source,
  );
  let serial = 100;
  const fetch = async (url, options) => {
    calls.push({ url: String(url), method: options.method, body: options.body });
    if (options.method === 'HEAD') {
      return { ok: !unavailable, headers: new Map([['content-type', 'image/jpeg']]) };
    }
    assert.equal(options.headers.Authorization, 'Bearer test-secret');
    assert.equal(options.redirect, 'error');
    assert.equal(String(url).includes('test-secret'), false);
    const path = new URL(url).pathname;
    if (path.endsWith('/media_publish') && failPublish) throw new Error('test-secret');
    let body;
    if (path.endsWith('/me')) {
      body = { username: wrongAccount ? 'other' : 'clock.penalty', user_id: '17841459544818975' };
    } else if (options.method === 'POST') {
      body = { id: String(++serial) };
    } else if (new URL(url).searchParams.get('fields') === 'permalink') {
      body = { permalink: 'https://www.instagram.com/p/test/' };
    } else {
      body = { status_code: recovered && path.endsWith('/101') ? 'PUBLISHED' : 'FINISHED' };
    }
    return { ok: true, json: async () => body };
  };
  await run(
    process,
    () => saved,
    (file, content) => {
      saved = content;
    },
    () => {},
    () => {
      if (checkpointFailure) throw new Error('git failure');
    },
    (...parts) => parts.join('/'),
    fetch,
    { log: (message) => logs.push(message), error: (message) => logs.push(message) },
  );
  assert.equal(logs.join('\n').includes('test-secret'), false);
  return { state: JSON.parse(saved), calls, exitCode: process.exitCode };
}

test('publishes one six-slide carousel and five stories in order', async () => {
  const result = await simulate();
  assert.equal(result.exitCode, 0);
  const posts = result.calls.filter((call) => call.method === 'POST');
  assert.equal(posts.filter((call) => call.url.endsWith('/media')).length, 12);
  assert.equal(posts.filter((call) => call.url.endsWith('/media_publish')).length, 6);
  assert.equal(result.state.carousel.permalink, 'https://www.instagram.com/p/test/');
  for (let index = 1; index <= 5; index++) {
    assert.equal(result.state[`story-${index}`].published, true);
  }
  const rerun = await simulate({ initial: result.state });
  assert.equal(rerun.exitCode, 0);
  assert.equal(rerun.calls.filter((call) => call.method === 'POST').length, 0);
});

test('uncertain publication is checkpointed and never automatically resent', async () => {
  const failed = await simulate({ failPublish: true });
  assert.equal(failed.exitCode, 1);
  assert.ok(failed.state.carousel.attempted);
  const retry = await simulate({ initial: failed.state });
  assert.equal(retry.exitCode, 1);
  assert.equal(retry.calls.filter((call) => call.method === 'POST').length, 0);
});

test('confirmed prior publication is recovered without republishing it', async () => {
  const initial = { carousel: { container: '101', attempted: 'earlier' } };
  for (let index = 1; index <= 6; index++) initial[`slide-${index}`] = { container: String(index) };
  const result = await simulate({ initial, recovered: true });
  assert.equal(result.state.carousel.published, true);
  assert.equal(
    result.calls.some((call) => call.body === '{"creation_id":"101"}'),
    false,
  );
});

test('wrong account and missing public image stop before any writes', async () => {
  for (const options of [{ wrongAccount: true }, { unavailable: true }]) {
    const result = await simulate(options);
    assert.equal(result.exitCode, 1);
    assert.equal(result.calls.filter((call) => call.method === 'POST').length, 0);
  }
});

test('failed durable checkpoint prevents publication', async () => {
  const result = await simulate({ checkpointFailure: true });
  assert.equal(result.exitCode, 1);
  assert.equal(result.calls.filter((call) => call.url.endsWith('/media_publish')).length, 0);
});
