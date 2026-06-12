// ============================================================
// Build do widget — gera dist/widget.js (minificado, IIFE)
//
// Como rodar:
//   npm run build        -> build unico
//   npm run dev          -> watch mode (rebuild automatico)
// ============================================================

import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const opcoes = {
  entryPoints: ["src/widget.js"],
  outfile: "dist/widget.js",
  bundle: true,
  minify: true,
  format: "iife",
  target: ["es2020"],
  sourcemap: true,
};

if (watch) {
  const ctx = await esbuild.context(opcoes);
  await ctx.watch();
  console.log("Observando mudancas em src/widget.js... (Ctrl+C para sair)");
} else {
  await esbuild.build(opcoes);
  console.log("Build concluido: dist/widget.js");
}
