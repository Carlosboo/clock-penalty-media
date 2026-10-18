import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';

const key = process.env.ELEVENLABS_API_KEY?.trim();
const folder = process.env.VOICE_STATE_DIR;
const stateBranch = process.env.VOICE_STATE_BRANCH ?? 'elevenlabs-beta-audio';
if (!/^elevenlabs-(beta|intro)-audio$/.test(stateBranch)) {
  throw new Error('Invalid voice state branch.');
}
if (!key || !folder) throw new Error('Missing ELEVENLABS_API_KEY or VOICE_STATE_DIR.');
const request = JSON.parse(
  readFileSync(
    new URL(process.env.VOICE_REQUEST_FILE ?? './elevenlabs-beta-request.json', import.meta.url),
  ),
);
const checkpoint = () => {
  for (const args of [
    ['add', '.'],
    [
      'commit',
      '-m',
      'chore(marketing): checkpoint ElevenLabs beta narration [skip ci]',
      '-m',
      'Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>',
    ],
    ['push', 'origin', `HEAD:${stateBranch}`],
  ])
    execFileSync('git', args, { cwd: folder, stdio: 'pipe' });
};

async function api(path, body) {
  const response = await fetch(`https://api.elevenlabs.io/${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { 'xi-api-key': key, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
    redirect: 'error',
    signal: AbortSignal.timeout(90000),
  });
  if (!response.ok) {
    const error = await response.json();
    const status = error.detail?.status;
    const safeStatus =
      typeof status === 'string' && /^[a-z_]{1,80}$/.test(status) ? status : 'unspecified';
    throw new Error(
      `ElevenLabs HTTP ${response.status} (${safeStatus}). No automatic credit-spending retry.`,
    );
  }
  return response.json();
}

function voiceSummary(voice) {
  return {
    id: voice.voice_id,
    name: voice.name,
    category: voice.category,
    labels: voice.labels,
    accent: voice.accent,
    gender: voice.gender,
    language: voice.language,
    locale: voice.locale,
    descriptive: voice.descriptive,
    use_case: voice.use_case,
    free_users_allowed: voice.free_users_allowed,
    rate: voice.rate,
    public_owner_id: voice.public_owner_id,
  };
}

try {
  if (request.mode === 'discover') {
    const available = await api('v2/voices?page_size=100&gender=male');
    const shared = await api(
      'v1/shared-voices?page_size=20&gender=male&locale=es-ES&include_custom_rates=false&sort=usage_character_count_1y',
    );
    if (!Array.isArray(available.voices) || !Array.isArray(shared.voices)) {
      throw new Error('ElevenLabs returned an unexpected voices response.');
    }
    const result = {
      available: available.voices.map(voiceSummary),
      shared: shared.voices.map(voiceSummary),
    };
    writeFileSync(resolve(folder, 'voices.json'), JSON.stringify(result, null, 2) + '\n');
    checkpoint();
    console.log('Voice metadata saved. No text-to-speech credits consumed.');
  } else if (request.mode === 'generate') {
    if (!/^[A-Za-z0-9]{15,40}$/.test(request.voice?.id ?? '')) {
      throw new Error('Invalid selected voice ID.');
    }
    const allText = request.scenes.flat();
    const characters = allText.reduce((sum, text) => sum + text.length, 0);
    if (allText.length !== 12 || characters > 1500) {
      throw new Error('Unexpected narration size; refusing generation.');
    }
    const path = resolve(folder, 'narration.json');
    const state = existsSync(path)
      ? JSON.parse(readFileSync(path, 'utf8'))
      : {
          provider: 'ElevenLabs',
          model: 'eleven_multilingual_v2',
          voice: request.voice,
          clips: [],
        };
    if (state.voice.id !== request.voice.id)
      throw new Error('Voice changed; use a separate audio state.');
    console.log(`Generating up to ${characters} text characters; cached clips are reused.`);
    for (let index = 0; index < allText.length; index++) {
      const text = allText[index];
      const filename = `phrase-${String(index + 1).padStart(2, '0')}.mp3`;
      const previous = state.clips[index];
      if (previous?.complete) {
        const bytes = readFileSync(resolve(folder, previous.file));
        if (
          previous.text !== text ||
          createHash('sha256').update(bytes).digest('hex') !== previous.sha256
        ) {
          throw new Error('Cached narration differs from the requested script.');
        }
        continue;
      }
      if (previous?.attempted) {
        throw new Error(
          'Previous generation is uncertain; inspect ElevenLabs history before spending credits again.',
        );
      }
      state.clips[index] = { text, file: filename, attempted: new Date().toISOString() };
      writeFileSync(path, JSON.stringify(state, null, 2) + '\n');
      checkpoint();
      const result = await api(
        `v1/text-to-speech/${request.voice.id}/with-timestamps?output_format=mp3_44100_128`,
        {
          text,
          model_id: state.model,
          voice_settings: {
            stability: 0.45,
            similarity_boost: 0.75,
            style: 0.15,
            use_speaker_boost: true,
          },
          previous_text: allText.slice(0, index).join(' '),
          next_text: allText.slice(index + 1).join(' '),
          seed: 481,
        },
      );
      const alignment = result.alignment;
      if (
        typeof result.audio_base64 !== 'string' ||
        !alignment ||
        !Array.isArray(alignment.characters) ||
        !Array.isArray(alignment.character_start_times_seconds) ||
        !Array.isArray(alignment.character_end_times_seconds) ||
        alignment.characters.join('') !== text ||
        alignment.characters.length !== alignment.character_start_times_seconds.length ||
        alignment.characters.length !== alignment.character_end_times_seconds.length
      ) {
        throw new Error('ElevenLabs returned invalid audio/alignment; no automatic retry.');
      }
      const bytes = Buffer.from(result.audio_base64, 'base64');
      if (bytes.length < 1000) throw new Error('ElevenLabs returned empty narration.');
      writeFileSync(resolve(folder, filename), bytes);
      state.clips[index] = {
        ...state.clips[index],
        complete: true,
        alignment,
        sha256: createHash('sha256').update(bytes).digest('hex'),
      };
      writeFileSync(path, JSON.stringify(state, null, 2) + '\n');
      checkpoint();
      console.log(`Saved phrase ${index + 1}/${allText.length}.`);
    }
    console.log('Narration complete; no social content was published.');
  } else {
    throw new Error('Unknown narration operation.');
  }
} catch (error) {
  // Never print raw network exceptions or provider responses containing credentials.
  const message =
    error instanceof Error &&
    /^(ElevenLabs |Invalid |Unexpected |Voice |Cached |Previous |Unknown )/.test(error.message)
      ? error.message.replaceAll(key, '[REDACTED]')
      : 'Narration stopped due to network or checkpoint failure. Inspect persisted state before retrying.';
  console.error(message);
  process.exitCode = 1;
}
