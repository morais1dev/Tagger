import { Janela } from "./components/Janela";
import { ponteSimulada } from "./mock/ponteSimulada";
import "./temas.css";
import "./estilo.css";

// Por enquanto a ponte é a simulada; a real (invoke do Tauri) entra quando o core estiver pronto.
const ponte = ponteSimulada();

export default function App() {
  return <Janela ponte={ponte} />;
}
