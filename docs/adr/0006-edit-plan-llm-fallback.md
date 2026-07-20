# ADR 0006: OpenRouter fallback for edit-plan generation

## Status
Accepted

## Context
Task 9 wired Claude into the edit-plan worker as the sole provider. During
verification, the founder's Anthropic account had insufficient credit
(same class of issue as ADR-0001's OpenAI quota problem) -- confirmed as a
real `400 invalid_request_error` from the API, not a code bug. With no
fallback, that's a hard stop on the whole pipeline any time Claude billing
has a hiccup, and the original product spec already anticipated needing a
fallback here ("AI STACK: Claude API, Whisper Large V3, Gemini fallback").

## Decision
Add `OpenRouterEditPlanProvider` (`workers/providers/llm/openrouter_provider.py`)
as a fallback, used only if the Claude call raises and `OPENROUTER_API_KEY`
is configured -- same shape as ADR-0001's OpenAI-primary/Groq-fallback
pattern. `workers/providers/llm/base.py` defines a small `EditPlanProvider`
interface so both providers are interchangeable from the task's perspective.

OpenRouter exposes an OpenAI-compatible chat-completions API in front of
many backend models, including free-tier ones, and routes to Gemini models
among others -- so this single integration point covers the spec's "Gemini
fallback" line item too, rather than adding a third, separate direct-to-Google
client for the same purpose.

Model choice (`nvidia/nemotron-3-super-120b-a12b:free`) came from querying
OpenRouter's public `/api/v1/models` endpoint for currently-available free
models with tool-calling support, not from memory -- the first model tried
(`meta-llama/llama-3.3-70b-instruct:free`) had already been moved to
paid-only by the time this was written, confirming free-tier model
availability on OpenRouter changes and the constant should be revisited if
it starts failing rather than assumed to be permanently correct.

## Consequences
- Same trade-off as ADR-0001's fallback: verified end-to-end with a real
  request, but the free-tier model's output quality is visibly lower than
  Claude's would be -- in the verification run it correctly identified and
  cut the injected silence gap and produced Hormozi-style captions with
  bolded keywords, but left captions incomplete partway through the output
  and produced no zooms despite the style rules asking for them. This is a
  fallback-quality gap, not a `validate_and_clamp()` gap -- clamping handled
  the partial plan correctly; the model simply produced less than Claude
  would have.
- `EditPlanRow.model` records which provider actually produced a given plan
  (`claude-sonnet-5` vs `openrouter:<model>`), so degraded fallback output is
  visible in the data, not silently indistinguishable from a full Claude run.
- Revisit the specific OpenRouter model periodically -- free-tier model
  availability on OpenRouter is not stable long-term.
