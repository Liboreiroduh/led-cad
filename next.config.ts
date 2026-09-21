import type { NextConfig } from "next";

/* LED STRUCTURE CAD — shell :3000 → mini-serviço FastAPI :3100.
 *
 * Por que 127.0.0.1 e não localhost?
 *   O uvicorn escuta em 0.0.0.0 (IPv4). `localhost` pode resolver para ::1
 *   primeiro neste sandbox; fixar 127.0.0.1 elimina a ambiguidade.
 *
 * Rotas:
 *   /cad            → app do CAD (estável, SEM query mágica — a borda externa
 *                     deixou de proxyar ?XTransformPort=3100; /cad nunca é
 *                     interceptada porque chega normal na :3000).
 *   /api/*, /js/*   → backend + vendors (o app chama caminhos absolutos quando
 *                     não há XTransformPort na URL).
 *   ?XTransformPort → legado (preview interno e gateway :81 continuam ok).
 */
const UP = "http://127.0.0.1:3100";

const nextConfig: NextConfig = {
  output: "standalone",
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  async rewrites() {
    return {
      // beforeFiles: roda ANTES das rotas de página — sem isso, "/" com
      // ?XTransformPort=3100 era servido pelo próprio Next.js (loop do iframe).
      beforeFiles: [
        // Caminho ESTÁVEL do CAD (bookmarcável, à prova de borda externa)
        { source: "/cad", destination: `${UP}/` },
        { source: "/cad/:path*", destination: `${UP}/:path*` },
        // API e vendors servidos a partir da :3000 (app sem query mágica)
        { source: "/api/:path*", destination: `${UP}/api/:path*` },
        { source: "/js/:path*", destination: `${UP}/js/:path*` },
        // Legado: acesso direto com ?XTransformPort=N (preview interno)
        {
          source: "/:path*",
          has: [{ type: "query", key: "XTransformPort", value: "(\\d+)" }],
          destination: `${UP}/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
