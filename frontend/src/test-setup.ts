import '@testing-library/jest-dom';

// Polyfill ResizeObserver for jsdom (used by recharts)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
