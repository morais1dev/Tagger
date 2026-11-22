// Nomes legíveis dos extras que a limpeza mostra (tagger/gui/limpeza.py da v2): frames ID3,
// chaves Vorbis (FLAC/Ogg), átomos MP4 e famílias com prefixo comum.

const NOMES_FRAMES: Record<string, string> = {
  PRIV: "dados privados de programas (Windows Media, Amazon...)",
  TXXX: "campos personalizados (inclui ReplayGain, MusicBrainz IDs...)",
  WXXX: "links",
  GEOB: "objetos embutidos",
  POPM: "avaliação (estrelas)",
  PCNT: "contagem de execuções",
  TENC: "codificado por",
  TSSE: "programa/configuração do encoder",
  TLEN: "duração gravada na tag",
  TCOP: "copyright",
  TPUB: "gravadora",
  TBPM: "BPM",
  TKEY: "tom",
  TSRC: "ISRC",
  TMED: "mídia de origem",
  TSOP: "artista para ordenação",
  TSOA: "álbum para ordenação",
  TSOT: "título para ordenação",
  TSO2: "artista do álbum para ordenação",
  TCMP: "compilação (iTunes)",
  RVA2: "ajuste de volume",
  MCDI: "identificador do CD",
  UFID: "identificador único (MusicBrainz...)",
};

const NOMES_VORBIS: Record<string, string> = {
  ENCODER: "programa/configuração do encoder",
  ENCODEDBY: "codificado por",
  "ENCODED-BY": "codificado por",
  ENCODING: "configuração do encoder",
  COPYRIGHT: "copyright",
  LABEL: "gravadora",
  ORGANIZATION: "gravadora",
  PUBLISHER: "gravadora",
  BPM: "BPM",
  KEY: "tom",
  INITIALKEY: "tom",
  ISRC: "ISRC",
  BARCODE: "código de barras",
  CATALOGNUMBER: "número de catálogo",
  MEDIA: "mídia de origem",
  SOURCEMEDIA: "mídia de origem",
  LENGTH: "duração gravada na tag",
  COMPILATION: "compilação",
  RATING: "avaliação (estrelas)",
  MOOD: "humor",
  GROUPING: "agrupamento",
  ARTISTSORT: "artista para ordenação",
  ALBUMSORT: "álbum para ordenação",
  TITLESORT: "título para ordenação",
  ALBUMARTISTSORT: "artista do álbum para ordenação",
  COMPOSERSORT: "compositor para ordenação",
  ORIGINALDATE: "data original de lançamento",
  ORIGINALYEAR: "ano original de lançamento",
  RELEASECOUNTRY: "país de lançamento",
  RELEASESTATUS: "situação do lançamento (MusicBrainz)",
  RELEASETYPE: "tipo de lançamento (MusicBrainz)",
  SCRIPT: "escrita (MusicBrainz)",
  WWW: "links",
  DISCID: "identificador do CD",
  CDDB: "identificador do CD",
};

const LOJA_ITUNES = "identificador da loja (iTunes)";
const NOMES_MP4: Record<string, string> = {
  "©too": "programa/configuração do encoder",
  "©enc": "codificado por",
  "©grp": "agrupamento",
  cprt: "copyright",
  desc: "descrição",
  ldes: "descrição longa",
  soar: "artista para ordenação",
  soal: "álbum para ordenação",
  sonm: "título para ordenação",
  soaa: "artista do álbum para ordenação",
  soco: "compositor para ordenação",
  purd: "data de compra (iTunes)",
  apID: "conta da loja (iTunes)",
  ownr: "dono (iTunes)",
  "xid ": LOJA_ITUNES,
  plID: LOJA_ITUNES,
  cnID: LOJA_ITUNES,
  geID: LOJA_ITUNES,
  atID: LOJA_ITUNES,
  sfID: LOJA_ITUNES,
  cmID: LOJA_ITUNES,
  akID: LOJA_ITUNES,
  iTunes_CDDB_IDs: "identificador do CD",
};

const PREFIXOS: Array<[string, string]> = [
  ["REPLAYGAIN_", "ajuste de volume (ReplayGain)"],
  ["MUSICBRAINZ_", "identificadores do MusicBrainz"],
  ["MUSICBRAINZ ", "identificadores do MusicBrainz"],
  ["ACOUSTID_", "identificadores do AcoustID"],
  ["ACOUSTID ", "identificadores do AcoustID"],
  ["DISCOGS_", "dados do Discogs"],
];

const PREFIXO_LIVRE_MP4 = "----:";

/** [chave curta para mostrar, descrição] de um frame ID3, chave Vorbis ou átomo MP4 extra. */
export function nomeExtra(chave: string): [string, string] {
  const curta = chave.startsWith(PREFIXO_LIVRE_MP4) ? chave.slice(chave.lastIndexOf(":") + 1) : chave;
  const maiuscula = curta.toUpperCase();
  const descricao =
    NOMES_FRAMES[curta] ?? NOMES_MP4[curta] ?? NOMES_VORBIS[maiuscula] ??
    PREFIXOS.find(([prefixo]) => maiuscula.startsWith(prefixo))?.[1];
  return [curta, descricao ?? "outro"];
}
