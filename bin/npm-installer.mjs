#!/usr/bin/env node
// bottega-kit npm installer — placeholder until the first release.
//
// Once released, `npx bottega-kit` will clone the tagged release and run its
// ./install.sh (milestone M3). Until then it only says so.

import process from "node:process";

console.error(
  "bottega-kit: not yet released. Clone the repository and run ./install.sh.",
);
process.exit(1);
