const paths = {
  cube: '<path d="m12 3 9 5v8l-9 5-9-5V8l9-5Z"/><path d="m3 8 9 5 9-5M12 13v8M7.5 5.5l9 5"/>',
  front:
    '<rect x="5" y="3" width="14" height="15" rx="1"/><path d="M12 18v3M9 21h6M5 8h14M10 3v15"/>',
  side: '<path d="m8 4 9-2v16l-9 2V4ZM12 19v3M9 22h6"/>',
  top: '<path d="m4 5 8 15 8-15M4 5h16"/><path d="M12 20V9" stroke-dasharray="2 3"/>',
  reset: '<path d="M3 10a9 9 0 1 1 2.7 8.4M3 4v6h6"/>',
  ruler:
    '<path d="m3 16 13-13 5 5L8 21l-5-5ZM7 12l2 2M10 9l2 2M13 6l2 2M4 15l2 2"/>',
  explode: '<path d="m12 3 8 4-8 4-8-4 8-4ZM4 12l8 4 8-4M4 17l8 4 8-4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  expand: '<path d="M8 3H3v5M16 3h5v5M3 16v5h5M21 16v5h-5"/>',
  pointer: '<path d="m5 3 14 9-7 1-3 7-4-17Z"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.1"/>',
  warning: '<path d="m12 3 10 18H2L12 3ZM12 9v5M12 17v.1"/>',
};

export const icon = (name, className = "") =>
  `<svg class="icon ${className}" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.cube}</svg>`;
