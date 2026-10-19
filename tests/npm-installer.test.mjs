// Tests for the `npx bottega-kit` wrapper (bin/npm-installer.mjs).
// Run: node --test tests/npm-installer.test.mjs
//
// Hermetic: the wrapper clones a LOCAL fixture repository through file://,
// built from this checkout's shipped files and tagged inside the fixture
// (never in this repository). HOME, XDG, TMPDIR and the install homes are
// temporary, and PATH holds the fake harnesses, node, git and python3 only.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  readlinkSync,
  realpathSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import test from "node:test";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const INSTALLER = join(ROOT, "bin", "npm-installer.mjs");
const VERSION = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8")).version;
const TAG = `bottega-kit--v${VERSION}`;
const SHIPPED = [
  "install.sh",
  "uninstall.sh",
  "doctor.sh",
  "bin/bottega",
  "bin/lib",
  "templates",
  "prompts",
  "LICENSE",
  "NOTICE",
  "package.json",
];
const CONFIG = {
  schema_version: 1,
  profiles: {
    "fable-judge": { harness: "claude", model: "claude-fable-5-1", effort: "max" },
    "opus-builder": { harness: "claude", model: "claude-opus-5-5", effort: "high" },
  },
  roles: { planner: "fable-judge", implementer: "opus-builder", reviewer: "opus-builder" },
  rounds: 3,
};

function which(command) {
  const r = spawnSync("bash", ["-c", `command -v ${command}`], { encoding: "utf8" });
  if (r.status !== 0) throw new Error(`${command} is needed by this test`);
  return realpathSync(r.stdout.trim());
}

// One temporary world per test: homes, TMPDIR, a bin dir, and the env.
function world(t) {
  const root = realpathSync(mkdtempSync(join(tmpdir(), "bottega-npm-test-")));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const d of ["home", "config", "data", "tmp", "bin", "install", "links"]) {
    mkdirSync(join(root, d));
  }
  for (const tool of ["git", "python3"]) {
    symlinkSync(which(tool), join(root, "bin", tool));
  }
  symlinkSync(process.execPath, join(root, "bin", "node"));
  const env = {
    HOME: join(root, "home"),
    XDG_CONFIG_HOME: join(root, "config"),
    XDG_DATA_HOME: join(root, "data"),
    TMPDIR: join(root, "tmp"),
    BOTTEGA_DATA_HOME: join(root, "install"),
    BOTTEGA_BIN_HOME: join(root, "links"),
    PATH: `${join(ROOT, "tests", "fakes")}:${join(root, "bin")}:/usr/bin:/bin`,
    GIT_CONFIG_NOSYSTEM: "1",
    PYTHONDONTWRITEBYTECODE: "1",
  };
  return { root, env };
}

function git(cwd, env, ...args) {
  const r = spawnSync(
    "git",
    ["-c", "user.name=bottega test", "-c", "user.email=test@example.invalid", ...args],
    { cwd, env, encoding: "utf8" },
  );
  if (r.status !== 0) throw new Error(`git ${args.join(" ")} failed: ${r.stderr}`);
  return r.stdout.trim();
}

function setVersion(dir, version) {
  writeFileSync(
    join(dir, "bin/lib/bottega/version.py"),
    `"""The one version string \`bottega --version\` prints."""\n\n__version__ = "${version}"\n`,
  );
}

// A release-shaped repository: this checkout's shipped files, one commit,
// optionally the release tag, then a later commit on main that says 9.9.9.
function fixture(w, { tag = TAG, taggedVersion = VERSION, later = true } = {}) {
  const dir = join(w.root, "origin");
  for (const item of SHIPPED) {
    cpSync(join(ROOT, item), join(dir, item), {
      recursive: true,
      filter: (src) => basename(src) !== "__pycache__",
    });
  }
  setVersion(dir, taggedVersion);
  git(w.root, w.env, "init", "-q", "-b", "main", dir);
  git(dir, w.env, "add", "-A");
  git(dir, w.env, "commit", "-q", "-m", "release");
  const tagged = git(dir, w.env, "rev-parse", "HEAD");
  if (tag) git(dir, w.env, "tag", "-a", tag, "-m", `bottega-kit ${taggedVersion}`);
  if (later) {
    setVersion(dir, "9.9.9");
    git(dir, w.env, "commit", "-q", "-am", "after the release");
  }
  return { url: pathToFileURL(dir).href, tagged };
}

function writeConfig(w) {
  mkdirSync(join(w.env.XDG_CONFIG_HOME, "bottega-kit"), { recursive: true });
  writeFileSync(
    join(w.env.XDG_CONFIG_HOME, "bottega-kit", "config.json"),
    JSON.stringify(CONFIG, null, 2),
  );
}

function wrapper(w, args, extraEnv = {}) {
  return spawnSync(process.execPath, [INSTALLER, ...args], {
    cwd: w.root,
    env: { ...w.env, ...extraEnv },
    encoding: "utf8",
    timeout: 120000,
  });
}

function marker(w) {
  return JSON.parse(readFileSync(join(w.env.BOTTEGA_DATA_HOME, "installed-version.json"), "utf8"));
}

// Every file and link under `dir`, with its content or link target.
function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stat = lstatSync(path);
    if (stat.isSymbolicLink()) out.push([path, readlinkSync(path)]);
    else if (stat.isDirectory()) walk(path, out);
    else out.push([path, readFileSync(path, "latin1")]);
  }
  return out;
}

function assertNothingPointsAt(w, prefix) {
  for (const home of [w.env.BOTTEGA_DATA_HOME, w.env.BOTTEGA_BIN_HOME]) {
    for (const [path, content] of walk(home)) {
      assert.ok(!content.includes(prefix), `${path} mentions the temporary clone`);
    }
  }
}

function assertTmpEmpty(w) {
  assert.deepEqual(readdirSync(w.env.TMPDIR), [], "the temporary clone was left behind");
}

test("installs the tag matching its own version, runs doctor, leaves no trace", (t) => {
  const w = world(t);
  const origin = fixture(w);
  writeConfig(w);
  const r = wrapper(w, ["--repo", origin.url]);
  assert.equal(r.status, 0, `stdout:\n${r.stdout}\nstderr:\n${r.stderr}`);
  assert.match(r.stdout, new RegExp(`installing ${TAG} from ${origin.url}`));
  assert.match(r.stdout, new RegExp(`installed bottega-kit ${VERSION.replaceAll(".", "\\.")}\\n`));
  assert.match(r.stdout, /0 failure\(s\)/); // doctor ran
  const m = marker(w);
  assert.equal(m.version, VERSION);
  assert.equal(m.ref, TAG);
  assert.equal(m.source, origin.url);
  assert.equal(m.commit, origin.tagged);
  assert.equal(m.commit_dirty, false);

  // The command runs after the clone is gone, from the install directory.
  const link = join(w.env.BOTTEGA_BIN_HOME, "bottega");
  assert.ok(realpathSync(link).startsWith(w.env.BOTTEGA_DATA_HOME));
  const v = spawnSync(link, ["--version"], { env: w.env, encoding: "utf8" });
  assert.equal(v.stdout.trim(), `bottega-kit ${VERSION}`);
  assertTmpEmpty(w);
  assertNothingPointsAt(w, w.env.TMPDIR);
});

test("--ref overrides the tag and --skip-doctor skips doctor", (t) => {
  const w = world(t);
  const origin = fixture(w);
  const r = wrapper(w, ["--repo", origin.url, "--ref", "main", "--skip-doctor"]);
  assert.equal(r.status, 0, r.stderr);
  assert.doesNotMatch(r.stdout, /failure\(s\)/);
  const m = marker(w);
  assert.equal(m.version, "9.9.9");
  assert.equal(m.ref, "main");
  assertTmpEmpty(w);
});

test("a missing release tag fails, names the ref, installs nothing", (t) => {
  const w = world(t);
  const origin = fixture(w, { tag: null });
  const r = wrapper(w, ["--repo", origin.url, "--skip-doctor"]);
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, new RegExp(`could not clone .* at ${TAG}`));
  assert.ok(!existsSync(join(w.env.BOTTEGA_DATA_HOME, "installed-version.json")));
  assertTmpEmpty(w);
});

test("a release tag holding another version is refused", (t) => {
  const w = world(t);
  const origin = fixture(w, { taggedVersion: "0.0.9", later: false });
  const r = wrapper(w, ["--repo", origin.url, "--skip-doctor"]);
  assert.equal(r.status, 1);
  assert.match(r.stderr, new RegExp(`${TAG} holds bottega-kit 0\\.0\\.9, not ${VERSION.replaceAll(".", "\\.")}`));
  assert.ok(!existsSync(join(w.env.BOTTEGA_DATA_HOME, "installed-version.json")));
  assertTmpEmpty(w);
});

test("doctor's failure is the exit code, with a hint; the install stays", (t) => {
  const w = world(t);
  const origin = fixture(w);
  const r = wrapper(w, ["--repo", origin.url]); // no configuration yet
  assert.equal(r.status, 2, r.stderr);
  assert.match(r.stderr, /installed, but doctor reported problems \(exit 2\)/);
  assert.match(r.stderr, /run bottega init, then bottega doctor/);
  assert.equal(marker(w).version, VERSION);
  assertTmpEmpty(w);
});

test("unknown arguments and a missing value are bad invocations", (t) => {
  const w = world(t);
  for (const args of [["--claude-only"], ["--ref"], ["--repo", "--skip-doctor"]]) {
    const r = wrapper(w, args);
    assert.equal(r.status, 64, args.join(" "));
    assert.match(r.stderr, /usage: npx bottega-kit/);
  }
  assertTmpEmpty(w);
});

test("git is required", (t) => {
  const w = world(t);
  const bare = join(w.root, "nogit");
  mkdirSync(bare);
  const r = wrapper(w, [], { PATH: bare });
  assert.equal(r.status, 69);
  assert.match(r.stderr, /git is required/);
});
