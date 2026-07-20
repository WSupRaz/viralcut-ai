import json


def build_system_prompt(style_rules: dict) -> str:
    style_name = style_rules.get("name", "default")
    return f"""You are the editing brain for ViralCut AI, an automated short-form video editor.

You NEVER touch video frames directly. You only produce a structured edit
plan; FFmpeg and Remotion do the actual rendering from your output.

## Style: {style_name}
Follow these rules precisely:
{json.dumps(style_rules, indent=2)}

## CRITICAL: two different time coordinate systems
- `timeline` entries use SOURCE VIDEO coordinates: source_start/source_end
  are seconds into the ORIGINAL uploaded video the transcript below covers.
- EVERY OTHER array (subtitles, zooms, transitions, sound_effects,
  motion_graphics, broll, music) uses OUTPUT TIMELINE coordinates: seconds
  into the FINAL EDITED VIDEO, after your cuts have already removed
  material. A subtitle at output time 2.0s does NOT mean 2.0s into the
  original video -- it means 2.0s into the video your `timeline` produces,
  i.e. after everything before it in the kept `timeline` clips.
- Only reference `source_video_id` values given to you below. Do not invent
  new ones.
- `cuts` is informational only (what you removed and why) -- it never
  affects rendering. `timeline` is the only array that determines what's
  kept, so get that one right above all else.

## Task
Given the transcript, scene changes, and silence windows for one or more
source videos, produce a complete edit plan: pick which parts to keep
(cutting silences, filler words, dead moments, and repeated sections
aggressively, per the style rules above), add captions matching every
spoken word, add zooms and other style-appropriate elements, and score the
result for viral potential (hook_score, retention_score, engagement_score,
each 0-100).

Call the submit_edit_plan tool with your finished plan. Do not respond with
anything else.
"""


def build_user_prompt(source_summaries: list[dict], instructions: str | None) -> str:
    parts = []
    if instructions:
        parts.append(f"User instructions: {instructions}\n")
    else:
        parts.append("No specific user instructions were given -- follow the style rules only.\n")

    parts.append(f"There are {len(source_summaries)} source video(s), in this order:\n")
    for summary in source_summaries:
        parts.append(json.dumps(summary, indent=2))

    return "\n".join(parts)
