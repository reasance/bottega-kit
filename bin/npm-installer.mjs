#!/usr/bin/env node
// bottega-kit npm installer: a thin wrapper over the repository's ./install.sh.
//
// `npx bottega-kit` clones https://github.com/matteoscurati/bottega-kit at the
// tag that matches this package's own version (bottega-kit--v<version>), runs
// ./install.sh from the clone, then ./doctor.sh, then deletes the clone.
// install.sh copies what it installs into BOTTEGA_DATA_HOME and records the
// repository and ref (never the temporary path) in installed-version.json, so
// nothing installed points at the deleted clone.
//
// Usage:
//   npx bottega-kit [--ref <tag-or-branch>] [--repo <git-url>] [--skip-doctor]
//
// Environment: BOTTEGA_DATA_HOME and BOTTEGA_BIN_HOME, as for ./install.sh.
// The wrapper never writes a configuration and never handles credentials.

import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import process from "node:process";

const DEFAULT_REPO = "https://github.com/matteoscurati/bottega-kit";
const TAG_PREFIX = "bottega-kit--v";
const USAGE =
  "usage: npx bottega-kit [--ref <tag-or-branch>] [--repo <git-url>] [--skip-doctor]";
const REQUIRED = [
  "install.sh",
  "doctor.sh",
  "bin/bottega",
  "bin/lib/bottega/version.py",
];

class WrapperError extends Error {
  constructor(message, code = 1) {
    super(message);
    this.code = code;
  }
}

function packageVersion() {
  const text = readFileSync(new URL("../package.json", import.meta.url), "utf8");
  return JSON.parse(text).version;
}

function parseArgs(argv) {
  const options = { ref: null, repo: null, skipDoctor: false, help: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const [name, inline] = arg.startsWith("--") && arg.includes("=")
      ? [arg.slice(0, arg.indexOf("=")), arg.slice(arg.indexOf("=") + 1)]
      : [arg, null];
    switch (name) {
      case "--ref":
      case "--repo": {
        const value = inline ?? argv[i + 1];
        if (inline === null) i += 1;
        if (!value || value.startsWith("--")) {
          throw new WrapperError(`${name} needs a value\n${USAGE}`, 64);
        }
        options[name.slice(2)] = value;
        break;
      }
      case "--skip-doctor":
        options.skipDoctor = true;
        break;
      case "-h":
      case "--help":
        options.help = true;
        break;
      default:
        // install.sh takes no arguments, so nothing is forwarded to it.
        throw new WrapperError(`unknown argument: ${arg}\n${USAGE}`, 64);
    }
  }
  return options;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: "inherit", ...options });
  if (result.error) {
    throw new WrapperError(`could not run ${command}: ${result.error.message}`);
  }
  return result;
}

function requireGit() {
  const probe = spawnSync("git", ["--version"], { stdio: "ignore" });
  if (probe.error || probe.status !== 0) {
    throw new WrapperError("git is required", 69);
  }
}

function clone(repo, ref, dir) {
  const result = run(
    "git",
    ["clone", "--quiet", "--depth", "1", "--branch", ref, repo, dir],
    { stdio: ["ignore", "ignore", "pipe"], encoding: "utf8" },
  );
  if (result.status !== 0) {
    const detail = (result.stderr || "").trim();
    throw new WrapperError(
      `could not clone ${repo} at ${ref}${detail ? `:\n${detail}` : ""}`,
    );
  }
}

function checkCheckout(dir, expectedVersion, ref) {
  for (const file of REQUIRED) {
    let ok = false;
    try {
      ok = statSync(join(dir, file)).isFile();
    } catch {
      ok = false;
    }
    if (!ok) {
      throw new WrapperError(`${ref} has no ${file}; it is not a bottega-kit release`);
    }
  }
  const text = readFileSync(join(dir, "bin/lib/bottega/version.py"), "utf8");
  const found = /^__version__ = "([^"]+)"$/m.exec(text)?.[1];
  if (expectedVersion && found !== expectedVersion) {
    throw new WrapperError(
      `${ref} holds bottega-kit ${found ?? "(no version)"}, not ${expectedVersion}`,
    );
  }
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    console.log(USAGE);
    return 0;
  }
  requireGit();
  const version = packageVersion();
  const repo = options.repo ?? DEFAULT_REPO;
  const ref = options.ref ?? `${TAG_PREFIX}${version}`;
  const parent = mkdtempSync(join(tmpdir(), "bottega-kit-"));
  const checkout = join(parent, "bottega-kit");
  try {
    console.log(`bottega-kit: installing ${ref} from ${repo}`);
    clone(repo, ref, checkout);
    // Only the default tag must match this package; --ref is the user's choice.
    checkCheckout(checkout, options.ref ? null : version, ref);
    const env = {
      ...process.env,
      BOTTEGA_INSTALL_SOURCE: repo,
      BOTTEGA_INSTALL_REF: ref,
    };
    const install = run("./install.sh", [], { cwd: checkout, env });
    if (install.status !== 0) {
      throw new WrapperError(
        `install.sh exited with ${install.status}`,
        install.status ?? 1,
      );
    }
    if (options.skipDoctor) {
      return 0;
    }
    const doctor = run("./doctor.sh", [], { cwd: checkout, env });
    if (doctor.status !== 0) {
      console.error(
        `bottega-kit: installed, but doctor reported problems (exit ${doctor.status}). ` +
          "A new install has no configuration yet: run bottega init, then bottega doctor.",
      );
      return doctor.status ?? 1;
    }
    return 0;
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
}

let code;
try {
  code = main();
} catch (error) {
  if (!(error instanceof WrapperError)) throw error;
  console.error(`bottega-kit: ${error.message}`);
  code = error.code;
}
process.exit(code);
