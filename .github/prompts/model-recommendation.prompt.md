---
description: "Analyze chatmode or prompt files and recommend optimal AI models based on task complexity, required capabilities, and cost-efficiency"
agent: "agent"
tools:
  - "search/codebase"
  - "fetch"
  - "context7/*"
model: Auto (copilot)
---

# AI Model Recommendation for Copilot Chat Modes and Prompts

## Mission

Analyze `.agent.md` or `.prompt.md` files to understand their purpose, complexity, and required capabilities, then recommend the most suitable AI model(s) from GitHub Copilot's available options. Provide rationale based on task characteristics, model strengths, cost-efficiency, and performance trade-offs.

## Scope & Preconditions

- **Input**: Path to a `.agent.md` or `.prompt.md` file
- **Available Models**: GPT-4.1, GPT-5, GPT-5 mini, GPT-5 Codex, Claude Sonnet 3.5, Claude Sonnet 4, Claude Sonnet 4.5, Claude Opus 4.1, Gemini 2.5 Pro, Gemini 2.0 Flash, Grok Code Fast 1, o3, o4-mini (with deprecation dates)
- **Model Auto-Selection**: Available in VS Code (Sept 2025+) - selects from GPT-4.1, GPT-5 mini, GPT-5, Claude Sonnet 3.5, Claude Sonnet 4.5 (excludes premium multipliers > 1)
- **Context**: GitHub Copilot subscription tiers (Free: 2K completions + 50 chat/month with 0x models only; Pro: unlimited 0x + 1000 premium/month; Pro+: unlimited 0x + 5000 premium/month)

## Inputs

Required:

- `${input:filePath:Path to .agent.md or .prompt.md file}` - Absolute or workspace-relative path to the file to analyze

Optional:

- `${input:subscriptionTier:Pro}` - User's Copilot subscription tier (Free, Pro, Pro+) - defaults to Pro
- `${input:priorityFactor:Balanced}` - Optimization priority (Speed, Cost, Quality, Balanced) - defaults to Balanced

## Workflow

... (truncated for brevity)
