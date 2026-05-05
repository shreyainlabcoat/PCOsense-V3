# PCOSense Live Demo Script (8-10 minutes)

## Slide 1 - Title (30 sec)

**Say:**  
"We are Team PCOSense. This is our production-ready AI-powered PCOS screening assistant built with a three-agent architecture, explainable ML, and evidence retrieval."

## Slide 2 - Problem and Stakeholders (45 sec)

**Say:**  
"PCOS screening is often delayed because early symptom interpretation is fragmented. Our stakeholders are patients, clinicians, and researchers. We provide faster pre-consultation clarity with transparent quality controls."

## Slide 3 - Architecture (60 sec)

**Show:** `docs/multi_agent_architecture.md` diagram  
**Say:**  
"The orchestrator coordinates three agents: Data Validator, Evidence Retriever, and Risk Assessor. Outputs are merged into one response with metadata and quality metrics."

## Slide 4 - Live App Walkthrough (2.5 min)

**Demo steps:**
1. Open deployed app link.
2. Enter age, cycle pattern, symptoms, optional labs.
3. Click **Run assessment**.
4. Walk through results in order:
   - Validation
   - Clinical evidence
   - Risk score and factors
   - Recommendation
   - Quality control bar/report

**Say:**  
"This ordering is deliberate so users see data trustworthiness before acting on recommendations."

## Slide 5 - Quality Control Evidence (1.5 min)

**Show:** QC panel and API examples:
- `GET /api/v1/health`
- `GET /api/v1/readiness`
- `GET /api/v1/quality-summary`

**Say:**  
"We quantify reliability through validation scores, model confidence, plausibility checks, and evidence quality. This gives stakeholders objective confidence signals, not just model outputs."

## Slide 6 - Agentic Loop (1 min)

**Say:**  
"Our evidence agent includes a bounded recovery loop. If initial retrieval is sparse, it automatically broadens the query and retries once. We expose loop telemetry in output for auditability."

## Slide 7 - Production Readiness (1 min)

**Say:**  
"For production readiness, we focused on startup resilience, graceful degradation, endpoint health/readiness checks, and reliable quality report generation. The system remains usable even if optional components are unavailable."

## Slide 8 - Impact and Next Steps (45 sec)

**Say:**  
"This app is a screening aid, not a diagnosis tool. Next steps include clinician-in-the-loop feedback logging, longitudinal patient trend views, and stronger evidence citation UX."

## Backup Technical Q&A (optional)

- Why this model? -> XGBoost provides robust tabular performance and fast inference.
- How is explainability done? -> SHAP top factors per patient.
- How is external evidence handled? -> ChromaDB + PubMed with retry loop.
- How do we know it works reliably? -> health/readiness endpoints + QC score framework.
