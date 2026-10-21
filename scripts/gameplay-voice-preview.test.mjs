import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  createDecipheriv,
  createHash,
  generateKeyPairSync,
  privateDecrypt,
  constants,
} from "node:crypto";
import { gunzipSync } from "node:zlib";
import test from "node:test";

import { encryptPreviewPackage, generateCommentary, verifyVoice } from "./gameplay-voice-preview.mjs";

const request = {
  voice: { id: "kw0sLdKrFNCRhdRYGrhU", name: "Pedro", locale: "es-ES" },
  voiceSettings: {
    stability: 0.31,
    similarity_boost: 0.78,
    style: 0.72,
    use_speaker_boost: true,
    speed: 1.08,
  },
  scenes: [
    ["¡Empate a uno!", "Última jugada."],
    ["Aquí no chutas:", "paras el reloj."],
    ["Cada centésima cuenta.", "Quince con noventa y nueve."],
    ["¡Dieciséis exactos!", "¡Doble cero!"],
    ["Se adelanta el Rayo.", "Del empate a la ventaja."],
    ["Una parada cambia todo.", "Invita a tu amigo a jugar ahora en clockpenalty.com."],
  ],
};

function alignment(text) {
  return {
    characters: [...text],
    character_start_times_seconds: [...text].map((_, index) => index / 10),
    character_end_times_seconds: [...text].map((_, index) => (index + 1) / 10),
  };
}

test("commentary request shape has twelve clips and preserves the requested CTA", () => {
  const allText = request.scenes.flat().join(" ");
  assert.equal(request.scenes.flat().length, 12);
  assert.ok(allText.includes("Invita a tu amigo a jugar ahora en clockpenalty.com."));
});

test("production script explains the rule without claiming a last play or a .99 stop", () => {
  const production = JSON.parse(readFileSync(new URL("./gameplay-commentator-request.json", import.meta.url)));
  const script = production.scenes.flat().join(" ");
  assert.match(script, /doble cero, ¡es gol!/);
  assert.ok(script.includes("Invita a tu amigo a jugar ahora en clockpenalty.com."));
  assert.doesNotMatch(script, /última jugada|noventa y nueve|\.99/);
});

test("catalog permission restriction does not imply text-to-speech is unavailable", async () => {
  await verifyVoice("test", request.voice.id, async () => ({
    ok: false,
    status: 401,
    json: async () => ({ detail: { status: "missing_permissions" } }),
  }));
});

test("an invalid API key stops before any speech generation", async () => {
  await assert.rejects(
    verifyVoice("test", request.voice.id, async () => ({
      ok: false,
      status: 401,
      json: async () => ({ detail: { status: "invalid_api_key" } }),
    })),
    /401, invalid_api_key/,
  );
});

test("incomplete attempted requests are never automatically repeated", async () => {
  let apiCalls = 0;
  const state = {
    requestHash: undefined,
    clips: [{ text: request.scenes[0][0], attempted: "previous run" }],
  };
  await assert.rejects(
    generateCommentary({
      request,
      state,
      key: "test",
      api: async () => {
        apiCalls++;
      },
      save() {},
      outputDir: tmpdir(),
    }),
    /uncertain; no automatic retry/,
  );
  assert.equal(apiCalls, 0);
});

test("preview package encrypts all narration and refuses changed audio", () => {
  const folder = mkdtempSync(join(tmpdir(), "gameplay-voice-test-"));
  try {
    const { publicKey, privateKey } = generateKeyPairSync("rsa", {
      modulusLength: 2048,
      publicKeyEncoding: { type: "spki", format: "pem" },
      privateKeyEncoding: { type: "pkcs8", format: "pem" },
    });
    const state = {
      voice: request.voice,
      voiceSettings: request.voiceSettings,
      requestScenes: request.scenes,
      clips: request.scenes.flat().map((text, index) => {
        const audio = Buffer.from(`voice clip ${index}`);
        writeFileSync(join(folder, `phrase-${String(index + 1).padStart(2, "0")}.mp3`), audio);
        return {
          text,
          complete: true,
          sha256: createHash("sha256").update(audio).digest("hex"),
          alignment: alignment(text),
        };
      }),
    };
    const encrypted = encryptPreviewPackage({ state, audioDir: folder, publicKey });
    const packagePath = join(folder, "voice-preview.enc.json");
    const privateKeyPath = join(folder, "private.pem");
    const narrationPath = join(folder, "unpacked");
    writeFileSync(packagePath, JSON.stringify(encrypted));
    writeFileSync(privateKeyPath, privateKey, { mode: 0o600 });
    execFileSync(process.execPath, [
      fileURLToPath(new URL("./unpack-gameplay-voice-preview.mjs", import.meta.url)),
      packagePath,
      privateKeyPath,
      narrationPath,
    ]);
    assert.equal(
      JSON.parse(readFileSync(join(narrationPath, "narration.json"), "utf8")).clips.length,
      12,
    );

    const contentKey = privateDecrypt({
      key: privateKey,
      padding: constants.RSA_PKCS1_OAEP_PADDING,
      oaepHash: "sha256",
    }, Buffer.from(encrypted.wrappedKey, "base64"));
    const decipher = createDecipheriv(
      "aes-256-gcm",
      contentKey,
      Buffer.from(encrypted.iv, "base64"),
    );
    decipher.setAuthTag(Buffer.from(encrypted.authTag, "base64"));
    const compressed = Buffer.concat([
      decipher.update(Buffer.from(encrypted.ciphertext, "base64")),
      decipher.final(),
    ]);
    const payload = JSON.parse(gunzipSync(compressed).toString("utf8"));
    assert.equal(payload.clips.length, 12);
    assert.equal(payload.clips[0].audio, Buffer.from("voice clip 0").toString("base64"));

    writeFileSync(join(folder, "phrase-01.mp3"), "modified audio");
    assert.throws(
      () => encryptPreviewPackage({ state, audioDir: folder, publicKey }),
      /audio hash mismatch/,
    );
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("voice generation stores aligned audio before marking a clip complete", async () => {
  const folder = mkdtempSync(join(tmpdir(), "gameplay-voice-generate-"));
  try {
    mkdirSync(folder, { recursive: true });
    const state = { clips: [] };
    let saves = 0;
    let calls = 0;
    await generateCommentary({
      request,
      state,
      key: "test",
      api: async (_, body) => {
        calls++;
        return {
          audio_base64: Buffer.alloc(1200, calls).toString("base64"),
          alignment: alignment(body.text),
        };
      },
      save() {
        saves++;
      },
      outputDir: folder,
    });
    assert.equal(calls, 12);
    assert.equal(saves, 25);
    assert.ok(state.clips.every((clip) => clip.complete && clip.sha256));
    assert.ok(readFileSync(resolve(folder, "phrase-12.mp3")).length >= 1000);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});
