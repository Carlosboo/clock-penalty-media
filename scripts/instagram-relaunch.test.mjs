import test from "node:test";
import assert from "node:assert/strict";
import { publishCampaign } from "./instagram-relaunch.mjs";
import { createHash } from "node:crypto";

function setup() {
  const bytes = Buffer.alloc(12345);
  bytes.write("ftyp", 4);
  const sha256 = createHash("sha256").update(bytes).digest("hex");
  const request = {
    domain: "clockpenalty.com",
    mediaCommit: "a".repeat(40),
    items: ["REELS", "REELS", "STORIES", "STORIES"].map((kind, i) => ({
      kind,
      key: `video-${i}`,
      file: `video-${i}.mp4`,
      bytes: 12345,
      sha256,
      caption: "clockpenalty.com",
    })),
  };
  const state = {};
  const writes = [];
  const posts = [];
  let n = 0;
  const fetcher = async (url, options) => {
    if (String(url).startsWith("https://raw.githubusercontent.com/"))
      return {
        ok: true,
        headers: new Headers({
          "content-type": "application/octet-stream",
          "content-length": "12345",
        }),
        arrayBuffer: async () => bytes,
      };
    const u = new URL(url);
    const body = options.body ? JSON.parse(options.body) : {};
    if (options.method === "POST") posts.push([u.pathname, body]);
    let result;
    if (u.pathname.endsWith("/me"))
      result = { user_id: "17841459544818975", username: "clock.penalty" };
    else if (u.pathname.endsWith("/media")) result = { id: String(++n) };
    else if (u.pathname.endsWith("/media_publish")) {
      assert.ok(writes.at(-1).items[`video-${n - 1}`].attempted);
      result = { id: String(100 + n) };
    } else if (u.searchParams.get("fields") === "status_code")
      result = { status_code: "FINISHED" };
    else
      result = {
        id: u.pathname.split("/").at(-1),
        permalink: "https://www.instagram.com/reel/example/",
        media_type: "VIDEO",
      };
    return { ok: true, json: async () => result };
  };
  return {
    request,
    state,
    writes,
    posts,
    fetcher,
    save: () => writes.push(structuredClone(state)),
    token: "not-a-real-token",
  };
}

test("publishes exactly two reels and two stories with durable checkpoints; rerun does not duplicate", async () => {
  const s = setup();
  await publishCampaign(s);
  assert.equal(s.state.complete, true);
  assert.equal(s.posts.filter(([p]) => p.endsWith("/media_publish")).length, 4);
  assert.equal(s.posts[0][1].share_to_feed, true);
  assert.equal(s.posts[4][1].media_type, "STORIES");
  await publishCampaign(s);
  assert.equal(s.posts.filter(([p]) => p.endsWith("/media_publish")).length, 4);
});

test("replacement campaign publishes only two reels with explicit verified covers", async () => {
  const s = setup();
  const cover = Buffer.alloc(2000);
  cover[0] = 255;
  cover[1] = 216;
  s.request.items = s.request.items.slice(0, 2).map((item) => ({
    ...item,
    cover: {
      file: "cover.jpg",
      bytes: cover.length,
      sha256: createHash("sha256").update(cover).digest("hex"),
    },
  }));
  const original = s.fetcher;
  s.fetcher = async (url, opts) =>
    String(url).endsWith("/cover.jpg")
      ? { ok: true, arrayBuffer: async () => cover }
      : original(url, opts);
  await publishCampaign(s);
  assert.equal(s.posts.filter(([p]) => p.endsWith("/media_publish")).length, 2);
  assert.ok(
    s.posts
      .filter(([p]) => p.endsWith("/media"))
      .every(([, p]) => p.cover_url.endsWith("/cover.jpg")),
  );
  assert.equal(s.state.complete, true);
});

test("provider diagnostics redact credentials and changed public files are rejected", async () => {
  let s = setup();
  s.fetcher = async () => ({
    ok: false,
    status: 400,
    json: async () => ({
      error: { code: 200, message: `API access blocked ${s.token}` },
    }),
  });

  await assert.rejects(
    publishCampaign(s),
    (error) =>
      error.message.includes("API access blocked") &&
      !error.message.includes(s.token),
  );
  s = setup();
  s.request.items[0].sha256 = "b".repeat(64);
  await assert.rejects(publishCampaign(s), /Public video hash/);
  assert.equal(s.posts.length, 0);
});

test("uncertain publication never automatically posts again", async () => {
  const s = setup();
  s.state.items = { "video-0": { container: "1", attempted: "previous" } };
  await assert.rejects(publishCampaign(s), /Uncertain/);
  assert.equal(s.posts.length, 0);
});

test("approved gameplay campaign publishes exactly one reel with cover and never duplicates", async () => {
  const s = setup();
  s.request.items = s.request.items.slice(0, 1);
  const cover = Buffer.alloc(2000);
  cover[0] = 255;
  cover[1] = 216;
  s.request.items[0].cover = {
    file: "cover.jpg",
    bytes: cover.length,
    sha256: createHash("sha256").update(cover).digest("hex"),
  };
  const fetcher = s.fetcher;
  s.fetcher = (url, options) => String(url).endsWith("/cover.jpg")
    ? Promise.resolve({ ok: true, arrayBuffer: async () => cover })
    : fetcher(url, options);
  await publishCampaign(s);
  await publishCampaign(s);
  assert.equal(s.state.complete, true);
  assert.equal(s.posts.filter(([path]) => path.endsWith("/media_publish")).length, 1);
  assert.ok(s.posts[0][1].cover_url.endsWith("/cover.jpg"));
  assert.equal(s.posts[0][1].media_type, "REELS");
});

test("wrong identity, stale URL and changed media are rejected before publishing", async () => {
  let s = setup();
  s.state.mediaCommit = "b".repeat(40);
  await assert.rejects(publishCampaign(s), /Campaign media changed/);
  s = setup();
  s.request.items[0].caption = "old.pages.dev";
  await assert.rejects(publishCampaign(s), /Invalid media/);
  s = setup();
  s.fetcher = async () => ({
    ok: true,
    json: async () => ({ user_id: "1", username: "other" }),
  });
  await assert.rejects(publishCampaign(s), /Unexpected Instagram account/);
});
