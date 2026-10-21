import { createCipheriv, createHash, publicEncrypt, randomBytes, constants } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { resolve } from "node:path";

const EXPECTED_CLIPS = 12;

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

export async function generateCommentary({ request, state, key, api, save, outputDir }) {
  const textItems = Array.isArray(request?.scenes) ? request.scenes.flat() : [];
  const settings = request?.voiceSettings ?? {};
  const settingLimits = {
    stability: [0, 1],
    similarity_boost: [0, 1],
    style: [0, 1],
    speed: [0.7, 1.2],
  };
  if (
    !key ||
    !request ||
    !/^[A-Za-z0-9]{15,40}$/.test(request.voice?.id ?? "") ||
    !Array.isArray(request.scenes) ||
    request.scenes.some((scene) => !Array.isArray(scene) || scene.length !== 2) ||
    textItems.length !== EXPECTED_CLIPS ||
    textItems.some((text) => typeof text !== "string" || text.length === 0 || text.length > 180) ||
    textItems.reduce((total, text) => total + text.length, 0) > 1000 ||
    Object.entries(settings).some(([name, value]) => {
      if (name === "use_speaker_boost") return typeof value !== "boolean";
      const range = settingLimits[name];
      return !range || !Number.isFinite(value) || value < range[0] || value > range[1];
    })
  ) {
    throw new Error("Invalid gameplay narration request.");
  }
  if (!state || typeof state !== "object" || Array.isArray(state)) {
    throw new Error("Invalid durable narration state.");
  }
  const requestHash = sha256(JSON.stringify(request));
  if (state.requestHash && state.requestHash !== requestHash) {
    throw new Error("Narration request changed; refusing to reuse generation state.");
  }
  state.requestHash = requestHash;
  state.voice = request.voice;
  state.voiceSettings = request.voiceSettings;
  state.clips ??= [];
  save();

  const texts = request.scenes.flat();
  for (let i = 0; i < texts.length; i++) {
    const text = texts[i];
    const previous = state.clips[i];
    if (previous?.complete) continue;
    if (previous?.attempted) {
      throw new Error("A previous voice request is uncertain; no automatic retry.");
    }

    state.clips[i] = { text, attempted: new Date().toISOString() };
    save();
    const result = await api(request.voice.id, {
      text,
      model_id: "eleven_multilingual_v2",
      voice_settings: request.voiceSettings,
      previous_text: texts.slice(0, i).join(" "),
      next_text: texts.slice(i + 1).join(" "),
      seed: 481 + i,
    });
    const alignment = result.alignment;
    if (
      typeof result.audio_base64 !== "string" ||
      !alignment ||
      !Array.isArray(alignment.characters) ||
      !Array.isArray(alignment.character_start_times_seconds) ||
      !Array.isArray(alignment.character_end_times_seconds) ||
      alignment.characters.join("") !== text ||
      alignment.characters.length !== alignment.character_start_times_seconds.length ||
      alignment.characters.length !== alignment.character_end_times_seconds.length
    ) {
      throw new Error("ElevenLabs returned invalid audio alignment; no retry.");
    }
    const audio = Buffer.from(result.audio_base64, "base64");
    if (audio.length < 1000) throw new Error("ElevenLabs returned empty audio.");
    writeFileSync(resolve(outputDir, `phrase-${String(i + 1).padStart(2, "0")}.mp3`), audio);
    state.clips[i] = {
      text,
      complete: true,
      sha256: sha256(audio),
      alignment,
    };
    save();
    console.log(`Generated narration clip ${i + 1}/${texts.length}.`);
  }
  if (state.clips.length !== EXPECTED_CLIPS || !state.clips.every((clip) => clip.complete)) {
    throw new Error("Narration checkpoint is incomplete.");
  }
  return state;
}

export function encryptPreviewPackage({ state, audioDir, publicKey }) {
  const clips = state.clips.map((clip, i) => {
    if (!clip.complete) return clip;
    const file = `phrase-${String(i + 1).padStart(2, "0")}.mp3`;
    const audio = readFileSync(resolve(audioDir, file));
    if (sha256(audio) !== clip.sha256) throw new Error("Narration audio hash mismatch.");
    return { ...clip, file, audio: audio.toString("base64") };
  });
  const payload = gzipSync(Buffer.from(JSON.stringify({
    provider: "ElevenLabs",
    model: "eleven_multilingual_v2",
    voice: state.voice,
    voiceSettings: state.voiceSettings,
    scenes: state.requestScenes,
    clips,
    failure: state.failure,
  })));
  const contentKey = randomBytes(32);
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", contentKey, iv);
  const ciphertext = Buffer.concat([cipher.update(payload), cipher.final()]);
  const wrappedKey = publicEncrypt({
    key: publicKey,
    padding: constants.RSA_PKCS1_OAEP_PADDING,
    oaepHash: "sha256",
  }, contentKey);
  return {
    version: 1,
    wrappedKey: wrappedKey.toString("base64"),
    iv: iv.toString("base64"),
    authTag: cipher.getAuthTag().toString("base64"),
    ciphertext: ciphertext.toString("base64"),
  };
}

async function api(key, voiceId, body) {
  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}/with-timestamps?output_format=mp3_44100_128`,
    {
      method: "POST",
      headers: { "xi-api-key": key, "Content-Type": "application/json" },
      body: JSON.stringify(body),
      redirect: "error",
      signal: AbortSignal.timeout(90000),
    },
  );
  if (!response.ok) {
    let status = "unspecified";
    try {
      const error = await response.json();
      if (typeof error.detail?.status === "string" && /^[a-z_]{1,80}$/.test(error.detail.status)) {
        status = error.detail.status;
      }
    } catch {
      // Provider details are deliberately not logged.
    }
    throw new Error(`ElevenLabs HTTP ${response.status} (${status}); no automatic retry.`);
  }
  return response.json();
}

async function verifyVoice(key, voiceId) {
  const response = await fetch(`https://api.elevenlabs.io/v1/voices/${voiceId}`, {
    headers: { "xi-api-key": key },
    redirect: "error",
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) {
    throw new Error(`ElevenLabs voice access check failed (HTTP ${response.status}); no narration generated.`);
  }
  const voice = await response.json();
  if (voice.voice_id !== voiceId) throw new Error("ElevenLabs voice access check returned an unexpected voice.");
}

async function main() {
  const key = process.env.ELEVENLABS_API_KEY?.trim();
  if (!key) throw new Error("Missing marketing ElevenLabs secret.");
  const appDir = process.env.GAMEPLAY_APP_DIR;
  if (!appDir) throw new Error("Missing workflow checkout path.");
  const audioDir = resolve(appDir, "audio");
  const statePath = resolve(audioDir, "state.json");
  const request = JSON.parse(
    readFileSync(
      new URL(
        process.env.GAMEPLAY_REQUEST_FILE ?? "./gameplay-commentator-request.json",
        import.meta.url,
      ),
    ),
  );
  mkdirSync(audioDir, { recursive: true });
  const state = { clips: [] };
  const save = () => {
    writeFileSync(statePath, JSON.stringify(state, null, 2) + "\n");
  };

  let safeError;
  state.requestScenes = Array.isArray(request?.scenes) ? request.scenes : [];
  try {
    await verifyVoice(key, request?.voice?.id ?? "");
    await generateCommentary({
      request,
      state,
      key,
      api: (voiceId, body) => api(key, voiceId, body),
      save,
      outputDir: audioDir,
    });
  } catch (error) {
    safeError = error instanceof Error
      ? (key ? error.message.replaceAll(key, "[REDACTED]") : error.message)
      : "Generation failed.";
    state.failure = safeError;
    save();
  } finally {
    const publicKey = readFileSync(resolve(appDir, "scripts/gameplay-voice-preview-public.pem"));
    const encrypted = encryptPreviewPackage({ state, audioDir, publicKey });
    writeFileSync(resolve(appDir, "voice-preview.enc.json"), JSON.stringify(encrypted));
  }
  if (safeError) throw new Error(safeError);
}

if (process.argv[1] && resolve(process.argv[1]) === new URL(import.meta.url).pathname) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
