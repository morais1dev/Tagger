//! Ponte entre a interface (React) e o `tagger-core`. Por enquanto só abre a janela.

pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("erro ao iniciar o Tagger");
}
