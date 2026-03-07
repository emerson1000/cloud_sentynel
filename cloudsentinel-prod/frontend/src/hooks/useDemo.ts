'use client';
// src/hooks/useDemo.ts
// Detects if the current user is the demo account and returns demo data

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import { DEMO_EMAIL } from '@/lib/demo-data';

export function useIsDemo() {
  const [isDemo, setIsDemo] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data: { user } }) => {
      setIsDemo(user?.email === DEMO_EMAIL);
      setLoading(false);
    });
  }, []);

  return { isDemo, loading };
}
