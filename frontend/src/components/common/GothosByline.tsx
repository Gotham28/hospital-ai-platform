interface GothosBylineProps {
  className?: string;
}

export default function GothosByline({ className = '' }: GothosBylineProps) {
  return (
    <a
      href="https://www.gothoslabs.com"
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1.5 font-gothos text-[11px] leading-[1.7] text-gothos-muted rounded-gothos-field focus-visible:outline-[3px] focus-visible:outline-solid focus-visible:outline-gothos-focus focus-visible:outline-offset-3 ${className}`}
    >
      <img src="/brand/gothos/gothos-owl-mark.png" alt="Gothos Labs" width={15} height={18} />
      <span>by</span>
      <span className="font-semibold uppercase text-gothos-forest">Gothos Labs</span>
    </a>
  );
}
