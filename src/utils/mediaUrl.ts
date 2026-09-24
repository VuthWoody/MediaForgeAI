/**
 * Converts a local file path to a bulletproof media:// protocol streaming URL.
 * Uses base64url tokenization to guarantee that spaces, hashtags (#), emojis,
 * query parameters, and special characters never get mangled or truncated by
 * Chromium's URL parser.
 */
export function toMediaUrl(filePath: string): string {
  if (!filePath) return '';
  try {
    const bytes = new TextEncoder().encode(filePath);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const b64 = btoa(binary)
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
    return `media://play/${b64}`;
  } catch (err) {
    console.error('Failed to encode media path to URL:', err);
    return '';
  }
}
