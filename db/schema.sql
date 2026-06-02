-- Black Sand — Social Media Analytics Schema
-- Phase 1: Instagram ingestion (platform-agnostic by design)
--
-- Design notes:
--   * platform / post_type are plain TEXT (+ CHECK) instead of enums, so adding
--     a new platform later is a one-line CHECK change, not an ALTER TYPE migration.
--   * Raw scraper payloads live in their own table for full reproducibility.
--   * Engagement metrics are stored as time-series snapshots so we can track how
--     a post's likes/comments/views evolve — the basis for the algorithm-rating signal.

-- ---------------------------------------------------------------------------
-- profiles — a channel / account on a platform
-- ---------------------------------------------------------------------------
create table if not exists profiles (
  id               uuid primary key default gen_random_uuid(),
  platform         text not null check (platform in ('instagram','youtube','linkedin','tiktok')),
  role             text not null default 'primary' check (role in ('primary','competitor')),
  platform_user_id text,
  username         text not null,
  full_name        text,
  biography        text,
  follower_count   bigint,
  following_count  bigint,
  post_count       bigint,
  is_verified      boolean,
  profile_pic_url  text,
  external_url     text,
  raw              jsonb,
  first_seen_at    timestamptz not null default now(),
  last_scraped_at  timestamptz,
  unique (platform, username)
);

-- ---------------------------------------------------------------------------
-- posts — a single piece of content
-- ---------------------------------------------------------------------------
create table if not exists posts (
  id               uuid primary key default gen_random_uuid(),
  profile_id       uuid not null references profiles(id) on delete cascade,
  platform         text not null check (platform in ('instagram','youtube','linkedin','tiktok')),
  platform_post_id text not null,                -- shortcode / video id
  url              text,
  post_type        text check (post_type in ('image','video','carousel','reel','story','other')),
  caption          text,
  hashtags         text[],
  mentions         text[],
  media_url        text,
  thumbnail_url    text,
  duration_seconds numeric,
  is_video         boolean,
  posted_at        timestamptz,
  raw              jsonb,
  first_seen_at    timestamptz not null default now(),
  last_scraped_at  timestamptz,
  unique (platform, platform_post_id)
);
create index if not exists posts_profile_idx on posts (profile_id);
create index if not exists posts_posted_at_idx on posts (posted_at desc);

-- ---------------------------------------------------------------------------
-- metric_snapshots — time series of engagement metrics per post
-- ---------------------------------------------------------------------------
create table if not exists metric_snapshots (
  id          bigint generated always as identity primary key,
  post_id     uuid not null references posts(id) on delete cascade,
  captured_at timestamptz not null default now(),
  likes       bigint,
  comments    bigint,
  views       bigint,
  plays       bigint,
  shares      bigint,
  saves       bigint,
  raw         jsonb
);
create index if not exists metric_snapshots_post_idx on metric_snapshots (post_id, captured_at desc);

-- ---------------------------------------------------------------------------
-- transcripts — Phase 2 (Whisper / native captions)
-- ---------------------------------------------------------------------------
create table if not exists transcripts (
  id         uuid primary key default gen_random_uuid(),
  post_id    uuid not null references posts(id) on delete cascade,
  language   text,
  source     text,                                -- 'whisper' | 'native' | ...
  text       text,
  segments   jsonb,
  created_at timestamptz not null default now(),
  unique (post_id)
);

-- ---------------------------------------------------------------------------
-- content_analysis — Phase 2 (LLM understanding of the content)
-- ---------------------------------------------------------------------------
create table if not exists content_analysis (
  id         uuid primary key default gen_random_uuid(),
  post_id    uuid not null references posts(id) on delete cascade,
  model      text,
  hook       text,
  topics     text[],
  structure  jsonb,
  tone       text,
  cta        text,
  summary    text,
  analysis   jsonb,
  created_at timestamptz not null default now()
);
create unique index if not exists content_analysis_post_uidx on content_analysis (post_id);

-- ---------------------------------------------------------------------------
-- performance_scores — Phase 3 (how well a post did vs. the channel baseline)
-- ---------------------------------------------------------------------------
create table if not exists performance_scores (
  id              uuid primary key default gen_random_uuid(),
  post_id         uuid not null references posts(id) on delete cascade,
  engagement_rate numeric,
  baseline_zscore numeric,
  rating          text check (rating in ('flop','below','avg','good','viral')),
  computed_at     timestamptz not null default now(),
  details         jsonb
);
create index if not exists performance_scores_post_idx on performance_scores (post_id);
alter table performance_scores add column if not exists view_rate   numeric;
alter table performance_scores add column if not exists view_zscore numeric;
alter table performance_scores add column if not exists algo_zscore numeric;

-- ---------------------------------------------------------------------------
-- raw_payloads — every raw scraper response, for reproducibility / re-parsing
-- ---------------------------------------------------------------------------
create table if not exists raw_payloads (
  id          bigint generated always as identity primary key,
  source      text not null,                      -- 'apify:instagram-scraper'
  entity_type text,                               -- 'profile' | 'post'
  entity_ref  text,                               -- username / shortcode
  payload     jsonb not null,
  fetched_at  timestamptz not null default now()
);
create index if not exists raw_payloads_ref_idx on raw_payloads (source, entity_ref);

-- ---------------------------------------------------------------------------
-- Phase 2b — zusätzliche strukturierte Felder + Kommentare
-- ("alle Daten, die wir bekommen können", als Features fürs spätere Forecasting)
-- ---------------------------------------------------------------------------
alter table profiles add column if not exists role text not null default 'primary';
alter table posts add column if not exists music             jsonb;
alter table posts add column if not exists tagged_usernames  text[];
alter table posts add column if not exists dimensions        jsonb;
alter table posts add column if not exists audio_url         text;

create table if not exists comments (
  id                  uuid primary key default gen_random_uuid(),
  post_id             uuid not null references posts(id) on delete cascade,
  platform_comment_id text,
  author              text,
  text                text,
  like_count          bigint,
  posted_at           timestamptz,
  raw                 jsonb,
  unique (post_id, platform_comment_id)
);
create index if not exists comments_post_idx on comments (post_id);

-- ---------------------------------------------------------------------------
-- Phase 4 — profil-weite Insights / Playbooks (LLM-Synthese + Aggregate)
-- ---------------------------------------------------------------------------
create table if not exists profile_insights (
  id          uuid primary key default gen_random_uuid(),
  profile_id  uuid not null references profiles(id) on delete cascade,
  kind        text not null default 'playbook',
  payload     jsonb not null,
  aggregates  jsonb,
  model       text,
  created_at  timestamptz not null default now()
);
create index if not exists profile_insights_idx on profile_insights (profile_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Visuelle Inhaltsanalyse (Claude Vision) — was im Bild/Video passiert
-- ---------------------------------------------------------------------------
create table if not exists visual_analysis (
  id          uuid primary key default gen_random_uuid(),
  post_id     uuid not null references posts(id) on delete cascade,
  model       text,
  source      text,          -- 'image' | 'carousel' | 'video_frames'
  n_images    int,
  payload     jsonb not null,
  created_at  timestamptz not null default now()
);
create unique index if not exists visual_analysis_post_uidx on visual_analysis (post_id);

-- ---------------------------------------------------------------------------
-- Embeddings (pgvector) — semantische Post-Vektoren für Ähnlichkeits-Prognose
-- Modell: paraphrase-multilingual-MiniLM-L12-v2 (384-dim, mehrsprachig)
-- ---------------------------------------------------------------------------
create extension if not exists vector;

create table if not exists post_embeddings (
  post_id    uuid primary key references posts(id) on delete cascade,
  model      text not null,
  embedding  vector(384) not null,
  created_at timestamptz not null default now()
);
create index if not exists post_embeddings_hnsw
  on post_embeddings using hnsw (embedding vector_cosine_ops);
