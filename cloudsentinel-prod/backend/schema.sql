-- ============================================================
-- CloudSentinel — Database Schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- ── Profiles (extended user info) ─────────────────────────────────────────
create table if not exists profiles (
  id                  uuid references auth.users on delete cascade primary key,
  full_name           text,
  tier                text not null default 'free' check (tier in ('free','pro','enterprise')),
  notification_config jsonb default '{"threshold":15,"email":true,"telegram":false,"chat_id":""}',
  stripe_customer_id  text,
  created_at          timestamptz default now(),
  updated_at          timestamptz default now()
);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name)
  values (new.id, new.raw_user_meta_data->>'full_name');
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ── Cloud connections ──────────────────────────────────────────────────────
create table if not exists cloud_connections (
  id                    uuid primary key default uuid_generate_v4(),
  user_id               uuid references auth.users on delete cascade not null,
  provider              text not null check (provider in ('azure','aws','gcp')),
  display_name          text not null,
  account_identifier    text not null,   -- subscription_id / aws_account_id / project_id
  credentials_encrypted text not null,   -- Fernet-encrypted JSON blob
  is_active             boolean default true,
  last_scan_at          timestamptz,
  created_at            timestamptz default now()
);

-- ── Reports ───────────────────────────────────────────────────────────────
create table if not exists reports (
  id                       uuid primary key default uuid_generate_v4(),
  connection_id            uuid references cloud_connections on delete cascade not null,
  user_id                  uuid references auth.users on delete cascade not null,
  provider                 text not null,
  report_type              text not null default 'weekly' check (report_type in ('weekly','on_demand','daily_check')),
  period_start             timestamptz not null,
  period_end               timestamptz not null,
  total_spend              numeric(12,2) default 0,
  total_savings_identified numeric(12,2) default 0,
  orphan_count             int default 0,
  anomaly_detected         boolean default false,
  report_data              jsonb not null default '{}',
  created_at               timestamptz default now()
);

-- ── Notification log (deduplication) ──────────────────────────────────────
create table if not exists notification_log (
  id              uuid primary key default uuid_generate_v4(),
  user_id         uuid references auth.users on delete cascade not null,
  connection_id   uuid references cloud_connections on delete cascade not null,
  notification_type text not null,
  channel         text not null,
  sent_at         timestamptz default now(),
  metadata        jsonb default '{}'
);

-- ── Row Level Security ────────────────────────────────────────────────────
alter table profiles          enable row level security;
alter table cloud_connections enable row level security;
alter table reports           enable row level security;
alter table notification_log  enable row level security;

-- Profiles: only own row
create policy "Users can view own profile"   on profiles for select using (auth.uid() = id);
create policy "Users can update own profile" on profiles for update using (auth.uid() = id);

-- Connections: only own connections
create policy "Users can view own connections"   on cloud_connections for select using (auth.uid() = user_id);
create policy "Users can insert own connections" on cloud_connections for insert with check (auth.uid() = user_id);
create policy "Users can update own connections" on cloud_connections for update using (auth.uid() = user_id);
create policy "Users can delete own connections" on cloud_connections for delete using (auth.uid() = user_id);

-- Reports: only own reports
create policy "Users can view own reports"   on reports for select using (auth.uid() = user_id);
create policy "Users can insert own reports" on reports for insert with check (auth.uid() = user_id);

-- Notification log: only own
create policy "Users can view own notifications" on notification_log for select using (auth.uid() = user_id);

-- ── Performance indexes ───────────────────────────────────────────────────
create index if not exists idx_connections_user     on cloud_connections(user_id);
create index if not exists idx_reports_connection   on reports(connection_id);
create index if not exists idx_reports_user         on reports(user_id);
create index if not exists idx_reports_created      on reports(created_at desc);
create index if not exists idx_notif_user_date      on notification_log(user_id, sent_at desc);

-- ── Done! ─────────────────────────────────────────────────────────────────
-- select 'CloudSentinel schema created ✓' as status;
