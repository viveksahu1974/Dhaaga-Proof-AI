# 3-minute pitch script — DhaagaProof AI

## 0:00–0:25 | Hook
"Ek chhota sawaal: ek self-help group ko 200 bags ka order milta hai. Kaun kitne bags banayega? Kis rate par? Agar 20 reject hue to kitni payment banti hai? Aur agar kisi member ko unfair allocation lage, uske paas proof kya hoga?"

"This is not only an accounting problem. It is a **trust problem**."

## 0:25–0:55 | What we built
"DhaagaProof is a transparent SHG order-to-wage decision system. Instead of a normal chatbot, it converts an order into a cost-checked quote, a capacity-aware work plan and an auditable member wage ledger."

## 0:55–1:45 | Live demonstration
1. Open **Orders & Quotes**. Explain per-unit material, labour and overhead assumptions.
2. Open **Generate fair-work plan** on the draft order. Show consent, capacity, proposed pieces and reasons.
3. Point out the **approval boundary**: no work assigned until people approve.
4. Show production progress and quality-accepted pieces. Explain that these become wage-eligible.
5. Open **Trust Ledger**. Demonstrate that wage approval is recorded, not paid automatically.

## 1:45–2:20 | Agent and safeguards
"Our local decision agent has five stages: observe, diagnose, propose, request approval and audit. It flags deadline and margin problems, but it won't make a financial commitment by itself. If available, an Ollama language model explains the local decision state in conversational Hindi; the planner itself is deterministic and transparent."

## 2:20–2:45 | What makes it worth trying
"Many systems digitise SHG ledgers. We are testing a tighter idea: attach every promise to a **fairness receipt** that shows how work was assigned and how accepted work became an earning. Members should not have to trust a black box."

## 2:45–3:00 | Honest close
"Today's data is fictional and the UI is a local prototype. Next we'll interview SHG members, test real allocation priorities and measure quote error, wage disputes and time saved. Our goal is not automation replacing the leader. Our goal is clear decisions workers can challenge and trust."

## Common jury Q&A

**Is the agent really AI?**  
It is a real multi-step decision agent with constrained planning and simple Bayesian-smoothed reliability estimation. Without Ollama, it is **not generative AI**. With Ollama locally, it gains a generative natural-language interface. We do not market a rule as a neural model.

**Why not just use Excel?**  
Excel can calculate wages; this prototype joins consent, capacity-aware assignments, deadlines, quality acceptance, human decision gates and audit history into one linked workflow. Whether that is enough to warrant a product must be proven in the field.

**What about bias?**  
A past-lateness measure could penalize people unfairly for caregiving or external disruptions. We use only a gentle tie-break rather than deny participation, show the rationale, let leaders override through future design, and will ask members what they find fair.

**Is the ledger tamper-proof?**  
No. It has tamper-evident linked hashes. An administrator could still rebuild the entire database chain, and there is no external signature or independent anchoring yet.

**Is it production-ready?**  
No. Before handling real identities or financial records, it needs secure accounts, role-based access, encryption, privacy review and validated wage rules.
