/** Gêneros sugeridos ao digitar: os mesmos de `config.PADROES["generos"]` na v2 (a lista das Configurações virá depois). */
export const GENEROS_PADRAO = [
  "Alternative", "Ambient", "Axé", "Blues", "Bossa Nova", "Classical", "Country", "Dance",
  "Disco", "Drum & Bass", "Electronic", "Folk", "Forró", "Funk", "Gospel", "Hard Rock",
  "Heavy Metal", "Hip-Hop", "House", "Indie", "Indie Rock", "Jazz", "Lo-Fi", "Metal",
  "MPB", "Pagode", "Pop", "Pop Rock", "Punk", "R&B", "Rap", "Reggae", "Rock", "Samba",
  "Sertanejo", "Soul", "Soundtrack", "Synthpop", "Techno", "Trap",
];

/** Lista final: a padrão mais os gêneros dos arquivos carregados, sem repetir (sem diferenciar maiúsculas), em ordem. */
export function listaDeGeneros(base: readonly string[], dosArquivos: readonly string[]): string[] {
  const vistos = new Map<string, string>();
  for (const g of [...base, ...dosArquivos]) {
    const nome = g.trim();
    if (nome && !vistos.has(nome.toLocaleLowerCase())) vistos.set(nome.toLocaleLowerCase(), nome);
  }
  return [...vistos.values()].sort((a, b) => a.localeCompare(b, "pt-BR", { sensitivity: "base" }));
}
