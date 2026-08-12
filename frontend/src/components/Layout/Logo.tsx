import type { CSSProperties } from 'react'

interface Props {
  size?: number
  style?: CSSProperties
  className?: string
}

/**
 * 电商分析 Logo：几何化数据柱状图 + AI 星芒
 * 尺寸 32x32，用渐变描边 + 半透明填充
 */
function Logo({ size = 32, style, className }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={style}
      className={className}
    >
      <defs>
        <linearGradient id="lg-bar" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#6366f1" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
        <linearGradient id="lg-spark" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop stopColor="#a78bfa" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
      </defs>

      {/* 外框圆角矩形 */}
      <rect
        x="2" y="2" width="44" height="44" rx="10"
        stroke="url(#lg-bar)"
        strokeWidth="1.5"
        fill="rgba(99,102,241,0.1)"
      />

      {/* 柱状图 - 三根柱 */}
      <rect x="11" y="24" width="6" height="14" rx="2" fill="url(#lg-bar)" opacity="0.85" />
      <rect x="20" y="16" width="6" height="22" rx="2" fill="url(#lg-bar)" opacity="0.95" />
      <rect x="29" y="20" width="6" height="18" rx="2" fill="url(#lg-bar)" opacity="0.75" />

      {/* AI 星芒 - 右上角小菱形 */}
      <path
        d="M37 10 L39 13 L37 16 L35 13 Z"
        fill="url(#lg-spark)"
        opacity="0.9"
      />
      {/* 星光点 */}
      <circle cx="35" cy="21" r="1.2" fill="url(#lg-spark)" opacity="0.6" />
      <circle cx="42" cy="16" r="1" fill="url(#lg-spark)" opacity="0.5" />
    </svg>
  )
}

export default Logo
