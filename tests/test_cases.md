# Test Cases

Run these after building the knowledge base with **bundled Acme Corp sample data**.

## Test Case 1: Docs-Only Question

**Question:** "How does API authentication work in this system?"

**Expected behavior:**
- Planner routes to `docs`
- Docs agent retrieves chunks from `authentication_guide.pdf`
- High grounding confidence
- Answer describes OAuth 2.0 JWT bearer tokens, SAML SSO, authorization code flow, JWKS validation
- Citations point to `authentication_guide.pdf`

**Validates:** Planner routing, docs retrieval, grounding check, citation generation.

---

## Test Case 2: GitHub-Only Question

**Question:** "When was API key authentication introduced?"

**Expected behavior:**
- Planner routes to `github`
- GitHub agent retrieves PR #142 and related commits
- High recency scores on March 2025 items
- Answer cites PR #142 ("Migrate authentication from OAuth2/SAML to API keys") and commit dates
- Citations include clickable GitHub URLs to `acme-corp/nexus-integration-hub`

**Validates:** GitHub-only routing, recency-weighted ranking, PR/commit citations.

---

## Test Case 3: Conflict Question (Key Demo)

**Question:** "What authentication method does the system currently use?"

**Expected behavior:**
- Planner routes to `both`
- Docs agent finds `authentication_guide.pdf` stating OAuth 2.0 + SAML SSO is the sole mechanism
- GitHub agent finds PR #142 and commits showing migration to API keys
- Reconciler detects **conflict**
- UI shows "⚠️ Conflict Detected" panel with both perspectives side-by-side
- Final answer presents both views and recommends trusting GitHub for current state

**Validates:** Multi-source retrieval, reconciliation node, conflict surfacing, evidence ranking with recency preference.

---

## Test Case 4: Self-Correction (Optional)

**Question:** "What is the flarnitz protocol for SAP integration?"

**Expected behavior:**
- Retrieval returns weak/no relevant evidence (nonsense term)
- Reconciler marks evidence as insufficient
- Self-corrector rewrites query (e.g., adds "Nexus Integration Hub SAP connector")
- After max retries, answer honestly states insufficient evidence

**Validates:** Bounded self-correction loop, query rewriting.
