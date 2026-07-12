"use client";

import Image from "next/image";
import type { Provider } from "@/lib/types";

const PROVIDER_CONFIG: Record<
  Provider,
  { label: string; brandColor: string; icon: string; icon2: string }
> = {
  bkash:  { label: "bKash",  brandColor: "#E3106D", icon: "/icons/bkash.png",  icon2: "/icons/bkash2.png" },
  nagad:  { label: "Nagad",  brandColor: "#F47920", icon: "/icons/nagad.png",  icon2: "/icons/nagad2.png" },
  rocket: { label: "Rocket", brandColor: "#8B2BE2", icon: "/icons/rocket.png", icon2: "/icons/rocket2.png" },
};

interface ProviderLogoProps {
  provider: Provider;
  size?: "sm" | "md" | "lg";
  /** Use "banner" logo (bkash.png) or "badge" logo (bkash2.png). Default: badge. */
  variant?: "banner" | "badge";
}

const sizePx = { sm: 32, md: 40, lg: 48 };

export function ProviderLogo({ provider, size = "md", variant = "badge" }: ProviderLogoProps) {
  const cfg = PROVIDER_CONFIG[provider];
  const px = sizePx[size];
  const src = variant === "banner" ? cfg.icon : cfg.icon2;

  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-md overflow-hidden"
      style={{ width: px, height: px }}
      aria-label={cfg.label}
    >
      <Image
        src={src}
        alt={cfg.label}
        width={px}
        height={px}
        className="object-contain w-full h-full"
        unoptimized
      />
    </span>
  );
}

export function ProviderLabel({ provider }: { provider: Provider }) {
  return <>{PROVIDER_CONFIG[provider]?.label ?? provider}</>;
}

export function providerBrandColor(provider: Provider): string {
  return PROVIDER_CONFIG[provider]?.brandColor ?? "var(--bv-brand)";
}
