# DHAAGAPROOF AI — Hackathon Idea Submission Draft

**Track:** Agentic AI  
**Theme:** 8 — Youth & Women Empowerment  
**Official problem:** 8.1 — Women's self-help groups lose orders and members' trust because fulfilment and pay are chaotic.

## Title and one-liner
DhaagaProof AI — Fair-work and fair-pay decision agent for women's self-help groups.

## The problem
For a ten-person tailoring or craft collective, a bulk order requires the leader to estimate costs, distribute work around home-based members' actual capacity, catch problems before the deadline, accept only good pieces, and explain how money should be shared. A notebook can record numbers, but cannot easily explain why one person received 50 pieces and another 20, or show a transparent link from quality-accepted work to each payout.

## Our proposed solution
DhaagaProof is a local-first decision-support workspace that creates a transparent **fairness receipt** for the complete order. A quoting guard highlights below-target margins; a bounded allocation planner maps work onto consenting members based on skill, daily capacity, ongoing commitments and historic timeliness. A five-step decision agent monitors deadline, cost and quality exceptions and proposes next actions for group approval. Accepted work flows into an auditable per-worker wage ledger, with spoken summaries where the browser supports them.

## What differentiates the approach
Not simply SHG bookkeeping or an LLM chatbot: **Every business promise is linked to the human work and wage that fulfills it.** The proposed system combines capacity-constrained allocation, explainable fairness metrics, consent-gated decisions, human-verified product acceptance, member-readable wage accounts, and tamper-evident event history. The *combination and user research* need validation; we do not claim the world has never seen similar components.

## Five-stage autonomous decision cycle
1. Observe: inspect quantity, due dates, accepted work, costs and worker capacity.
2. Diagnose: detect missing allocations, dangerously low margins, quality rejections or nearing deadlines.
3. Plan: calculate bounded possible assignments and low-risk next steps.
4. Permission: request leader/group approval before assigning work, preparing check-in drafts or approving payables.
5. Memory: record proposals and decisions in the database's hash-linked audit log. Approved follow-up actions prepare local UNSENT message drafts; no messages are sent.

## Prototype tech and current truth
- Python standard-library HTTP API; SQLite database.
- Mobile-friendly JavaScript dashboard.
- Explainable constraint planner + Bayesian-smoothed reliability estimate (not a trained neural ML classifier).
- Optional locally-hosted Ollama model for language responses; clearly marked non-LLM fallback.
- Fictional sample members and orders. No real UPI transfers, bank integrations or genuine worker tests.

## Target users and pilot hypothesis
A 10–15-person SHG creating garments, gift packaging or handmade goods. Hypothesis to test: transparent quote and allocation receipts will reduce leader bookkeeping time, improve worker trust in wage calculations, and surface capacity gaps earlier. **These are hypotheses, not results.**

## How we will measure a real pilot
- Mean time to make a quote and allocate an order, versus notebooks.
- Count of late or missed orders, adjusted for order size and season.
- Count of payout disputes and time to resolve them.
- Absolute deviation between quoted and actual costs.
- Member comprehension of allocations and earnings (usability survey).
- Distribution of hours and earnings; qualitative assessment of fairness.

## Privacy and responsible AI
Only consented members are eligible for new allocations. People approve commitments and payables. Worker-specific sign-in and encryption would be mandatory before deploying this beyond a fictional demonstration. The agent must explain evidence and uncertainty; it does not autonomously move money.

## Business model hypothesis
Low-fee SaaS through SHG federations, producer companies and livelihood-support partners, with assisted onboarding and local-language support. Pricing and willingness-to-pay must be validated in field interviews rather than invented.

## Request for feedback
We want to test the algorithm's fairness against actual women-led collectives' norms of skill, piece complexity, family availability and quality review, then iterate using real operational constraints.
