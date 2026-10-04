/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    borderRadius: {
      none: '0px',
      DEFAULT: '0px',
    },
    boxShadow: {
      none: 'none',
      DEFAULT: 'none',
    },
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      ground: 'var(--color-ground, #101215)',
      surface: 'var(--color-surface, #161A1E)',
      'surface-raised': 'var(--color-surface-raised, #1D2227)',
      rule: 'var(--color-rule, #2A3036)',
      'rule-strong': 'var(--color-rule-strong, #414A53)',
      ink: 'var(--color-ink, #E8E6E1)',
      'ink-2': 'var(--color-ink-2, #A9ADB1)',
      'ink-3': 'var(--color-ink-3, #737A82)',
      attention: 'var(--color-attention, #D8A24A)',
      fact: 'var(--color-fact, #74B08C)',
      policy: 'var(--color-policy, #8FA3B8)',
      safety: 'var(--color-safety, #CE5F51)',
    },
    fontFamily: {
      sans: ['"IBM Plex Sans"', 'sans-serif'],
      mono: ['"IBM Plex Mono"', 'monospace'],
    },
    extend: {},
  },
  plugins: [],
};
