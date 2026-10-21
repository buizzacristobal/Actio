"use client";
import { useId } from "react";

interface Props extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
  flag?: boolean; // value was not found in the document: ask the user to review
  wide?: boolean;
}

export function Field({ label, hint, error, flag, wide, className = "", ...rest }: Props) {
  const id = useId();
  return (
    <div className={wide ? "sm:col-span-2" : ""}>
      <label htmlFor={id} className="label flex items-center justify-between gap-2">
        <span>{label}</span>
        {flag && <span className="badge !normal-case !tracking-normal">Revisar</span>}
      </label>
      <input id={id} aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-e` : undefined}
        className={`input ${error ? "!border-red-400" : flag ? "!border-gold-400" : ""} ${className}`} {...rest} />
      {error ? <p id={`${id}-e`} className="mt-1 text-xs text-red-700">{error}</p> : hint && <p className="hint">{hint}</p>}
    </div>
  );
}

export function SelectField({ label, flag, children, ...rest }: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string; flag?: boolean }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="label flex items-center justify-between gap-2">
        <span>{label}</span>
        {flag && <span className="badge !normal-case !tracking-normal">Revisar</span>}
      </label>
      <select id={id} className={`input ${flag ? "!border-gold-400" : ""}`} {...rest}>{children}</select>
    </div>
  );
}
