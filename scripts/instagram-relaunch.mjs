import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const ACCOUNT = "17841459544818975";

export async function publishCampaign({
  token,
  request,
  state,
  save,
  fetcher = fetch,
  sleep = (ms) => new Promise((r) => setTimeout(r, ms)),
}) {
  if (
    !token ||
    request.domain !== "clockpenalty.com" ||
    !/^[a-f0-9]{40}$/.test(request.mediaCommit)
  ) {
    throw new Error("Invalid campaign configuration.");
  }
  if (
    !Array.isArray(request.items) ||
    !["REELS", "REELS,REELS", "REELS,REELS,STORIES,STORIES"].includes(
      request.items.map((x) => x.kind).join(","),
    )
  ) {
    throw new Error("Unexpected campaign media selection.");
  }
  if (state.mediaCommit && state.mediaCommit !== request.mediaCommit) {
    throw new Error(
      "Campaign media changed; refusing to reuse publication state.",
    );
  }
  async function api(path, params = {}, method = "GET") {
    const url = new URL(`https://graph.instagram.com/v25.0/${path}`);
    const options = {
      method,
      headers: { Authorization: `Bearer ${token}` },
      redirect: "error",
      signal: AbortSignal.timeout(90000),
    };
    if (method === "GET") url.search = new URLSearchParams(params).toString();
    else {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(params);
    }
    const response = await fetcher(url, options);
    const body = await response.json();
    if (!response.ok || body.error) {
      const detail =
        typeof body.error?.message === "string"
          ? body.error.message
              .replaceAll(token, "[REDACTED]")
              .replace(/https?:\/\/\S+/g, "[URL]")
              .slice(0, 600)
          : "No provider explanation.";
      throw new Error(
        `Instagram HTTP ${response.status}; code ${Number.isInteger(body.error?.code) ? body.error.code : "unknown"}; endpoint ${path}; ${detail}`,
      );
    }
    return body;
  }
  const id = (value) => {
    if (typeof value !== "string" || !/^\d+$/.test(value))
      throw new Error("Invalid Instagram media ID.");
    return value;
  };
  const account = await api("me", { fields: "user_id,username" });
  if (
    account.username !== "clock.penalty" ||
    String(account.user_id) !== ACCOUNT
  ) {
    throw new Error("Unexpected Instagram account.");
  }
  const seen = new Set();
  for (const item of request.items) {
    if (
      !/^[a-z0-9-]+$/.test(item.key) ||
      seen.has(item.key) ||
      !/^[a-z0-9-]+\.mp4$/.test(item.file) ||
      !Number.isInteger(item.bytes) ||
      item.bytes < 1000 ||
      item.bytes > 100_000_000 ||
      !/^[a-f0-9]{64}$/.test(item.sha256 ?? "") ||
      typeof item.caption !== "string" ||
      item.caption.includes("pages.dev")
    ) {
      throw new Error("Invalid media manifest entry.");
    }
    seen.add(item.key);
    const url = `https://raw.githubusercontent.com/Carlosboo/clock-penalty-media/${request.mediaCommit}/relaunch/${item.file}`;
    const response = await fetcher(url, {
      method: "GET",
      signal: AbortSignal.timeout(90000),
    });
    const contentType = response.headers.get("content-type")?.split(";")[0];
    if (
      !response.ok ||
      !["video/mp4", "application/octet-stream"].includes(contentType) ||
      Number(response.headers.get("content-length")) !== item.bytes
    ) {
      throw new Error(
        "Public video is missing or differs from approved export.",
      );
    }
    const bytes = Buffer.from(await response.arrayBuffer());
    if (
      bytes.length !== item.bytes ||
      bytes.toString("ascii", 4, 8) !== "ftyp" ||
      createHash("sha256").update(bytes).digest("hex") !== item.sha256
    ) {
      throw new Error(
        "Public video hash or MP4 signature differs from approved export.",
      );
    }
    item.url = url;
    if (item.cover) {
      if (
        item.kind !== "REELS" ||
        !/^[a-z0-9-]+\.jpg$/.test(item.cover.file) ||
        !/^[a-f0-9]{64}$/.test(item.cover.sha256) ||
        !Number.isInteger(item.cover.bytes) ||
        item.cover.bytes < 1000 ||
        item.cover.bytes > 8_000_000
      ) {
        throw new Error("Invalid cover manifest.");
      }
      item.coverUrl = `https://raw.githubusercontent.com/Carlosboo/clock-penalty-media/${request.mediaCommit}/relaunch/${item.cover.file}`;
      const response = await fetcher(item.coverUrl, {
        signal: AbortSignal.timeout(30000),
      });
      if (!response.ok) throw new Error("Public video cover unavailable.");
      const bytes = Buffer.from(await response.arrayBuffer());
      if (
        bytes.length !== item.cover.bytes ||
        bytes[0] !== 255 ||
        bytes[1] !== 216 ||
        createHash("sha256").update(bytes).digest("hex") !== item.cover.sha256
      ) {
        throw new Error("Public video cover differs from approved export.");
      }
    }
  }
  state.mediaCommit = request.mediaCommit;
  state.items ??= {};
  save();
  for (const item of request.items) {
    const entry = (state.items[item.key] ??= {});
    if (entry.mediaId && entry.published) continue;
    if (entry.attempted) {
      const status = await api(id(entry.container), { fields: "status_code" });
      if (status.status_code === "PUBLISHED") {
        entry.published = true;
        entry.needsMediaIdReconciliation = true;
        save();
        continue;
      }
      throw new Error(
        "Uncertain previous publication; no duplicate submitted.",
      );
    }
    if (!entry.container) {
      const params = { media_type: item.kind, video_url: item.url };
      if (item.kind === "REELS") {
        params.caption = item.caption;
        params.share_to_feed = true;
        if (item.coverUrl) params.cover_url = item.coverUrl;
      }
      const created = await api(`${ACCOUNT}/media`, params, "POST");
      entry.container = id(created.id);
      save();
    }
    let ready = false;
    for (let attempt = 0; attempt < 60; attempt++) {
      const status = await api(id(entry.container), { fields: "status_code" });
      if (status.status_code === "FINISHED") {
        ready = true;
        break;
      }
      if (status.status_code !== "IN_PROGRESS")
        throw new Error("Video processing failed or container expired.");
      await sleep(10000);
    }
    if (!ready)
      throw new Error(
        "Video processing timed out; retry later without recreating container.",
      );
    entry.attempted = new Date().toISOString();
    save();
    const published = await api(
      `${ACCOUNT}/media_publish`,
      { creation_id: entry.container },
      "POST",
    );
    entry.mediaId = id(published.id);
    entry.published = true;
    save();
    const fields =
      item.kind === "REELS" ? "id,permalink,media_type" : "id,media_type";
    const verified = await api(entry.mediaId, { fields });
    if (id(verified.id) !== entry.mediaId)
      throw new Error("Published media verification failed.");
    if (item.kind === "REELS") {
      if (!verified.permalink?.startsWith("https://www.instagram.com/"))
        throw new Error("Unexpected published permalink.");
      entry.permalink = verified.permalink;
    }
    entry.verified = true;
    save();
    console.log(`${item.key}: published and verified (${entry.mediaId}).`);
  }
  state.complete = request.items.every(
    (item) => state.items[item.key].verified,
  );
  save();
}

async function main() {
  const folder = process.env.PUBLISH_STATE_DIR;
  if (!folder) throw new Error("Missing publication state directory.");
  const filename = process.env.PUBLISH_STATE_FILE ?? "relaunch.json";
  if (!/^(relaunch|reels-covers-v[23]|gameplay-v1|reto-00-v1)\.json$/.test(filename))
    throw new Error("Invalid state filename.");
  const path = resolve(folder, filename);
  const state = existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : {};
  const save = () => {
    const content = JSON.stringify(state, null, 2) + "\n";
    if (existsSync(path) && readFileSync(path, "utf8") === content) return;
    writeFileSync(path, content);
    for (const args of [
      ["add", filename],
      [
        "commit",
        "-m",
        "chore(marketing): checkpoint Instagram relaunch [skip ci]",
        "-m",
        "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
      ],
      ["push", "origin", "HEAD:instagram-relaunch-state"],
    ])
      execFileSync("git", args, { cwd: folder, stdio: "pipe" });
  };
  try {
    await publishCampaign({
      token: process.env.INSTAGRAM_ACCESS_TOKEN?.trim(),
      request: JSON.parse(
        readFileSync(
          new URL(
            process.env.PUBLISH_REQUEST_FILE ??
              "./instagram-relaunch-operation.json",
            import.meta.url,
          ),
        ),
      ),
      state,
      save,
    });
  } catch (error) {
    const message =
      error instanceof Error &&
      /^(Invalid |Unexpected |Campaign |Instagram HTTP |Public video |Uncertain |Video processing |Published media )/.test(
        error.message,
      )
        ? error.message
        : "Publication stopped due to network or checkpoint error. Inspect persisted state before retrying.";
    state.error = message;
    save();
    throw new Error(message);
  }
}

if (
  process.argv[1] &&
  fileURLToPath(import.meta.url) === resolve(process.argv[1])
) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
