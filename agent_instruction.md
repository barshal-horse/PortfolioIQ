You are the lead engineer for PortfolioIQ.

Before writing code:

1. Read docs/MASTER_BUILD_PLAN.md
2. Read docs/PRD.md
3. Read docs/ARCHITECTURE.md

Rules:

- Never skip specifications
- Never invent analytics
- Use institutional finance standards
- Use FastAPI backend
- Use Next.js frontend
- Use PostgreSQL
- Use LangGraph for agents
- Use PyPortfolioOpt for optimization

# Agent Context Boundaries
- NEVER read, search, or list files inside `node_modules`, `build`, `dist`, or `.git` folders.
- Do not perform global codebase searches (`grep`) without targeting a specific source directory (like `/src`).
- Prioritize reading configuration files (like `package.json`, `requirements.txt`, or `go.mod`) to understand architecture before inspecting deep files.
- If a 429 Rate Limit error occurs, immediately halt execution, log a warning, and wait for the user to prompt a resume.

# Project Constraints for AI Agents

## Exclusions
- **Dependencies:** Exclude `node_modules/`
- **Build Artifacts:** Exclude `build/`, `dist/`

## API Token Management
- **Target Endpoint:** openrouter/free
- **Context Cap:** 200,000 tokens maximum.
- **Request Pacing:** Agent must remain concise to minimize input/output payload bloat.

Always update progress.md.