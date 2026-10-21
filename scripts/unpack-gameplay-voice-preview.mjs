import { createDecipheriv, createHash, privateDecrypt, constants } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { resolve } from "node:path";

const [packagePath, privateKeyPath, destination] = process.argv.slice(2);
const inspectOnly = destination === "--inspect";
if (
  !packagePath ||
  !privateKeyPath ||
  !destination ||
  (!inspectOnly && process.argv.length !== 5)
) {
  throw new Error("Usage: node unpack-gameplay-voice-preview.mjs <encrypted-package> <private-key> <output-directory|--inspect>");
}

const validBase64 = (value) =>
  typeof value === "string" && value.length > 0 && /^[A-Za-z0-9+/]*={0,2}$/.test(value);
const sha256 = (value) => createHash("sha256").update(value).digest("hex");

function unpack() {
  const envelope = JSON.parse(readFileSync(resolve(packagePath), "utf8"));
  if (
    envelope.version !== 1 ||
    !validBase64(envelope.wrappedKey) ||
    !validBase64(envelope.iv) ||
    !validBase64(envelope.authTag) ||
    !validBase64(envelope.ciphertext)
  ) throw new Error("Invalid encrypted narration package.");

  const key = privateDecrypt({
    key: readFileSync(resolve(privateKeyPath)),
    padding: constants.RSA_PKCS1_OAEP_PADDING,
    oaepHash: "sha256",
  }, Buffer.from(envelope.wrappedKey, "base64"));
  if (key.length !== 32) throw new Error("Invalid encrypted narration key.");

  const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(envelope.iv, "base64"));
  decipher.setAuthTag(Buffer.from(envelope.authTag, "base64"));
  const compressed = Buffer.concat([
    decipher.update(Buffer.from(envelope.ciphertext, "base64")),
    decipher.final(),
  ]);
  const payload = JSON.parse(gunzipSync(compressed, { maxOutputLength: 25 * 1024 * 1024 }).toString("utf8"));
  if (
    payload.provider !== "ElevenLabs" ||
    payload.model !== "eleven_multilingual_v2" ||
    !Array.isArray(payload.clips) ||
    payload.clips.length > 12 ||
    !Array.isArray(payload.scenes)
  ) throw new Error("Invalid narration package contents.");
  if (!payload.clips.every((clip, index) => {
    if (typeof clip.text !== "string") return false;
    if (!clip.complete) return typeof clip.attempted === "string";
    const expectedFile = `phrase-${String(index + 1).padStart(2, "0")}.mp3`;
    return clip.file === expectedFile &&
        typeof clip.sha256 === "string" &&
        /^[a-f0-9]{64}$/.test(clip.sha256) &&
        validBase64(clip.audio) &&
        Array.isArray(clip.alignment?.characters) &&
        clip.alignment.characters.join("") === clip.text &&
        clip.alignment.character_start_times_seconds?.length === clip.text.length &&
        clip.alignment.character_end_times_seconds?.length === clip.text.length;
  })) throw new Error("Narration is incomplete or has invalid alignment.");
  if (payload.clips.some((clip) => clip.complete && sha256(Buffer.from(clip.audio, "base64")) !== clip.sha256)) {
    throw new Error("Narration audio hash mismatch.");
  }
  return payload;
}

const payload = unpack();
if (inspectOnly) {
  console.log(JSON.stringify({
    completedClips: payload.clips.filter((clip) => clip.complete).length,
    attemptedClips: payload.clips.filter((clip) => !clip.complete && clip.attempted).length,
    failure: payload.failure ?? null,
  }, null, 2));
} else {
  if (payload.clips.length !== 12 || !payload.clips.every((clip) => clip.complete)) {
    throw new Error("Narration is incomplete; inspect the encrypted checkpoint before retrying.");
  }
  const outputPath = resolve(destination);
  mkdirSync(outputPath, { mode: 0o700 });
  const clips = payload.clips.map(({ audio, ...clip }, index) => {
    writeFileSync(resolve(outputPath, `phrase-${String(index + 1).padStart(2, "0")}.mp3`), Buffer.from(audio, "base64"), { mode: 0o600 });
    return clip;
  });
  writeFileSync(resolve(outputPath, "narration.json"), JSON.stringify({
    provider: payload.provider,
    model: payload.model,
    voice: payload.voice,
    voiceSettings: payload.voiceSettings,
    clips,
  }, null, 2) + "\n", { mode: 0o600 });
  console.log(`Recovered and verified ${clips.length} private narration clips.`);
}
