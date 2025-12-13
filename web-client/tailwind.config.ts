import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Orcha Enterprise Blue Palette (primary)
        primary: {
          50: '#DEEBFF',
          100: '#DEEBFF',
          200: '#B3D4FF',
          300: '#4C9AFF',
          400: '#2684FF',
          500: '#0065FF',
          600: '#0052CC',
          700: '#0747A6',
          800: '#0747A6',
          900: '#172B4D',
          950: '#172B4D',
        },
        blue: {
          50: '#DEEBFF',
          600: '#0052CC',
          700: '#0747A6',
        },
        // Orcha Neutral Palette
        gray: {
          50: '#F4F5F7',
          100: '#EBECF0',
          200: '#DFE1E6',
          300: '#B3BAC5',
          400: '#7A869A',
          500: '#5E6C84',
          600: '#42526E',
          700: '#344563',
          800: '#253858',
          900: '#172B4D',
          950: '#172B4D',
        },
        // Orcha Accent Colors
        success: {
          50: '#E3FCEF',
          100: '#ABF5D1',
          200: '#79F2C0',
          300: '#57D9A3',
          400: '#36B37E',
          500: '#00875A',
          600: '#006644',
          700: '#00875A',
          800: '#00875A',
          900: '#00875A',
        },
        warning: {
          50: '#FFFAE6',
          100: '#FFF0B3',
          200: '#FFE380',
          300: '#FFC400',
          400: '#FFAB00',
          500: '#FF991F',
          600: '#FF8B00',
          700: '#FF991F',
          800: '#FF991F',
          900: '#FF991F',
        },
        error: {
          50: '#FFEBE6',
          100: '#FFBDAD',
          200: '#FF8F73',
          300: '#FF7452',
          400: '#FF5630',
          500: '#DE350B',
          600: '#BF2600',
          700: '#DE350B',
          800: '#DE350B',
          900: '#DE350B',
        },
        // Dark mode specific colors (Orcha dark theme)
        dark: {
          bg: '#1a1a1a',
          surface: '#1f1f1f',
          surfaceHover: '#252525',
          border: 'rgba(255, 255, 255, 0.08)',
          text: '#ffffff',
          textSecondary: 'rgba(255, 255, 255, 0.6)',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
      borderRadius: {
        'xs': '4px',
        'sm': '6px',
        'md': '8px',
        'lg': '10px',
        'xl': '12px',
      },
      boxShadow: {
        'soft': '0 1px 1px rgba(9, 30, 66, 0.25), 0 0 1px rgba(9, 30, 66, 0.31)',
        'medium': '0 4px 8px -2px rgba(9, 30, 66, 0.25), 0 0 1px rgba(9, 30, 66, 0.31)',
        'strong': '0 8px 16px -4px rgba(9, 30, 66, 0.25), 0 0 1px rgba(9, 30, 66, 0.31)',
        'xl': '0 20px 60px rgba(0, 0, 0, 0.15)',
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
} satisfies Config;
