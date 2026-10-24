# DHAAGAPROOF AI

**Every order has a deadline. Every worker deserves proof of fair pay.**

An original prototype *implementation* for Tech4Bharat / GAVS 2026, mapped to official **Challenge 8.1: Women's self-help group (SHG) order fulfilment and pay** (Agentic AI track).

The name and code are written specifically for this prototype. It is not claimed to be the world's first SHG app: multiple SHG accounting and voice apps already exist. What we are testing is the distinct **quote → capacity-aware work allocation → quality-accepted piece → auditable member payout** workflow, with transparent human approval at all consequential steps.

## One-click startup on Windows

1. Install **Python 3.11 or later** from python.org, if needed. Tick **Add python.exe to PATH** during installation.
2. Extract the ZIP folder anywhere, such as Desktop.
3. Double-click `RUN_PROJECT_WINDOWS.bat` (or open terminal here and run `python app.py`).
4. Open **http://127.0.0.1:8765** in Chrome, Edge or Firefox.
5. Stop the terminal with `Ctrl+C`. Data stays in `dhaagaproof.sqlite3` until you delete it.

**No `npm install`, API key or pip dependencies are required for the core system.** The backend and UI run on your computer. Browsers still need to be able to access `127.0.0.1` locally. The server binds to localhost by default; do not expose it publicly.

## Live workflows to demonstrate to judges

1. **Overview:** Inspect fictional order values, pending work, exceptions and live production progress.
2. **Orders & Quotes:** Choose the second **draft** order. Inspect unit economics, then press `Generate fair-work plan`. See proposed assignments, per-member explanations, labour shares, and the fairness Gini coefficient. Select **Approve assignments** to save that decision.
3. **Production & Quality:** For an active order, use `+ Add progress` on a member row. Specify how many newly produced units passed manual quality inspection. Non-accepted pieces never generate accepted-piece wages.
4. **Decision Agent:** Select an order and click `Run agent`. It observes order state, evaluates deadline, quality and margin, then stores next-action proposals. The **Action inbox** lets you approve *internal* preparations (for example, UNSENT member check-in drafts). It never sends external messages.
5. **Trust Ledger:** Press `Review payables`. See accepted units, earned labour, previously approved wages and new due wages. After explicit confirmation, mark the amounts approved. **No funds are moved**. A hash-linked event history records the approval.
6. **Member Studio:** Open a member card and use `Hear my record` if your browser has a Hindi speech synthesis voice. Toggle consent to prevent a worker from receiving *new* assignments. Existing work is preserved.
7. **Export:** Press the download icon or `Export CSV` to save current assignment/payment records.

## Optional local LLM: genuine AI explanations

By default, the **planner and risk engine** work without any model or API key. Their calculations use explainable constraints and a Bayesian-smoothed on-time-reliability estimate. These are algorithmic decision components, **not a generative model**.

For free-form language explanations on your own machine, install and start [Ollama](https://ollama.com/):

```bash
ollama pull llama3.2:3b
ollama serve
```

If `ollama serve` says the address is already in use, Ollama is probably already running, so simply run the project. Choose a model your laptop can support. Default model name is `llama3.2:3b`; to override before running the app:

```bat
set OLLAMA_MODEL=gemma3:1b
python app.py
```

The app sends only the chosen demo order snapshot and the question to **localhost:11434**, with no hosted AI service. If Ollama is unavailable, it shows a labelled **non-LLM template response**, rather than pretending AI generated it. The planner never blindly executes an LLM response.

**Speech caveat:** The Web Speech API depends on your browser and installed voices. Voice *recognition* can use a browser-vendor cloud service; do not use it for sensitive data unless its privacy characteristics have been verified. Voice *output* also depends on installed voices.

## Key technical components

| Part | Actual implementation |
|---|---|
| Front end | Responsive vanilla JavaScript, HTML and original custom CSS |
| Backend | Python standard-library `ThreadingHTTPServer` JSON API |
| Database | SQLite with transaction handling |
| Allocation | Constraint-based workload balancing: worker consent + product skill + max daily capacity + other committed work + reliability tie-break |
| Price guard | Unit material + labour minutes × hourly rate + overhead; quote = cost / (1 - target margin) |
| Fairness report | Work allocation Gini + per-member justification + visible wage per accepted unit |
| Reliability estimate | Bayesian smoothing of on-time history; only illustrative with demo records |
| Agent | Five-step observe → evaluate → propose → approve → audit loop; persistent action queue and simulated UNSENT outbox |
| Optional language AI | Local Ollama inference, no remote API key |
| Audit | SHA-256 chain of changes, verification indicator (tamper-evident, not tamper-proof) |
| Payment | Proposed/approved *ledger only*, **not bank or UPI payout** |

## Safety and honest scope

- **Prototype, NOT ready for deployment with personal or financial records.** It lacks sign-in, worker-specific access control, encryption at rest, dispute resolution, production-scale reliability and legal wage-policy verification.
- Demo member names and all order figures are invented. No real interviews or validated impact measurements are claimed.
- Actual wage obligations depend on agreements and applicable law. The labour rate in this demo is merely an input assumption, not a verified prevailing wage or minimum wage.
- Allocation fairness by unit count **does not automatically establish fair pay** for varying skills or difficulty. The field validation plan tests workers' notion of fairness.
- Completed/accepted work is entered by a human inspector; no computer-vision quality assessment is claimed.
- No public service, bank or WhatsApp integration is connected. Contact text can be prepared only as a clearly labelled UNSENT draft after human approval, and cannot be sent from this app.
- Running on localhost can work without internet after browser assets are available. Hosted multi-user and offline mobile/PWA sync are not implemented.
- The audit chain reveals isolated database edits; a malicious administrator could rewrite the whole chain. It does not prove legal authenticity or immutable storage.
- You must check the hackathon's current rules on permitted AI assistance and declare tools honestly if asked.

## Project organization

```text
DhaagaProof-AI/
├── app.py                   # REST API, database, audit, Ollama interface
├── engine.py                # cost, fairness, decision tools
├── static/
│   ├── index.html           # SPA structure and approval dialogs
│   ├── style.css            # responsive original dashboard design
│   └── app.js               # dashboard actions and states
├── tests/test_core.py       # automated logic and data integrity tests
├── docs/IDEA_SUBMISSION.md  # hackathon submission draft
├── docs/PITCH_SCRIPT.md     # presenter speaking notes
├── docs/FIELD_RESEARCH.md   # genuine interview validation protocol
├── RUN_PROJECT_WINDOWS.bat
├── .gitignore
└── README.md
```

## Run tests

```bash
python -m unittest discover -s tests -v
```

Tests cover quotes, fairness, consent, shortfalls, approval gates, payout calculations, audit integrity, member records and more.

## Next milestones after field interviews

- Per-member secure logins + data consent and dispute workflow.
- Native offline Hindi voice capture (Whisper.cpp or verified offline ASR).
- Robust optimization objective with constraints co-designed with real SHG members.
- Device-level PWA caching and queue-based sync over intermittent connectivity.
- Real pilot metrics: quote error, order lateness, payout disputes, approval time and worker satisfaction.

## Official brief

- https://thegavshackathon.com/challenges
- https://thegavshackathon.com/rules
- https://thegavshackathon.com/docs/Tech4Bharat-2026-Problem-Statements.pdf

**Author/developer attribution:** Set your own team credits in the submission and document genuine contributions. The code and prototype are AI-assisted; do not falsely state otherwise if your hackathon requires disclosure. You can make this project your own through testing, technical changes and stakeholder interviews.
