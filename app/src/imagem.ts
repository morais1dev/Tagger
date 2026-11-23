/** Imagens de capa: reconhece JPEG/PNG pelos bytes (não pela extensão) e lê as dimensões sem decodificar. */
import { type Capa } from "./api";

export interface CabecalhoImagem {
  mime: "image/jpeg" | "image/png";
  largura: number;
  altura: number;
}

const ASSINATURA_PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

/** Tipo e dimensões de um PNG ou JPEG; null para qualquer outra coisa (GIF, WebP, texto…). */
export function lerCabecalhoImagem(b: Uint8Array): CabecalhoImagem | null {
  if (b.length >= 24 && ASSINATURA_PNG.every((v, i) => b[i] === v)) {
    const ler32 = (i: number) => ((b[i] << 24) | (b[i + 1] << 16) | (b[i + 2] << 8) | b[i + 3]) >>> 0;
    return { mime: "image/png", largura: ler32(16), altura: ler32(20) };
  }
  if (b.length >= 4 && b[0] === 0xff && b[1] === 0xd8) {
    let i = 2;
    while (i + 9 < b.length) {
      if (b[i] !== 0xff) { i++; continue; }
      const marcador = b[i + 1];
      if (marcador === 0xff) { i++; continue; }
      if (marcador >= 0xd0 && marcador <= 0xd8) { i += 2; continue; }                     // sem tamanho (RSTn, SOI)
      const tamanho = (b[i + 2] << 8) | b[i + 3];
      const ehQuadro = marcador >= 0xc0 && marcador <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marcador);
      if (ehQuadro) return { mime: "image/jpeg", largura: (b[i + 7] << 8) | b[i + 8], altura: (b[i + 5] << 8) | b[i + 6] };
      i += 2 + tamanho;
    }
    return { mime: "image/jpeg", largura: 0, altura: 0 };                                // JPEG válido, mas sem quadro legível
  }
  return null;
}

function paraBase64(bytes: Uint8Array): string {
  let texto = "";
  for (let i = 0; i < bytes.length; i += 0x8000) texto += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(texto);
}

/** Capa a partir dos bytes de um arquivo; null se não for JPEG nem PNG. */
export function capaDeBytes(bytes: Uint8Array): Capa | null {
  const cabecalho = lerCabecalhoImagem(bytes);
  if (!cabecalho) return null;
  return { ...cabecalho, bytes: bytes.length, url: `data:${cabecalho.mime};base64,${paraBase64(bytes)}` };
}

export async function lerArquivo(arquivo: Blob): Promise<Uint8Array> {
  if (typeof arquivo.arrayBuffer === "function") return new Uint8Array(await arquivo.arrayBuffer());
  return new Promise((resolve, reject) => {
    const leitor = new FileReader();
    leitor.onload = () => resolve(new Uint8Array(leitor.result as ArrayBuffer));
    leitor.onerror = () => reject(leitor.error);
    leitor.readAsArrayBuffer(arquivo);
  });
}

/** "JPEG · 500×500 · 12 KB", como `_descrever_capa` da v2. */
export function descreverCapa(capa: Capa): string {
  const formato = capa.mime.split("/")[1].toUpperCase().replace("JPG", "JPEG");
  const tamanho = `${Math.max(1, Math.round(capa.bytes / 1024))} KB`;
  return capa.largura > 0 ? `${formato} · ${capa.largura}×${capa.altura} · ${tamanho}` : `${formato} · ${tamanho}`;
}

/** Nome sugerido ao exportar: o álbum (ou "capa") sem caracteres inválidos, com .png ou .jpg conforme o tipo. */
export function nomeSugeridoDaCapa(album: string, mime: Capa["mime"]): string {
  const extensao = mime === "image/png" ? ".png" : ".jpg";
  return ((album || "capa") + extensao).replace(/[\\/:*?"<>|]/g, "");
}

export function extensaoAceita(nome: string): boolean {
  return /\.(jpe?g|png)$/i.test(nome);
}
