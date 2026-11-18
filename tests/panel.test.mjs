// Tests for the panel's pure logic: node --test tests/
import assert from "node:assert/strict";
import test from "node:test";

import {
  ERROR_TEXT,
  LEAVE_MODES,
  PHOTO_FORMATS,
  defaultFolder,
  errorMessage,
  fill,
  formatBytes,
  intervalLabel,
  looksLikeAlbumLink,
  mediaBrowserUrl,
  needsDraw,
  pickAlbum,
  progressPercent,
  relativeTime,
  settingsPayload,
  slugify,
  statusChip,
  toggleSelection,
  warningMessage,
} from "../frontend/logic.mjs";

test("fill and error messages", () => {
  assert.equal(fill("{a} and {b}", { a: 1 }), "1 and {b}");
  assert.equal(
    errorMessage("untrusted_host", { host: "evil.example", kind: "cloudkit" }).includes("evil.example"),
    true,
  );
  assert.equal(errorMessage("nope"), ERROR_TEXT.unknown);
  assert.equal(errorMessage(null), null);
  assert.equal(errorMessage("download_failed", { count: 2 }).startsWith("2 file(s)"), true);
  assert.equal(warningMessage("empty_listing").includes("nothing was removed"), true);
  assert.equal(warningMessage("other"), "other");
});

test("every backend error key has text", () => {
  for (const key of [
    "invalid_link",
    "album_not_found",
    "album_requires_login",
    "apple_error",
    "cannot_connect",
    "incomplete_listing",
    "untrusted_host",
    "low_disk_space",
    "download_failed",
    "storage_error",
    "already_configured",
    "invalid_folder",
    "invalid_host",
  ]) {
    assert.ok(ERROR_TEXT[key], key);
  }
});

test("choices match the integration's options", () => {
  assert.deepEqual(
    PHOTO_FORMATS.map(([v]) => v),
    ["convert", "original", "dashboard"],
  );
  assert.deepEqual(
    LEAVE_MODES.map(([v]) => v),
    ["quarantine", "keep", "delete"],
  );
});

test("formatBytes", () => {
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(1023), "1023 B");
  assert.equal(formatBytes(2048), "2 KB");
  assert.equal(formatBytes(5 * 1024 * 1024), "5 MB");
  assert.equal(formatBytes(1.25 * 1024 ** 3), "1.25 GB");
  assert.equal(formatBytes(undefined), "0 B");
});

test("relativeTime", () => {
  const now = Date.parse("2026-11-18T12:00:00Z");
  assert.equal(relativeTime(null, now), "never");
  assert.equal(relativeTime("garbage", now), "never");
  assert.equal(relativeTime("2026-11-18T11:59:50Z", now), "just now");
  assert.match(relativeTime("2026-11-18T11:00:00Z", now), /hour/);
  assert.match(relativeTime("2026-11-15T12:00:00Z", now), /day/);
});

test("progress and status", () => {
  assert.equal(progressPercent(null), null);
  assert.equal(progressPercent({ done: 0, total: 0 }), null);
  assert.equal(progressPercent({ done: 1, total: 3 }), 33);
  assert.equal(progressPercent({ done: 5, total: 3 }), 100);
  assert.equal(statusChip({ state: "setup_error" }).tone, "off");
  assert.equal(statusChip({ state: "loaded", syncing: true }).tone, "busy");
  assert.equal(statusChip({ state: "loaded", last_error: "x" }).tone, "error");
  assert.equal(statusChip({ state: "loaded" }).label, "Up to date");
});

test("intervalLabel", () => {
  assert.equal(intervalLabel(0), "Manual only");
  assert.equal(intervalLabel(15), "Every 15 minutes");
  assert.equal(intervalLabel(60), "Every hour");
  assert.equal(intervalLabel(180), "Every 3 hours");
  assert.equal(intervalLabel(1440), "Every day");
  assert.equal(intervalLabel(10080), "Every 7 days");
});

test("slugify and default folder", () => {
  assert.equal(slugify("Família Photos 2026!"), "familia_photos_2026");
  assert.equal(defaultFolder("Family Photos"), "shared_albums/family_photos");
});

test("looksLikeAlbumLink mirrors links.py", () => {
  for (const ok of [
    "https://photos.icloud.com/shared/album/AbC12_-xyZ",
    "photos.icloud.com/shared/gallery/AbC12xyZ/",
    "https://photos.icloud.com.cn/shared/album/AbC12xyZ",
    "https://www.icloud.com/sharedalbum/#B0z5qAGN1JIFd3y",
    "https://www.icloud.com/sharedalbum/en-us/#B0z5qAGN1JIFd3y",
    "icloud.com/sharedalbum/#B0z5qAGN1JIFd3y;CAEQARoQ",
  ]) {
    assert.ok(looksLikeAlbumLink(ok), ok);
  }
  for (const bad of [
    "",
    "nope",
    "https://photos.icloud.com/",
    "https://photos.icloud.com.evil.example/shared/album/AbC12xyZ",
    "https://www.icloud.com/sharedalbum/",
    "https://www.icloud.com/photos/#B0z5qAGN1JIFd3y",
  ]) {
    assert.ok(!looksLikeAlbumLink(bad), bad);
  }
});

test("settingsPayload", () => {
  assert.deepEqual(
    settingsPayload({ interval_minutes: "60", leave_mode: "keep", extra_trusted_hosts: "a.example, b.example\nc.example" }),
    { interval_minutes: 60, leave_mode: "keep", extra_trusted_hosts: ["a.example", "b.example", "c.example"] },
  );
  assert.deepEqual(settingsPayload({ extra_trusted_hosts: ["x.example"] }), { extra_trusted_hosts: ["x.example"] });
});

test("mediaBrowserUrl", () => {
  assert.equal(mediaBrowserUrl(null), "/media-browser/browser/app%2Cmedia-source%3A%2F%2Fmedia_source");
  assert.equal(
    mediaBrowserUrl("media-source://media_source/local/shared_albums/x"),
    "/media-browser/browser/app%2Cmedia-source%3A%2F%2Fmedia_source/directory%2Cmedia-source%3A%2F%2Fmedia_source%2Flocal%2Fshared_albums%2Fx",
  );
});

test("selection, redraw and album picking", () => {
  const a = toggleSelection(new Set(), "x");
  assert.ok(a.has("x"));
  assert.ok(!toggleSelection(a, "x").has("x"));
  assert.equal(needsDraw(new Map()), false);
  assert.equal(needsDraw(new Map([["hass", 1]])), false);
  assert.equal(needsDraw(new Map([["hass", 1], ["_data", 1]])), true);
  const albums = [{ entry_id: "a" }, { entry_id: "b" }];
  assert.equal(pickAlbum([], "a"), null);
  assert.equal(pickAlbum(albums, "b"), "b");
  assert.equal(pickAlbum(albums, "gone"), "a");
});
