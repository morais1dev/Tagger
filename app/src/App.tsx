import { useEffect, useState } from "react";
import { TEMAS, TEMA_PADRAO } from "./temas";
import "./temas.css";
import "./estilo.css";

const CHAVE = "tagger.tema";

/** Tema salvo, se ainda existir; senão o padrão. O armazenamento pode estar indisponível. */
function temaInicial(): string {
  try {
    const salvo = localStorage.getItem(CHAVE);
    if (salvo && salvo in TEMAS) return salvo;
  } catch {
    /* sem armazenamento: usa o padrão */
  }
  return TEMA_PADRAO;
}

export default function App() {
  const [tema, setTema] = useState(temaInicial);

  useEffect(() => {
    document.documentElement.dataset.tema = tema;
    try {
      localStorage.setItem(CHAVE, tema);
    } catch {
      /* não persiste, mas o tema continua valendo nesta sessão */
    }
  }, [tema]);

  return (
    <main className="janela">
      <header className="barra">
        <label>
          Tema{" "}
          <select value={tema} onChange={(e) => setTema(e.target.value)}>
            <optgroup label="Escuros">
              {Object.entries(TEMAS).filter(([, t]) => t.escuro).map(([id, t]) => (
                <option key={id} value={id}>{t.nome}</option>
              ))}
            </optgroup>
            <optgroup label="Claros">
              {Object.entries(TEMAS).filter(([, t]) => !t.escuro).map(([id, t]) => (
                <option key={id} value={id}>{t.nome}</option>
              ))}
            </optgroup>
          </select>
        </label>
      </header>
    </main>
  );
}
