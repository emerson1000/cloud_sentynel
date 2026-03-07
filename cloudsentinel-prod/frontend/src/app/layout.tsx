// src/app/layout.tsx
import type { Metadata } from 'next';
import { DM_Mono, Syne } from 'next/font/google';
import { Toaster } from 'react-hot-toast';
import './globals.css';

const dmMono = DM_Mono({
  subsets: ['latin'],
  weight: ['300', '400', '500'],
  variable: '--font-mono',
  display: 'swap',
});

const syne = Syne({
  subsets: ['latin'],
  weight: ['700', '800'],
  variable: '--font-display',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'CloudSentinel — Cloud Cost Intelligence',
  description: 'Stop paying for cloud resources you forgot. Detect zombies, anomalies and optimization opportunities across Azure, AWS and GCP.',
  openGraph: {
    title: 'CloudSentinel',
    description: 'Multi-cloud cost intelligence for startups.',
    url: 'https://cloudsentinel.io',
    siteName: 'CloudSentinel',
    images: [{ url: '/og-image.png', width: 1200, height: 630 }],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${dmMono.variable} ${syne.variable}`}>
      <body className="bg-[#03070f] text-[#e2e8f0] font-mono antialiased">
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#060d1a',
              color: '#e2e8f0',
              border: '1px solid #0d2340',
              fontFamily: 'var(--font-mono)',
              fontSize: '13px',
            },
            success: { iconTheme: { primary: '#22c55e', secondary: '#060d1a' } },
            error:   { iconTheme: { primary: '#ef4444', secondary: '#060d1a' } },
          }}
        />
      </body>
    </html>
  );
}
