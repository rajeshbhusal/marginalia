export function Logo() {
  return (
    <span className="flex items-center gap-2">
      <svg viewBox="0 0 64 64" className="size-7 shrink-0" aria-hidden>
        <rect x="6" y="4" width="40" height="56" rx="6" className="fill-brand" />
        <rect x="14" y="16" width="20" height="4" rx="2" fill="#fff" opacity=".9" />
        <rect x="14" y="26" width="24" height="4" rx="2" fill="#fff" opacity=".9" />
        <rect x="14" y="36" width="16" height="4" rx="2" fill="#fff" opacity=".9" />
        <rect x="40" y="22" width="20" height="16" rx="4" fill="#ffc400" />
        <path d="M44 38l-4 7v-7z" fill="#ffc400" />
      </svg>
      {/* The mark alone on the narrowest phones, so the header still fits */}
      <span className="font-serif text-xl font-semibold tracking-tight text-ink max-[22.5rem]:sr-only">
        Marginalia
      </span>
    </span>
  );
}
