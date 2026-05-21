export async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();

  if (!text.trim()) {
    throw new Error(`HTTP ${response.status} ${response.statusText || 'sin mensaje'}: respuesta vacía`);
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`HTTP ${response.status} ${response.statusText || 'sin mensaje'}: respuesta no es JSON`);
  }
}
