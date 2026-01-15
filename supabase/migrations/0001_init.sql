create extension if not exists pgcrypto;

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  status text not null,
  yt_url text,
  source_key text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists job_events (
  id bigserial primary key,
  event_id text not null unique,
  job_id uuid not null references jobs(id) on delete cascade,
  status text not null,
  message text,
  created_at timestamptz not null default now()
);

create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger jobs_updated_at
before update on jobs
for each row execute procedure update_updated_at_column();
