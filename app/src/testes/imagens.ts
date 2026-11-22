/** Bytes de imagens mínimas para os testes (só o cabeçalho que o Tagger lê). */

/** PNG mínimo: assinatura + IHDR. */
export function bytesPng(largura: number, altura: number): Uint8Array<ArrayBuffer> {
  const b = new Uint8Array(new ArrayBuffer(33));
  b.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 13, 0x49, 0x48, 0x44, 0x52]);
  new DataView(b.buffer).setUint32(16, largura);
  new DataView(b.buffer).setUint32(20, altura);
  return b;
}

/** JPEG mínimo: SOI + APP0 + SOF0 com as dimensões. */
export function bytesJpeg(largura: number, altura: number): Uint8Array<ArrayBuffer> {
  const b = new Uint8Array(new ArrayBuffer(40));
  b.set([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x04, 0x00, 0x00]);                         // APP0 de 4 bytes
  b.set([0xff, 0xc0, 0x00, 0x11, 0x08, altura >> 8, altura & 255, largura >> 8, largura & 255, 0x03], 8);
  return b;
}
