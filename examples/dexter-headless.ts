#!/usr/bin/env bun
/**
 * Headless Dexter runner — runs a single query and prints a transcript.
 * Bypasses the Ink TUI and consumes Agent events directly.
 *
 * Usage:
 *   FINANCIAL_DATASETS_BASE_URL=http://localhost:8765 \
 *   DEXTER_MODEL=ollama:qwen3:30b \
 *   bun run examples/dexter-headless.ts "analyze AAPL as a value investment"
 *
 * This lives in the findata-proxy repo as reference; drop it into
 * dexter/scripts/headless.ts to use.
 */
import { config } from 'dotenv';
import { Agent } from '../src/agent/index.js';

config({ quiet: true });

const query = process.argv.slice(2).join(' ').trim();
if (!query) {
  console.error('Usage: bun run headless.ts "your question"');
  process.exit(2);
}

const model = process.env.DEXTER_MODEL || 'ollama:qwen3:30b';
const maxIterations = Number(process.env.DEXTER_MAX_ITER || '8');

console.error(`[headless] model=${model} maxIter=${maxIterations}`);
console.error(`[headless] proxy=${process.env.FINANCIAL_DATASETS_BASE_URL || '(default)'}`);
console.error(`[headless] query=${query}\n---`);

const agent = await Agent.create({
  model,
  maxIterations,
  memoryEnabled: false,
  requestToolApproval: async () => 'allow-session' as const,
});

const started = Date.now();
let toolCount = 0;

for await (const event of agent.run(query)) {
  switch (event.type) {
    case 'thinking':
      if (event.message) {
        const msg = event.message.replace(/\s+/g, ' ').slice(0, 200);
        process.stderr.write(`💭 ${msg}\n`);
      }
      break;
    case 'tool_start':
      toolCount++;
      console.error(`🔧 [${toolCount}] ${event.tool}(${JSON.stringify(event.args).slice(0, 240)})`);
      break;
    case 'tool_end': {
      const r = typeof event.result === 'string' ? event.result : JSON.stringify(event.result);
      const dur = event.duration ? `${event.duration}ms` : '?';
      console.error(`   ↳ ok ${dur} (${r.length}b)`);
      break;
    }
    case 'tool_error':
      console.error(`   ❌ ERROR: ${event.error}`);
      break;
    case 'tool_denied':
      console.error(`   🚫 DENIED: ${event.tool}`);
      break;
    case 'done':
      console.log('\n=== ANSWER ===\n');
      console.log(event.answer || '(no answer)');
      console.log('\n=== END ===');
      break;
  }
}

const elapsed = ((Date.now() - started) / 1000).toFixed(1);
console.error(`\n[headless] done in ${elapsed}s, ${toolCount} tool calls`);
