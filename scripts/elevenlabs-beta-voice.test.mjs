import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';
import { basename } from 'node:path';
import test from 'node:test';

const source = readFileSync(new URL('./elevenlabs-beta-voice.mjs', import.meta.url), 'utf8')
  .replace(/^import .*;\n/gm, '')
  .replaceAll('import.meta.url', "'file:///app/scripts/elevenlabs-beta-voice.mjs'");
const request = JSON.parse(
  readFileSync(new URL('./elevenlabs-beta-request.json', import.meta.url)),
);
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

async function simulate({ mode = 'generate', error = false, networkError = false, initial } = {}) {
  const files = new Map([['elevenlabs-beta-request.json', JSON.stringify({ ...request, mode })]]);
  if (initial) for (const [name, value] of initial) files.set(name, value);
  const logs = [],
    calls = [];
  const process = {
    env: { ELEVENLABS_API_KEY: 'test-private-key', VOICE_STATE_DIR: '/audio' },
    exitCode: 0,
  };
  const execute = new AsyncFunction(
    'process',
    'readFileSync',
    'writeFileSync',
    'existsSync',
    'execFileSync',
    'resolve',
    'createHash',
    'fetch',
    'console',
    source,
  );
  await execute(
    process,
    (file) => {
      const value = files.get(basename(String(file)));
      if (value === undefined) throw new Error('Missing test file');
      return value;
    },
    (file, value) => files.set(basename(file), value),
    (file) => files.has(basename(file)),
    () => {},
    (...parts) => parts.join('/'),
    createHash,
    async (url, options) => {
      assert.equal(options.headers['xi-api-key'], 'test-private-key');
      assert.equal(options.redirect, 'error');
      assert.ok(url.startsWith('https://api.elevenlabs.io/'));
      assert.equal(url.includes('test-private-key'), false);
      calls.push({ url, options });
      if (networkError) throw new Error('test-private-key');
      if (error)
        return {
          ok: false,
          status: 401,
          json: async () => ({
            detail: { status: 'invalid_api_key', message: 'test-private-key' },
          }),
        };
      if (options.method === 'GET') return { ok: true, json: async () => ({ voices: [] }) };
      const body = JSON.parse(options.body);
      assert.equal(body.model_id, 'eleven_multilingual_v2');
      return {
        ok: true,
        json: async () => ({
          audio_base64: Buffer.alloc(2000, 1).toString('base64'),
          alignment: {
            characters: [...body.text],
            character_start_times_seconds: [...body.text].map((_, i) => i / 20),
            character_end_times_seconds: [...body.text].map((_, i) => (i + 1) / 20),
          },
        }),
      };
    },
    { log: (value) => logs.push(value), error: (value) => logs.push(value) },
  );
  assert.equal(logs.join('\n').includes('test-private-key'), false);
  for (const value of files.values())
    assert.equal(String(value).includes('test-private-key'), false);
  return { files, logs, calls, exitCode: process.exitCode };
}

test('discovery does not generate paid speech', async () => {
  const result = await simulate({ mode: 'discover' });
  assert.equal(result.exitCode, 0);
  assert.equal(result.calls.length, 2);
  assert.ok(result.calls.every((call) => call.options.method === 'GET'));
  assert.ok(result.files.has('voices.json'));
});

test('generation produces exactly twelve cached clips and reuses them', async () => {
  const result = await simulate();
  assert.equal(result.exitCode, 0);
  assert.equal(result.calls.length, 12);
  const state = JSON.parse(result.files.get('narration.json'));
  assert.equal(state.clips.length, 12);
  assert.ok(state.clips.every((clip) => clip.complete));
  const rerun = await simulate({ initial: result.files });
  assert.equal(rerun.exitCode, 0);
  assert.equal(rerun.calls.length, 0);
});

test('provider rejection and network failure do not retry or leak credentials', async () => {
  for (const options of [{ error: true }, { networkError: true }]) {
    const result = await simulate(options);
    assert.equal(result.exitCode, 1);
    assert.equal(result.calls.length, 1);
    const rerun = await simulate({ initial: result.files });
    assert.equal(rerun.exitCode, 1);
    assert.equal(rerun.calls.length, 0);
  }
});

test('changed cached script is rejected before spending credits', async () => {
  const result = await simulate();
  const state = JSON.parse(result.files.get('narration.json'));
  state.clips[0].text = 'different text';
  result.files.set('narration.json', JSON.stringify(state));
  const rerun = await simulate({ initial: result.files });
  assert.equal(rerun.exitCode, 1);
  assert.equal(rerun.calls.length, 0);
});
