import type { Provider } from "@/lib/types";

const PROVIDER_CONFIG: Record<
  Provider,
  { initial: string; bgColor: string; textColor: string }
> = {
  bkash: { initial: "bK", bgColor: "#E3106D", textColor: "#fff" },
  nagad: { initial: "Na", bgColor: "#F47920", textColor: "#fff" },
  rocket: { initial: "Ro", bgColor: "#8B2BE2", textColor: "#fff" },
};

interface ProviderLogoProps {
  provider: Provider;
  size?: "sm" | "md" | "lg";
}

const sizeClasses = {
  sm: "size-8 text-label-sm",
  md: "size-10 text-label-md",
  lg: "size-12 text-title-sm",
};

/**
 * Colored-circle placeholder logo per provider.
 * Drop real SVG assets into /public/logos/ and swap this out in Phase 5.
 * Uses inline style for provider-specific colors (not BV semantic tokens) since
 * these are brand colors of third-party providers, not design-system tokens.
 */
export function ProviderLogo({ provider, size = "md" }: ProviderLogoProps) {
  const cfg = PROVIDER_CONFIG[provider];
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-pill font-semibold ${sizeClasses[size]}`}
      style={{ backgroundColor: cfg.bgColor, color: cfg.textColor }}
      aria-label={provider}
    >
      {cfg.initial}
    </span>
  );
}

export function ProviderLabel({ provider }: { provider: Provider }) {
  const labels: Record<Provider, string> = {
    bkash: "bKash",
    nagad: "Nagad",
    rocket: "Rocket",
  };
  return <>{labels[provider]}</>;
}
