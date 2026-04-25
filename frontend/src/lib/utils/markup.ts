/**
 * Converts BBCode-style markup tags used in game content to safe HTML.
 * HTML entities are escaped first to prevent XSS, then supported tags are
 * applied. Unrecognized BBCode tags are stripped.
 *
 * Supported tags: [bold]/[b], [italic]/[i], [underline]/[u], [strike]/[s]
 */
export function renderMarkup(text: string): string {
  // Escape HTML entities before any substitution to prevent XSS.
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

  return (
    escaped
      .replace(/\[bold](.*?)\[\/bold]/gs, "<strong>$1</strong>")
      .replace(/\[b](.*?)\[\/b]/gs, "<strong>$1</strong>")
      .replace(/\[italic](.*?)\[\/italic]/gs, "<em>$1</em>")
      .replace(/\[i](.*?)\[\/i]/gs, "<em>$1</em>")
      .replace(/\[underline](.*?)\[\/underline]/gs, "<u>$1</u>")
      .replace(/\[u](.*?)\[\/u]/gs, "<u>$1</u>")
      .replace(/\[strike](.*?)\[\/strike]/gs, "<s>$1</s>")
      .replace(/\[s](.*?)\[\/s]/gs, "<s>$1</s>")
      // Strip any remaining unrecognized BBCode tags (e.g. color tags).
      .replace(/\[\/?\w[^\]]*]/g, "")
  );
}
