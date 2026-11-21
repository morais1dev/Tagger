import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

// Espelha nucleo::Tags (a capa chega como data URL, pronta para <img>).
type Tags = {
  formato: string;
  titulo: string;
  artista: string;
  faixa: string;
  gravadora: string;
  capa: string | null;
};

const CAMPOS = [
  ["titulo", "Título"],
  ["artista", "Artista"],
  ["faixa", "Faixa"],
  ["gravadora", "Gravadora"],
] as const;

type Campo = (typeof CAMPOS)[number][0];

export default function App() {
  const [arquivos, setArquivos] = useState<string[]>([]);
  const [atual, setAtual] = useState<string | null>(null);
  const [tags, setTags] = useState<Tags | null>(null);
  const [campo, setCampo] = useState<Campo>("titulo");
  const [valor, setValor] = useState("");
  const [aviso, setAviso] = useState("");

  async function gerar() {
    try {
      setArquivos(await invoke<string[]>("gerar_amostras"));
      setAviso("Amostras geradas numa pasta temporária.");
    } catch (e) {
      setAviso(`Erro: ${e}`);
    }
  }

  async function abrir(caminho: string) {
    try {
      const lidas = await invoke<Tags>("ler", { caminho });
      setAtual(caminho);
      setTags(lidas);
      setValor(lidas[campo]);
    } catch (e) {
      setAviso(`Erro ao ler: ${e}`);
    }
  }

  async function gravar() {
    if (!atual) return;
    try {
      await invoke("gravar", { caminho: atual, campo, valor });
      await abrir(atual); // relê do disco: o que aparece é o que ficou gravado
      setAviso("Gravado e relido do disco.");
    } catch (e) {
      setAviso(`Erro ao gravar: ${e}`);
    }
  }

  async function capaDeTeste() {
    if (!atual) return;
    try {
      await invoke("capa_de_teste", { caminho: atual });
      await abrir(atual);
      setAviso("Capa frontal trocada (as outras imagens ficam).");
    } catch (e) {
      setAviso(`Erro na capa: ${e}`);
    }
  }

  useEffect(() => {
    if (tags) setValor(tags[campo]);
  }, [campo]);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 16, maxWidth: 720 }}>
      <h1 style={{ fontSize: 20 }}>Tagger — spike Tauri + lofty</h1>
      <button onClick={gerar}>Gerar amostras (MP3, FLAC, M4A)</button>
      <ul>
        {arquivos.map((a) => (
          <li key={a}>
            <button onClick={() => abrir(a)} style={{ fontWeight: a === atual ? "bold" : "normal" }}>
              {a.split(/[\\/]/).pop()}
            </button>
          </li>
        ))}
      </ul>

      {tags && (
        <section style={{ display: "flex", gap: 16 }}>
          <div>
            {tags.capa ? (
              <img src={tags.capa} alt="Capa" width={160} height={160} style={{ objectFit: "cover" }} />
            ) : (
              <div style={{ width: 160, height: 160, border: "1px dashed #888" }}>sem capa</div>
            )}
            <div>
              <button onClick={capaDeTeste}>Capa de teste</button>
            </div>
          </div>
          <div>
            <p>Formato: {tags.formato.toUpperCase()}</p>
            <table>
              <tbody>
                {CAMPOS.map(([chave, rotulo]) => (
                  <tr key={chave}>
                    <th style={{ textAlign: "left", paddingRight: 8 }}>{rotulo}</th>
                    <td>{tags[chave] || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p>
              <select value={campo} onChange={(e) => setCampo(e.target.value as Campo)}>
                {CAMPOS.map(([chave, rotulo]) => (
                  <option key={chave} value={chave}>
                    {rotulo}
                  </option>
                ))}
              </select>{" "}
              <input value={valor} onChange={(e) => setValor(e.target.value)} placeholder="vazio remove" />{" "}
              <button onClick={gravar}>Gravar</button>
            </p>
          </div>
        </section>
      )}
      <p role="status">{aviso}</p>
    </main>
  );
}
