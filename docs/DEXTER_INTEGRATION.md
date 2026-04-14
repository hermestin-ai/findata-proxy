# Dexter Integration Guide

Complete end-to-end setup for running [Dexter](https://github.com/virattt/dexter) against `findata-proxy` instead of the paid Financial Datasets API.

**Status: verified working as of v0.2.** A headless query like
`"What is AAPL current stock price?"` round-trips successfully:
Dexter (Bun) → LLM (Ollama) → tool call → proxy (FastAPI) → yfinance/SEC → answer.

## Prerequisites

- macOS or Linux
- Bun 1.x (runtime for Dexter)
- Python 3.11+ (runtime for proxy)
- An LLM provider, either:
  - **Ollama** (local, free) — recommended for the proxy-only validation
  - **OpenAI / Anthropic / Google / xAI / OpenRouter** — recommended for production-quality answers

Install missing pieces:

```bash
# Bun
brew install oven-sh/bun/bun
# Ollama (includes GUI app)
brew install --cask ollama-app
# Start Ollama server
ollama serve &
# Pull a tool-calling model — qwen3:30b has the best reasoning/size tradeoff
ollama pull qwen3:30b
# OR for a smaller test: qwen2.5:14b executes tools but does not reason well
```

## 1. Start findata-proxy

```bash
cd ~/projects/findata-proxy
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set SEC_USER_AGENT to "Your Name your@email.com"
uvicorn app.main:app --port 8765 --log-level warning &
curl http://localhost:8765/                 # {"status":"ok",...}
```

## 2. Clone and set up Dexter

```bash
cd ~/projects
git clone https://github.com/virattt/dexter.git
cd dexter
bun install    # ~90s, also downloads Playwright chromium
```

### Patch Dexter to honor `FINANCIAL_DATASETS_BASE_URL`

Two one-line patches — they've been upstream-ready since v0.2 of this proxy:

**`src/tools/finance/api.ts`** (line 4):
```diff
-const BASE_URL = 'https://api.financialdatasets.ai';
+const BASE_URL = process.env.FINANCIAL_DATASETS_BASE_URL || 'https://api.financialdatasets.ai';
```

**`src/tools/finance/filings.ts`** (line 30 in the `getFilingItemTypes()` function):
```diff
-  const response = await fetch('https://api.financialdatasets.ai/filings/items/types/');
+  const baseUrl = process.env.FINANCIAL_DATASETS_BASE_URL || 'https://api.financialdatasets.ai';
+  const response = await fetch(`${baseUrl}/filings/items/types/`);
```

One-liner to apply both:
```bash
sed -i.bak "s|'https://api.financialdatasets.ai'|process.env.FINANCIAL_DATASETS_BASE_URL || 'https://api.financialdatasets.ai'|" src/tools/finance/api.ts
# filings.ts needs the fetch() one; do it manually
```

## 3. Headless runner

Dexter ships as an interactive Ink TUI — great for humans, not for scripts/cron. Drop this file into `scripts/headless.ts`:

```typescript
#!/usr/bin/env bun
import { config } from 'dotenv';
import { Agent } from '../src/agent/index.js';
config({ quiet: true });

const query = process.argv.slice(2).join(' ').trim();
const model = process.env.DEXTER_MODEL || 'ollama:qwen3:30b';
const maxIterations = Number(process.env.DEXTER_MAX_ITER || '8');

const agent = await Agent.create({
  model,
  maxIterations,
  memoryEnabled: false,
  requestToolApproval: async () => 'allow-session' as const,
});

for await (const event of agent.run(query)) {
  switch (event.type) {
    case 'tool_start':
      console.error(`🔧 ${event.tool}(${JSON.stringify(event.args).slice(0, 200)})`);
      break;
    case 'tool_end':
      console.error(`   ↳ ${event.duration}ms`);
      break;
    case 'tool_error':
      console.error(`   ❌ ${event.error}`);
      break;
    case 'done':
      console.log(event.answer);
      break;
  }
}
```

A fuller version (with thinking events, limits, timing) lives in this repo at
[`examples/dexter-headless.ts`](../examples/dexter-headless.ts).

## 4. Run a query

```bash
cd ~/projects/dexter

FINANCIAL_DATASETS_BASE_URL=http://localhost:8765 \
OLLAMA_BASE_URL=http://localhost:11434 \
DEXTER_MODEL=ollama:qwen3:30b \
DEXTER_MAX_ITER=8 \
bun run scripts/headless.ts "Build a brief value-investing thesis on AAPL. \
Pull annual financials and key ratios, then summarize in 300 words: valuation, \
financial strength, Buy/Hold/Avoid recommendation."
```

## Observed behavior (v0.2)

| LLM | Tool execution | Reasoning quality |
|-----|----------------|-------------------|
| `ollama:qwen2.5:14b` | ✅ Executes tools correctly | ❌ Fails to synthesize — asks clarifying questions instead of answering |
| `ollama:qwen3:30b`   | ✅ Executes tools correctly | ✅ Produces usable theses |
| `openai:gpt-4o` (if key set) | ✅ | ✅ Best quality |
| `anthropic:claude-sonnet-4` (if key set) | ✅ | ✅ Best for reasoning-heavy analysis |

Tool call latency: 30-40s first call (model load + yfinance cold), 2-10s subsequent.

## Known compatibility notes

- The proxy returns `_source` field in `/financials/*` responses; Dexter ignores unknown fields so this is harmless.
- Some Financial Datasets fields may be `null` in proxy responses (e.g. `interest_expense` when the filer doesn't report it as a separate line). Dexter's LLM handles nulls gracefully.
- The screener endpoint (`POST /financials/search/screener/`) iterates yfinance over a hardcoded S&P 500 top-100 list. Queries that expect the full US market will undercount — use FMP for production-grade screening.

## Running as a persistent service

### macOS launchd

Create `~/Library/LaunchAgents/com.findata-proxy.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key>             <string>com.findata-proxy</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOUR_USER/projects/findata-proxy/.venv/bin/uvicorn</string>
    <string>app.main:app</string>
    <string>--port</string><string>8765</string>
  </array>
  <key>WorkingDirectory</key>  <string>/Users/YOUR_USER/projects/findata-proxy</string>
  <key>RunAtLoad</key>         <true/>
  <key>KeepAlive</key>         <true/>
  <key>StandardOutPath</key>   <string>/tmp/findata-proxy.log</string>
  <key>StandardErrorPath</key> <string>/tmp/findata-proxy.err</string>
</dict></plist>
```

Then: `launchctl load ~/Library/LaunchAgents/com.findata-proxy.plist`

### Docker

```bash
docker-compose up -d  # uses the Dockerfile in repo root
```
