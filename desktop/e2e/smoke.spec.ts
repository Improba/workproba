describe('Workproba desktop — smoke', () => {
  it('affiche le shell desktop et le badge sidecar', async () => {
    // La webview Tauri se charge sur tauri://localhost ; le routeur redirige
    // vers /home qui monte WorkprobaLayout (sidebar + badge sidecar).
    await browser.url('tauri://localhost/home');

    const statusText = $('.wp-sidebar__status-text');
    await statusText.waitForDisplayed({ timeout: 20000 });

    // Sans sidecar lancé, le badge passe à « Sidecar injoignable ».
    // Avec `make dev-ai`, il passe à « Sidecar connecté ».
    const label = await statusText.getText();
    const acceptable = ['Sidecar connecté', 'Sidecar injoignable', 'Aucun workspace', 'Prêt'];
    if (!acceptable.includes(label)) {
      throw new Error(`badge sidecar inattendu : "${label}"`);
    }
  });
});
