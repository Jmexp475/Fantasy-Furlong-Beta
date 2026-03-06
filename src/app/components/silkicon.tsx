interface SilkIconProps {
  colors?: string[];
  silkUrl?: string;
  size?: number;
  className?: string;
}

export function SilkIcon({ colors = [], silkUrl, size = 32, className = "" }: SilkIconProps) {
  if (silkUrl) {
    return (
      <img
        src={silkUrl}
        alt="Horse silks"
        width={size}
        height={size}
        className={className}
        style={{ display: "inline-block", width: size, height: size, objectFit: "contain", flexShrink: 0 }}
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = "none";
        }}
      />
    );
  }

  const [body, sleeve] = colors?.length >= 2 ? colors : ["#1a6b3c", "#f5c518"];
  return (
    <svg width={size} height={size * 1.1} viewBox="0 0 32 36" className={className} style={{ display: "inline-block", flexShrink: 0 }}>
      <path d="M8 8 L4 14 L8 16 L8 34 L24 34 L24 16 L28 14 L24 8 L20 6 L16 8 L12 6 Z" fill={body} stroke="#fff" strokeWidth="0.8" />
      <path d="M4 14 L1 20 L6 22 L8 16 Z" fill={sleeve} stroke="#fff" strokeWidth="0.8" />
      <path d="M28 14 L31 20 L26 22 L24 16 Z" fill={sleeve} stroke="#fff" strokeWidth="0.8" />
      <ellipse cx="16" cy="7" rx="6" ry="4" fill={sleeve} stroke="#fff" strokeWidth="0.8" />
      <ellipse cx="16" cy="6" rx="4" ry="2.5" fill={body} />
    </svg>
  );
}
