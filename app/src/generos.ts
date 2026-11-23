/** Gêneros sugeridos ao digitar: os mesmos de `config.PADROES["generos"]` na v2 (a lista das Configurações virá depois). */
export const GENEROS_PADRAO = [
  "Alternative", "Ambient", "Axé", "Blues", "Bossa Nova", "Classical", "Country", "Dance",
  "Disco", "Drum & Bass", "Electronic", "Folk", "Forró", "Funk", "Gospel", "Hard Rock",
  "Heavy Metal", "Hip-Hop", "House", "Indie", "Indie Rock", "Jazz", "Lo-Fi", "Metal",
  "MPB", "Pagode", "Pop", "Pop Rock", "Punk", "R&B", "Rap", "Reggae", "Rock", "Samba",
  "Sertanejo", "Soul", "Soundtrack", "Synthpop", "Techno", "Trap",
];

/**
 * Lista final do autocompletar, como `PainelEditor.definir_generos` da v2: a das Configurações mais os gêneros dos
 * arquivos, sem repetir (só repetições idênticas saem, como o `set` da v2) e em ordem sem diferenciar maiúsculas.
 */
export function listaDeGeneros(base: readonly string[], dosArquivos: readonly string[]): string[] {
  const unicos = [...new Set([...base, ...dosArquivos].filter((g) => g.trim() !== ""))];
  return unicos.sort((a, b) => a.toLocaleLowerCase().localeCompare(b.toLocaleLowerCase(), "pt-BR"));
}

/** Sugestões para o que foi digitado: quem contém o trecho, sem diferenciar maiúsculas (QCompleter MatchContains). */
export function filtrarGeneros(lista: readonly string[], digitado: string, limite = 50): string[] {
  const trecho = digitado.trim().toLocaleLowerCase();
  if (!trecho) return [];
  return lista.filter((g) => g.toLocaleLowerCase().includes(trecho)).slice(0, limite);
}
