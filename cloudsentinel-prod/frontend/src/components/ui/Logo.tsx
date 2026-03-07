// src/components/ui/Logo.tsx
export function Logo({ size = 15 }: { size?: number }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="w-7 h-7 bg-gradient-to-br from-[#f59e0b] to-[#d97706] rounded-[6px] flex items-center justify-center text-sm shrink-0">⚡</div>
      <span className="font-display font-extrabold tracking-[.1em]" style={{ fontSize: size }}>
        CLOUD<span className="text-[#f59e0b]">SENTINEL</span>
      </span>
    </div>
  );
}
