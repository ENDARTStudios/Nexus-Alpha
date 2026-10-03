import test from "node:test";
import assert from "node:assert/strict";

import { ALLOWED_GET, ALLOWED_POST, isAllowed, normalizePath } from "./policy.mjs";

test("GET: rotas de leitura permitidas", () => {
  assert.equal(isAllowed("GET", ["health"]), true);
  assert.equal(isAllowed("GET", ["metrics"]), true);
  assert.equal(isAllowed("GET", ["brain", "stats"]), true);
  assert.equal(isAllowed("GET", ["brain", "episodes"]), true);
  assert.equal(isAllowed("GET", ["graph", "topology"]), true);
});

test("POST: apenas /chat é permitido", () => {
  assert.equal(isAllowed("POST", ["chat"]), true);
});

test("POST: rotas administrativas bloqueadas (relay)", () => {
  assert.equal(isAllowed("POST", ["ingest"]), false);
  assert.equal(isAllowed("POST", ["brain", "consolidate"]), false);
  assert.equal(isAllowed("POST", ["brain", "activate"]), false);
  assert.equal(isAllowed("POST", ["brain", "episode"]), false);
  assert.equal(isAllowed("POST", ["extract"]), false);
  assert.equal(isAllowed("POST", ["simulate"]), false);
});

test("GET: rotas não listadas bloqueadas", () => {
  assert.equal(isAllowed("GET", ["ingest"]), false);
  assert.equal(isAllowed("GET", ["brain", "unknown"]), false);
  assert.equal(isAllowed("GET", []), false);
});

test("métodos não suportados bloqueados", () => {
  assert.equal(isAllowed("DELETE", ["brain", "stats"]), false);
  assert.equal(isAllowed("PUT", ["chat"]), false);
  assert.equal(isAllowed("PATCH", ["ingest"]), false);
});

test("normalização de caminho e case-insensibilidade", () => {
  assert.equal(normalizePath(["Brain", "Stats"]), "brain/stats");
  assert.equal(normalizePath(["/ingest/"]), "ingest");
  assert.equal(isAllowed("post", ["CHAT"]), true);
  assert.equal(isAllowed("POST", ["brain", "CONSOLIDATE"]), false);
});

test("allowlists são explícitas e pequenas", () => {
  assert.equal(ALLOWED_GET.size, 5);
  assert.equal(ALLOWED_POST.size, 1);
  assert.equal(ALLOWED_POST.has("chat"), true);
  assert.equal(ALLOWED_POST.has("ingest"), false);
});
