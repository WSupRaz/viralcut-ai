# Database Schema

Implemented as SQLAlchemy 2.0 models + Alembic migrations (ADR-0002). Shown
here in table form — this is the source-of-truth design; actual model code
comes in Phase 1 implementation.

All tables: `id UUID PK default gen_random_uuid()`, `created_at`, `updated_at`
timestamptz, omitted below per-table for brevity except where noteworthy.

## users
| column | type | notes |
|---|---|---|
| email | text, unique | |
| password_hash | text, nullable | nullable to allow OAuth-only accounts |
| name | text | |
| avatar_url | text, nullable | |
| plan | enum(free, creator, pro, business) | drives credit allocation |
| stripe_customer_id | text, nullable, unique | |
| onboarded_at | timestamptz, nullable | |

## projects
| column | type | notes |
|---|---|---|
| user_id | FK users | |
| title | text | |
| status | enum(draft, processing, ready, failed, archived) | |
| target_aspect_ratio | enum(9:16, 16:9, 1:1) | |
| style_id | FK styles, nullable | |
| instructions | text, nullable | free-text user prompt, e.g. "make this look like Alex Hormozi" |

## source_videos
| column | type | notes |
|---|---|---|
| project_id | FK projects | |
| r2_key_raw | text | original upload |
| r2_key_proxy | text, nullable | low-res proxy, populated after step 2 |
| duration_seconds | numeric, nullable | populated after probe |
| order_index | int | clip arrangement in project timeline |
| status | enum(uploaded, proxy_ready, metadata_ready, failed) | |

## metadata
One row per `source_video`. This is the *only* input Claude ever receives
(never raw video) — see architecture.md step 5.
| column | type | notes |
|---|---|---|
| source_video_id | FK source_videos, unique | |
| transcript | jsonb | word-level timestamps + speaker labels |
| scene_changes | jsonb | array of timestamps from PySceneDetect |
| silences | jsonb | array of {start, end} |
| speakers | jsonb | diarization segments — single full-duration segment in Phase 1, see ADR-0004 amendment |
| provider | text | which ASR provider produced this (ADR-0001) |

## edit_plans
One row per project per generation attempt (kept, not overwritten, so
regenerations are auditable and Claude output quality is reviewable).
| column | type | notes |
|---|---|---|
| project_id | FK projects | |
| style_id | FK styles, nullable | |
| plan_json | jsonb | validated against `edit-plan-schema` package before insert |
| viral_score | jsonb | {hook_score, retention_score, engagement_score} |
| model | text | e.g. "claude-sonnet-5" — track which model produced it |
| status | enum(generated, approved, superseded) | |

## timelines
User-editable, seeded from an `edit_plan` but diverges once a human drags
clips around. Separate from `edit_plans` intentionally — one is AI output,
the other is current editable state.
| column | type | notes |
|---|---|---|
| project_id | FK projects | |
| source_edit_plan_id | FK edit_plans, nullable | |
| state_json | jsonb | Clip/Track/Transition/Caption/Overlay/Effect/Audio entities |

## exports
| column | type | notes |
|---|---|---|
| project_id | FK projects | |
| timeline_id | FK timelines | |
| aspect_ratio | enum(9:16, 16:9, 1:1) | |
| quality | enum(720p, 1080p, 4k) | |
| r2_key_output | text, nullable | populated on completion |
| job_id | FK jobs | |

## jobs
Generic job-tracking row; one per queue task across the whole pipeline (proxy,
metadata, edit-plan, render). Gives you one place to build a progress UI.
| column | type | notes |
|---|---|---|
| project_id | FK projects | |
| type | enum(proxy, metadata_extraction, edit_plan, render) | |
| status | enum(queued, running, succeeded, failed, retrying) | |
| progress_pct | int, default 0 | |
| error | text, nullable | |
| retry_count | int, default 0 | |
| celery_task_id | text, nullable | |

## assets
Cached, content-hashed library entries (transitions, sound effects, music,
motion graphics templates, fetched B-roll).
| column | type | notes |
|---|---|---|
| type | enum(transition, sound_effect, music, motion_graphic, broll) | |
| source | enum(internal, pexels, pixabay) | |
| content_hash | text, unique | dedupe key |
| r2_key | text | |
| license_meta | jsonb, nullable | required for pexels/pixabay attribution/compliance |
| tags | text[] | search keywords for retrieval |

## templates
| column | type | notes |
|---|---|---|
| name | text | |
| asset_id | FK assets, nullable | for motion-graphics templates |
| remotion_composition_id | text | maps to `apps/render-worker` composition |
| config_schema | jsonb | prop shape the template accepts |

## styles
Preset engines (Hormozi, Documentary, MrBeast, Ali Abdaal, ...).
| column | type | notes |
|---|---|---|
| name | text, unique | |
| slug | text, unique | |
| rules_json | jsonb | cut pacing, caption style, zoom rules, transition rules — fed into Claude's prompt, not hardcoded editing logic |
| is_system | boolean | false for future user-created custom styles |

## billing_accounts
| column | type | notes |
|---|---|---|
| user_id | FK users, unique | |
| stripe_subscription_id | text, nullable | |
| plan | enum(free, creator, pro, business) | mirrors users.plan, source of truth for billing state |
| renews_at | timestamptz, nullable | |

## credits
Ledger, not a mutable balance column — auditable, and correct under
concurrent workers debiting simultaneously.
| column | type | notes |
|---|---|---|
| user_id | FK users | |
| amount | int | positive (grant/purchase) or negative (spend) |
| reason | enum(monthly_grant, purchase, render_spend, refund, promo) | |
| project_id | FK projects, nullable | |
| balance_after | int | denormalized snapshot for fast reads |

## Indexing notes
- `jobs(project_id, status)` — dashboard polling hot path.
- `source_videos(project_id, order_index)` — timeline ordering.
- `credits(user_id, created_at)` — balance history / statements.
- `assets(content_hash)` unique — this is what makes the asset cache actually
  work; without it "assets should be cached" is just a comment, not a system.
