/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
        },
        surface: {
          page: '#f8fafc',
          card: '#ffffff',
          muted: '#f1f5f9',
        },
        ink: {
          900: '#0f172a',
          700: '#334155',
          600: '#475569',
          500: '#64748b',
        },
        success: '#059669',
        warning: '#d97706',
        danger: '#dc2626',
        focus: '#93c5fd',
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        h1: ['1.875rem', { lineHeight: '2.25rem', fontWeight: '700', letterSpacing: '-0.02em' }],
        h2: ['1.375rem', { lineHeight: '1.75rem', fontWeight: '700', letterSpacing: '-0.015em' }],
        h3: ['1.0625rem', { lineHeight: '1.5rem', fontWeight: '600' }],
        body: ['0.9375rem', { lineHeight: '1.5rem', fontWeight: '400' }],
        caption: ['0.75rem', { lineHeight: '1rem', fontWeight: '500' }],
      },
      spacing: {
        page: '1.5rem',
        'page-lg': '2rem',
      },
      borderRadius: {
        control: '0.625rem',
        card: '0.875rem',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(15 23 42 / 0.05)',
        elevated: '0 12px 28px -12px rgb(15 23 42 / 0.22)',
      },
      transitionDuration: {
        'motion-micro': '180ms',
        'motion-standard': '300ms',
        'motion-emphasis': '550ms',
      },
      transitionTimingFunction: {
        'motion-standard': 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [],
}
