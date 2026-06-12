/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // A API sera chamada por widgets embedados em outros dominios
  // (sites dos ISVs). CORS liberado de forma ampla na Fase 1;
  // restringir por dominio do projeto e' tarefa da Fase 2/3
  // (campo "projetos.dominio" ja existe no schema para isso).
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          { key: "Access-Control-Allow-Origin", value: "*" },
          { key: "Access-Control-Allow-Methods", value: "GET, POST, OPTIONS" },
          { key: "Access-Control-Allow-Headers", value: "Content-Type" },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
