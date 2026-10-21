import { Scale } from "lucide-react";
import Link from "next/link";

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-2.5" aria-label="LegalTech Chile — inicio">
      <span className="flex h-9 w-9 items-center justify-center rounded-md bg-gold-500 text-ink-950">
        <Scale className="h-5 w-5" aria-hidden />
      </span>
      <span className={`font-serif text-lg font-semibold leading-none ${light ? "text-white" : "text-ink-900"}`}>
        LegalTech <span className={light ? "text-gold-400" : "text-gold-600"}>Chile</span>
      </span>
    </Link>
  );
}
