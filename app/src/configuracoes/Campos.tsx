import { useEffect, useId, useState, type ReactNode } from "react";

/** Caixa de seleção com o texto ao lado. */
export function Opcao({ rotulo, marcado, aoMudar, dica }: {
  rotulo: string;
  marcado: boolean;
  aoMudar: (v: boolean) => void;
  dica?: string;
}) {
  return (
    <label className="cfg-opcao" title={dica}>
      <input type="checkbox" checked={marcado} onChange={(e) => aoMudar(e.target.checked)} />
      <span>{rotulo}</span>
    </label>
  );
}

export function Ajuda({ children }: { children: ReactNode }) {
  return <p className="cfg-ajuda">{children}</p>;
}

export function Secao({ children }: { children: ReactNode }) {
  return <h3 className="cfg-secao">{children}</h3>;
}

/** Linha "rótulo + controle" do formulário. */
export function Linha({ rotulo, para, children }: { rotulo: string; para?: string; children: ReactNode }) {
  return (
    <div className="cfg-linha">
      <label className="cfg-rotulo" htmlFor={para}>{rotulo}</label>
      <div className="cfg-controle">{children}</div>
    </div>
  );
}

/**
 * Campo numérico com limites: o que está fora do intervalo (ou não é número inteiro) mostra o erro
 * e NÃO chega à configuração. Devolve o valor só quando é válido.
 */
export function CampoNumero({ rotulo, valor, min, max, passo = 1, sufixo, desabilitado, aoMudar }: {
  rotulo: string;
  valor: number;
  min: number;
  max: number;
  passo?: number;
  sufixo?: string;
  desabilitado?: boolean;
  aoMudar: (n: number) => void;
}) {
  const id = useId();
  const [texto, setTexto] = useState(String(valor));
  const n = Number(texto);
  const valido = texto.trim() !== "" && Number.isInteger(n) && n >= min && n <= max;

  useEffect(() => {
    // o valor mudou por fora (Restaurar padrões, importação): o campo acompanha
    setTexto((atual) => (Number(atual) === valor ? atual : String(valor)));
  }, [valor]);

  return (
    <div className="cfg-numero">
      <input
        id={id}
        type="number"
        aria-label={rotulo}
        aria-invalid={!valido}
        aria-describedby={valido ? undefined : `${id}-erro`}
        min={min}
        max={max}
        step={passo}
        value={texto}
        disabled={desabilitado}
        onChange={(e) => {
          setTexto(e.target.value);
          const novo = Number(e.target.value);
          if (e.target.value.trim() !== "" && Number.isInteger(novo) && novo >= min && novo <= max) aoMudar(novo);
        }}
      />
      {sufixo && <span className="cfg-sufixo">{sufixo}</span>}
      {!valido && !desabilitado && (
        <span id={`${id}-erro`} role="alert" className="cfg-erro">
          Use um valor de {min} a {max}.
        </span>
      )}
    </div>
  );
}
