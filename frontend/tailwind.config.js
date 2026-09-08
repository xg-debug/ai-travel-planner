/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 清新旅行主题色 - 浅色系
        travel: {
          primary: '#2563EB',
          secondary: '#111827',
          accent: '#7B4FF6',
          ocean: '#111827',
          sky: '#2563EB',
          mint: '#0F766E',
          gray: '#7A8494',
          light: '#F6F7F9',
          lighter: '#FFFFFF', // 纯白
          muted: '#94A3B8', // 柔和灰
          border: '#E2E8F0', // 边框灰
          card: '#FFFFFF', // 卡片白
          'primary-light': '#818CF8', // 浅靛蓝
          'secondary-light': '#34D399', // 浅翠绿
          'accent-light': '#FBBF24', // 浅琥珀
        }
      },
      fontFamily: {
        'display': ['SF Pro Display', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'], // 清新显示字体
        'body': ['SF Pro Text', 'Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        'code': ['SF Mono', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
        'chinese': ['SF Pro Display', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
      },
      animation: {
        // 清新动画
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'float-soft': 'floatSoft 6s ease-in-out infinite',
        'shimmer': 'shimmer 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: 0 },
          '100%': { opacity: 1 }
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: 0 },
          '100%': { transform: 'translateY(0)', opacity: 1 }
        },
        pulseSoft: {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.8 }
        },
        floatSoft: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' }
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' }
        }
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, #4F46E5 0%, #818CF8 100%)',
        'gradient-secondary': 'linear-gradient(135deg, #10B981 0%, #34D399 100%)',
        'gradient-accent': 'linear-gradient(135deg, #F59E0B 0%, #FBBF24 100%)',
        'gradient-light': 'linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 100%)',
        'subtle-grid': 'linear-gradient(rgba(148, 163, 184, 0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(148, 163, 184, 0.1) 1px, transparent 1px)',
        'noise-subtle': "url('data:image/svg+xml,%3Csvg viewBox=\"0 0 200 200\" xmlns=\"http://www.w3.org/2000/svg\"%3E%3Cfilter id=\"noise\"%3E%3CfeTurbulence type=\"fractalNoise\" baseFrequency=\"0.65\" numOctaves=\"3\" stitchTiles=\"stitch\"/%3E%3C/filter%3E%3Crect width=\"100%25\" height=\"100%25\" filter=\"url(%23noise)\" opacity=\"0.02\"/%3E%3C/svg%3E')",
      },
      backdropBlur: {
        'light': '8px',
      },
      boxShadow: {
        'soft': '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',
        'medium': '0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.03)',
        'large': '0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02)',
        'inner': 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.03)',
        'travel-card': '0 10px 28px rgba(17, 24, 39, 0.06)',
        'travel-card-lg': '0 18px 42px rgba(17, 24, 39, 0.10)',
      }
    },
  },
  plugins: [],
}
