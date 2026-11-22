import { type ClipboardEvent, type DragEvent, useEffect, useState } from "react";
import { type AcaoCapa, type Capa, type Faixa, type Ponte, caminhoDaPasta, valorDoCampo } from "../api";
import { TEXTO_VARIAS_CAPAS, capaDaSelecao, temAlgumaCapa, textoCapaPendente } from "../edicao";
import { descreverCapa, capaDeBytes, extensaoAceita, lerArquivo, nomeSugeridoDaCapa } from "../imagem";

interface Props {
  faixas: readonly Faixa[];
  ponte: Ponte;
  aoAtualizar(faixas: Faixa[]): void;
  aoAvisar(texto: string): void;
  /** Pergunta sim/não ao usuário (substituir o cover da pasta). */
  confirmar(texto: string): Promise<boolean> | boolean;
}

const AVISO_FORMATO = "Só imagens JPEG ou PNG (.jpg, .jpeg, .png) servem de capa.";
const AVISO_ILEGIVEL = "Não consegui abrir essa imagem.";

/** Bloco da capa: quadro de 112 px, informações, "Trocar capa" e o menu de mais opções. */
export function CapaEditor({ faixas, ponte, aoAtualizar, aoAvisar, confirmar }: Props) {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const [arrastando, setArrastando] = useState(false);
  const ids = faixas.map((f) => f.id);
  const mostrada = capaDaSelecao(faixas);
  const pendente = textoCapaPendente(faixas);
  const temPendencia = faixas.some((f) => f.capaPendente !== undefined);

  async function aplicar(acao: AcaoCapa) {
    aoAtualizar(await ponte.definirCapa(ids, acao));
  }

  async function aceitarArquivo(arquivo: Blob & { name?: string }) {
    if (arquivo.name && !extensaoAceita(arquivo.name) && !arquivo.type.startsWith("image/")) {
      aoAvisar(AVISO_FORMATO);
      return;
    }
    const capa = capaDeBytes(await lerArquivo(arquivo));
    if (!capa) {
      aoAvisar(arquivo.type === "image/png" || arquivo.type === "image/jpeg" ? AVISO_ILEGIVEL : AVISO_FORMATO);
      return;
    }
    await aplicar({ tipo: "definir", capa });
  }

  async function trocar() {
    const capa = await ponte.escolherImagem();
    if (capa) await aplicar({ tipo: "definir", capa });
  }

  async function colar() {
    const capa = await ponte.lerImagemDaAreaDeTransferencia();
    if (!capa) {
      aoAvisar("Não há imagem na área de transferência.");
      return;
    }
    await aplicar({ tipo: "definir", capa });
  }

  async function exportar() {
    if (mostrada.tipo !== "capa") return;
    const sugestao = nomeSugeridoDaCapa(valorDoCampo(faixas[0], "album"), mostrada.capa.mime);
    const nome = await ponte.exportarCapa(mostrada.capa, sugestao);
    if (nome) aoAvisar(`Capa exportada para ${nome}`);
  }

  async function salvarCover() {
    if (mostrada.tipo !== "capa") return;
    const nome = mostrada.capa.mime === "image/png" ? "cover.png" : "cover.jpg";
    const existentes = await ponte.pastasComCover(ids, nome);
    if (existentes.length > 0 && !(await confirmar(`Já existe um ${nome} em ${existentes.length} pasta(s). Substituir?`))) return;
    const { gravadas, falhas } = await ponte.salvarCoverNaPasta(ids, mostrada.capa, nome);
    if (falhas > 0) {
      aoAvisar(`Não consegui gravar ${nome} em ${falhas} pasta(s).`);
      return;
    }
    const pastas = [...new Set(faixas.map(caminhoDaPasta))];
    aoAvisar(`${nome} salvo em ${gravadas === 1 ? (pastas[0].split(/[\\/]/).pop() ?? pastas[0]) : `${gravadas} pastas`}`);
  }

  function abrirMenu(x: number, y: number) {
    setMenu({ x, y });
  }

  function soltar(e: DragEvent) {
    e.preventDefault();
    setArrastando(false);
    const arquivo = e.dataTransfer.files[0];
    if (arquivo) void aceitarArquivo(arquivo);
    else aoAvisar(AVISO_FORMATO);
  }

  function colarNoQuadro(e: ClipboardEvent) {
    const arquivo = [...e.clipboardData.files].find((a) => a.type.startsWith("image/"));
    if (!arquivo) return;                                   // texto colado: nada a fazer aqui
    e.preventDefault();
    void aceitarArquivo(arquivo);
  }

  const info = mostrada.tipo === "capa" ? descreverCapa(mostrada.capa) : mostrada.tipo === "varias" ? "Capas diferentes" : "Nenhuma imagem";

  return (
    <div className="bloco-capa">
      <div
        className={`quadro-capa${arrastando ? " arrastando" : ""}`}
        data-testid="quadro-capa"
        tabIndex={0}
        aria-label="Capa"
        title="Arraste uma imagem, cole (Ctrl+V) ou clique com o botão direito"
        onContextMenu={(e) => { e.preventDefault(); abrirMenu(e.clientX, e.clientY); }}
        onDragOver={(e) => { e.preventDefault(); setArrastando(true); }}
        onDragEnter={(e) => { e.preventDefault(); setArrastando(true); }}
        onDragLeave={() => setArrastando(false)}
        onDrop={soltar}
        onPaste={colarNoQuadro}
      >
        {mostrada.tipo === "capa" ? <img src={mostrada.capa.url} alt="Capa do álbum" draggable={false} />
          : <span className="quadro-texto">{mostrada.tipo === "varias" ? TEXTO_VARIAS_CAPAS : "Sem capa"}</span>}
      </div>
      <div className="capa-lado">
        <div className="capa-info" aria-live="polite">
          {pendente && <div className="capa-pendente">{pendente} <span className="marca" aria-hidden="true">●</span></div>}
          <div className="mono">{info}</div>
        </div>
        <div className="capa-botoes">
          <button type="button" onClick={() => void trocar()}>Trocar capa</button>
          <button
            type="button"
            className="icone"
            aria-label="Mais opções da capa"
            title="Mais opções da capa"
            aria-haspopup="menu"
            onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); abrirMenu(r.left, r.bottom); }}
          >…</button>
        </div>
      </div>
      {menu && (
        <MenuCapa
          x={menu.x}
          y={menu.y}
          temCapaMostrada={mostrada.tipo === "capa"}
          temAlguma={temAlgumaCapa(faixas)}
          temPendencia={temPendencia}
          aoFechar={() => setMenu(null)}
          acoes={{
            escolher: () => void trocar(),
            colar: () => void colar(),
            exportar: () => void exportar(),
            cover: () => void salvarCover(),
            remover: () => void aplicar({ tipo: "remover" }),
            manter: () => void aplicar(null),
          }}
        />
      )}
    </div>
  );
}

interface PropsMenu {
  x: number;
  y: number;
  temCapaMostrada: boolean;
  temAlguma: boolean;
  temPendencia: boolean;
  acoes: Record<"escolher" | "colar" | "exportar" | "cover" | "remover" | "manter", () => void>;
  aoFechar(): void;
}

/** Menu "Mais opções da capa" (botão … e clique direito no quadro). */
function MenuCapa({ x, y, temCapaMostrada, temAlguma, temPendencia, acoes, aoFechar }: PropsMenu) {
  useEffect(() => {
    const fechar = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    document.addEventListener("keydown", fechar);
    return () => document.removeEventListener("keydown", fechar);
  }, [aoFechar]);

  const item = (texto: string, acao: () => void, ativo = true) => (
    <button type="button" role="menuitem" disabled={!ativo} onClick={() => { aoFechar(); acao(); }}>{texto}</button>
  );
  return (
    <>
      <div className="menu-fundo" onClick={aoFechar} onContextMenu={(e) => { e.preventDefault(); aoFechar(); }} />
      <div role="menu" aria-label="Opções da capa" className="menu" style={{ left: x, top: y }}>
        {item("Escolher imagem…", acoes.escolher)}
        {item("Colar imagem", acoes.colar)}
        {item("Exportar capa…", acoes.exportar, temCapaMostrada)}
        {item("Salvar como cover.jpg na pasta", acoes.cover, temCapaMostrada)}
        <hr />
        {item("Remover capa", acoes.remover, temAlguma)}
        {item("Manter capa original", acoes.manter, temPendencia)}
      </div>
    </>
  );
}
