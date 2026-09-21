export default function Home() {
  // Shell de preview do sandbox: todo o sistema (backend Python FastAPI +
  // frontend HTML/JS/Three.js) roda no mini-serviço led-cad na porta 3100.
  // O acesso é feito pelo caminho estável /cad (proxy na :3000) — sem a query
  // mágica XTransformPort, que a borda externa deixou de proxyar. Nenhuma
  // lógica de CAD vive no Node (arquitetura PYTHON-FIRST, conforme especificação).
  return (
    <div className="fixed inset-0 flex flex-col bg-white">
      <iframe
        src="/cad?v=2"
        title="LED STRUCTURE CAD"
        className="flex-1 w-full h-full border-0"
        allow="fullscreen"
      />
      <noscript>
        <p style={{ padding: 16 }}>
          Este aplicativo requer JavaScript (visualizador 3D Three.js).
        </p>
      </noscript>
    </div>
  );
}
