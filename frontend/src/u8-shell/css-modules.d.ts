// CSS Modules for the complete workspace's own components (Vite resolves them; tests see
// plain objects).
declare module '*.module.css' {
  const classes: Readonly<Record<string, string>>;
  export default classes;
}
