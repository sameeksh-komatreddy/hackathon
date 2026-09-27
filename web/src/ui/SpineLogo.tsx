export default function SpineLogo({ width, height }: { width: number; height: number }) {
  return (
    <svg width={width} height={height} viewBox="0 0 30 34" fill="none">
      <circle cx="15" cy="4" r="3.4" stroke="#F3F4F1" strokeWidth="1.8" />
      <path d="M15 8 L13 13 L16 18 L12 23 L15 29 L14 33" stroke="#F3F4F1" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="13" cy="13" r="1.6" fill="#F3F4F1" />
      <circle cx="16" cy="18" r="1.6" fill="#F3F4F1" />
      <circle cx="12" cy="23" r="1.6" fill="#F3F4F1" />
    </svg>
  )
}
