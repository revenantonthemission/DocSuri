// The shell's CSS Module, typed beside it, so every program that compiles a shell file
// finds its classes by ordinary resolution: U1's and U2's lanes type-check `App.tsx` and
// `main.tsx` from a file list, without `css-modules.d.ts` in their program (Vite
// resolves the stylesheet; tests see plain objects).
declare const classes: Readonly<Record<string, string>>;
export default classes;
