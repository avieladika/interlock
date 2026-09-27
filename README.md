# Interlock

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-222222?style=for-the-badge)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)

**Links:** [Repository](https://github.com/avieladika/interlock) · [Orchestrator](core/synchronizer.py) · [Validation gate](core/gates/phase4gates/gatePhase4.py)

Interlock is a development assistant that turns a Jira ticket and project context into structured requirements, a technical plan, and proposed code changes. Its workflow brings together Atlassian MCP integration, repository indexing, model-backed synthesis, and validation gates.

## The Challenge

Implementation context is often spread across tickets, documentation, and source code. Moving directly from a ticket to generated code can leave requirements, assumptions, and acceptance criteria implicit.

## The Solution

Interlock collects context before producing requirements and a plan. Each phase exchanges structured artifacts and checks whether its output is usable before continuing. The final phase produces proposed code changes for review.

## What It Includes

- Jira and Confluence access through an Atlassian MCP subprocess.
- Repository checkout and code indexing for contextual retrieval.
- Structured context, requirements, plan, and code-change artifacts.
- Validation stages for intermediate outputs.
- Generated-change JSON validation and Python syntax checks.
- Streamlit tabs for requirements, plans, code, and execution logs.

## System Model

The synchronizer coordinates phase services. Source adapters collect evidence, synthesizers transform it into artifacts, and gates decide whether the workflow can advance. Code generation returns proposed changes; syntax validation does not establish behavioral correctness.

## Core Technical Flow

Jira ticket → context discovery → evidence and requirements → technical plan → proposed changes → structural/syntax checks.

```mermaid
flowchart LR
    T[Jira ticket] --> C[Context and evidence]
    C --> R[Requirements]
    R --> P[Technical plan]
    P --> G[Proposed code changes]
    G --> V[Structure and syntax checks]
```

## Why This Design

Explicit artifacts make the transition from a requirement to a proposed change inspectable. Phase boundaries also make incomplete context visible before it reaches code generation.

## Setup

Requires Python 3.12, `uv`/`uvx` for the Atlassian MCP subprocess, Git, a Groq key, and access to your Jira/Confluence demo workspace.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Configure your own accounts and a demo repository in .env.
python -m streamlit run app.py
```

Enter a Jira ticket ID in the sidebar and start a sync cycle. Some context prompts currently appear in the launching terminal. The orchestrator checks out and indexes the configured repository under `.data/`; use a dedicated demo repository.

The current Confluence-space defaults are `ENG`, `ARCH`, and `INT`; adjust `allowed_confluence_spaces` in `core/synchronizer.py` for your workspace. Local embedding models may download on first use.

## Project map

- `app.py`: Streamlit interface.
- `core/phases/`: infrastructure, discovery, requirements, planning, and generation.
- `core/models/`: structured artifacts exchanged by phases.
- `core/gates/`: validation before progressing.
- `core/synthesizers/`: model-backed transformations.
- `core/sources/`: source adapters.
- `core/utils/`: Git and knowledge-base helpers.

## Scope and next steps

This is a prototype for assisted development. Syntax validation does not prove correctness. The pipeline generates proposed changes; it does not automatically merge or deploy them. A repeatable fixture-based demonstration and an automated regression suite are future work. Dependency versions are not fully locked.

## Author

Aviel Adika. Personal software project.
