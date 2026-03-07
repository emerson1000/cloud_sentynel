-- ============================================================
-- CloudSentinel — Migration: Scan quota tracking
-- Run this in Supabase SQL Editor
-- ============================================================

-- Track on-demand scans per user per week
CREATE TABLE IF NOT EXISTS scan_quota (
  id           uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id      uuid REFERENCES auth.users ON DELETE CASCADE NOT NULL,
  week_start   date NOT NULL,  -- Monday of the current week
  scans_used   int  NOT NULL DEFAULT 0,
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now(),
  UNIQUE(user_id, week_start)
);

ALTER TABLE scan_quota ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own quota" ON scan_quota FOR SELECT USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_quota_user_week ON scan_quota(user_id, week_start);

-- ── Quota limits per tier ──────────────────────────────────
-- free      → 0 on-demand scans (weekly auto only)
-- pro       → 2 on-demand scans per week
-- enterprise→ unlimited (-1)

-- Helper function: get current week's Monday
CREATE OR REPLACE FUNCTION current_week_start()
RETURNS date AS $$
  SELECT date_trunc('week', now())::date;
$$ LANGUAGE sql STABLE;

-- Helper function: check if user can scan
CREATE OR REPLACE FUNCTION can_user_scan(p_user_id uuid)
RETURNS jsonb AS $$
DECLARE
  v_tier      text;
  v_limit     int;
  v_used      int;
  v_week      date;
BEGIN
  -- Get tier
  SELECT tier INTO v_tier FROM profiles WHERE id = p_user_id;
  
  -- Map tier to limit
  v_limit := CASE v_tier
    WHEN 'free'       THEN 0
    WHEN 'pro'        THEN 2
    WHEN 'enterprise' THEN -1  -- unlimited
    ELSE 0
  END;

  -- Unlimited
  IF v_limit = -1 THEN
    RETURN jsonb_build_object('allowed', true, 'used', 0, 'limit', -1, 'tier', v_tier);
  END IF;

  -- No scans allowed
  IF v_limit = 0 THEN
    RETURN jsonb_build_object('allowed', false, 'used', 0, 'limit', 0, 'tier', v_tier,
      'reason', 'On-demand scans require the Operator plan. Upgrade to scan anytime.');
  END IF;

  -- Check usage this week
  v_week := current_week_start();
  SELECT COALESCE(scans_used, 0) INTO v_used
  FROM scan_quota
  WHERE user_id = p_user_id AND week_start = v_week;

  v_used := COALESCE(v_used, 0);

  IF v_used >= v_limit THEN
    RETURN jsonb_build_object(
      'allowed', false,
      'used',    v_used,
      'limit',   v_limit,
      'tier',    v_tier,
      'reason',  format('Weekly scan limit reached (%s/%s). Resets next Monday.', v_used, v_limit)
    );
  END IF;

  RETURN jsonb_build_object('allowed', true, 'used', v_used, 'limit', v_limit, 'tier', v_tier);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Helper function: consume one scan quota
CREATE OR REPLACE FUNCTION consume_scan_quota(p_user_id uuid)
RETURNS void AS $$
DECLARE
  v_week date := current_week_start();
BEGIN
  INSERT INTO scan_quota (user_id, week_start, scans_used)
  VALUES (p_user_id, v_week, 1)
  ON CONFLICT (user_id, week_start)
  DO UPDATE SET scans_used = scan_quota.scans_used + 1,
                updated_at = now();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
