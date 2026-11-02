import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";

let commit = process.env.COMMIT_REF ?? "";
if (!/^[a-f0-9]{40}$/.test(commit)) {
  commit = execFileSync("git", ["rev-parse", "HEAD"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
}
if (!/^[a-f0-9]{40}$/.test(commit)) {
  throw new Error("A verified Git commit is required for deployment metadata.");
}

writeFileSync(
  "dist/client/version.json",
  `${JSON.stringify({ project: "governai", source_commit: commit, built_at: new Date().toISOString() }, null, 2)}\n`,
);
