// The search reading view's CSS Module, typed beside it, so every program that compiles
// a U3 corpus file finds its classes by ordinary resolution: U3's CI typecheck compiles
// `main.tsx` from a file list, without `css-modules.d.ts` in its program (Vite resolves
// the stylesheet; tests see plain objects).
declare const classes: Readonly<Record<string, string>>;
export default classes;
