// Gerado por app/scripts/gerar_temas.py a partir de tagger/gui/tema.py. Não edite à mão.

export interface Tema {
  nome: string;
  escuro: boolean;
  cores: Record<string, string>;
}

export const TEMAS: Record<string, Tema> = {
  "grafite": { nome: "Grafite", escuro: true, cores: {"bg": "#0f1012", "surface": "#16171a", "surface2": "#1c1e22", "field": "#111214", "line": "#25282d", "line2": "#33373d", "text": "#e8e9eb", "muted": "#9ba0a8", "faint": "#5d626b", "hover": "#1f2125", "erro": "#ff6b6b", "acento": "#3ddc97"} },
  "meia-noite": { nome: "Meia-noite", escuro: true, cores: {"bg": "#0b1020", "surface": "#11182b", "surface2": "#172036", "field": "#0d1426", "line": "#1f2a44", "line2": "#2b3858", "text": "#e6eaf3", "muted": "#98a3bb", "faint": "#56617a", "hover": "#1a2440", "erro": "#ff6b6b", "acento": "#6b9bff"} },
  "alto-contraste": { nome: "Alto contraste", escuro: true, cores: {"bg": "#000000", "surface": "#0a0a0a", "surface2": "#141414", "field": "#000000", "line": "#3a3a3a", "line2": "#5c5c5c", "text": "#ffffff", "muted": "#cfcfcf", "faint": "#8a8a8a", "hover": "#1c1c1c", "erro": "#ff5c5c", "acento": "#f5c542"} },
  "dracula": { nome: "Dracula", escuro: true, cores: {"bg": "#21222c", "surface": "#282a36", "surface2": "#343746", "field": "#21222c", "line": "#383a4a", "line2": "#44475a", "text": "#f8f8f2", "muted": "#a6accd", "faint": "#6272a4", "hover": "#313343", "erro": "#ff5555", "acento": "#bd93f9"} },
  "nord": { nome: "Nord", escuro: true, cores: {"bg": "#272c36", "surface": "#2e3440", "surface2": "#3b4252", "field": "#292e39", "line": "#3b4252", "line2": "#4c566a", "text": "#eceff4", "muted": "#b0b8c8", "faint": "#616e88", "hover": "#353c4a", "erro": "#bf616a", "acento": "#88c0d0"} },
  "gruvbox-dark": { nome: "Gruvbox Dark", escuro: true, cores: {"bg": "#1d2021", "surface": "#282828", "surface2": "#32302f", "field": "#1d2021", "line": "#3c3836", "line2": "#504945", "text": "#ebdbb2", "muted": "#a89984", "faint": "#665c54", "hover": "#2f2d2c", "erro": "#fb4934", "acento": "#fe8019"} },
  "catppuccin-mocha": { nome: "Catppuccin Mocha", escuro: true, cores: {"bg": "#181825", "surface": "#1e1e2e", "surface2": "#313244", "field": "#181825", "line": "#2a2b3c", "line2": "#45475a", "text": "#cdd6f4", "muted": "#a6adc8", "faint": "#6c7086", "hover": "#262637", "erro": "#f38ba8", "acento": "#cba6f7"} },
  "tokyo-night": { nome: "Tokyo Night", escuro: true, cores: {"bg": "#16161e", "surface": "#1a1b26", "surface2": "#24283b", "field": "#16161e", "line": "#232433", "line2": "#2f3549", "text": "#c0caf5", "muted": "#a9b1d6", "faint": "#565f89", "hover": "#202231", "erro": "#f7768e", "acento": "#7aa2f7"} },
  "one-dark": { nome: "One Dark", escuro: true, cores: {"bg": "#21252b", "surface": "#282c34", "surface2": "#2c313a", "field": "#21252b", "line": "#323842", "line2": "#3e4451", "text": "#d7dae0", "muted": "#9da5b4", "faint": "#5c6370", "hover": "#2a2f37", "erro": "#e06c75", "acento": "#61afef"} },
  "solarized-dark": { nome: "Solarized Dark", escuro: true, cores: {"bg": "#00212b", "surface": "#002b36", "surface2": "#073642", "field": "#00252f", "line": "#0a3a47", "line2": "#14505e", "text": "#eee8d5", "muted": "#93a1a1", "faint": "#586e75", "hover": "#04313d", "erro": "#dc322f", "acento": "#268bd2"} },
  "monokai": { nome: "Monokai", escuro: true, cores: {"bg": "#1e1f1c", "surface": "#272822", "surface2": "#31322c", "field": "#1e1f1c", "line": "#34352f", "line2": "#49483e", "text": "#f8f8f2", "muted": "#b4b2a2", "faint": "#75715e", "hover": "#2e2f29", "erro": "#f92672", "acento": "#a6e22e"} },
  "github-dark": { nome: "GitHub Dark", escuro: true, cores: {"bg": "#010409", "surface": "#0d1117", "surface2": "#161b22", "field": "#0d1117", "line": "#21262d", "line2": "#30363d", "text": "#e6edf3", "muted": "#9198a1", "faint": "#484f58", "hover": "#131820", "erro": "#f85149", "acento": "#4493f8"} },
  "rose-pine": { nome: "Rosé Pine", escuro: true, cores: {"bg": "#191724", "surface": "#1f1d2e", "surface2": "#26233a", "field": "#191724", "line": "#2a273f", "line2": "#403d52", "text": "#e0def4", "muted": "#908caa", "faint": "#6e6a86", "hover": "#21202e", "erro": "#eb6f92", "acento": "#c4a7e7"} },
  "claro": { nome: "Claro", escuro: false, cores: {"bg": "#eceef1", "surface": "#ffffff", "surface2": "#f5f6f8", "field": "#ffffff", "line": "#e2e5e9", "line2": "#cfd4da", "text": "#14161a", "muted": "#59606a", "faint": "#a3a9b1", "hover": "#f1f3f5", "erro": "#d93838", "acento": "#3ddc97"} },
  "sepia": { nome: "Sépia", escuro: false, cores: {"bg": "#ece4d6", "surface": "#faf6ef", "surface2": "#f3ece0", "field": "#fffdf8", "line": "#e2d8c6", "line2": "#d2c5ae", "text": "#2b2419", "muted": "#685d4c", "faint": "#a89c88", "hover": "#f0e8da", "erro": "#c0392b", "acento": "#c47a3a"} },
  "catppuccin-latte": { nome: "Catppuccin Latte", escuro: false, cores: {"bg": "#e6e9ef", "surface": "#eff1f5", "surface2": "#e6e9ef", "field": "#f7f8fa", "line": "#dce0e8", "line2": "#ccd0da", "text": "#4c4f69", "muted": "#5c5f77", "faint": "#9ca0b0", "hover": "#e9ecf1", "erro": "#d20f39", "acento": "#8839ef"} },
  "gruvbox-light": { nome: "Gruvbox Light", escuro: false, cores: {"bg": "#f2e5bc", "surface": "#fbf1c7", "surface2": "#f2e5bc", "field": "#f9f5d7", "line": "#e5d5ad", "line2": "#d5c4a1", "text": "#3c3836", "muted": "#665c54", "faint": "#a89984", "hover": "#f5ead0", "erro": "#9d0006", "acento": "#af3a03"} },
  "solarized-light": { nome: "Solarized Light", escuro: false, cores: {"bg": "#eee8d5", "surface": "#fdf6e3", "surface2": "#f5efdc", "field": "#fffbf0", "line": "#e8e1cc", "line2": "#d9d2bd", "text": "#073642", "muted": "#4f656c", "faint": "#93a1a1", "hover": "#f7f0dd", "erro": "#dc322f", "acento": "#268bd2"} },
  "github-light": { nome: "GitHub Light", escuro: false, cores: {"bg": "#f6f8fa", "surface": "#ffffff", "surface2": "#f6f8fa", "field": "#ffffff", "line": "#d8dee4", "line2": "#d0d7de", "text": "#1f2328", "muted": "#59636e", "faint": "#8c959f", "hover": "#f3f5f7", "erro": "#d1242f", "acento": "#0969da"} },
  "rose-pine-dawn": { nome: "Rosé Pine Dawn", escuro: false, cores: {"bg": "#faf4ed", "surface": "#fffaf3", "surface2": "#f2e9e1", "field": "#fffaf3", "line": "#e9e1da", "line2": "#dfdad9", "text": "#575279", "muted": "#625e7a", "faint": "#9893a5", "hover": "#f4ede8", "erro": "#b4637a", "acento": "#286983"} },
};

export const TEMA_PADRAO = "grafite";
