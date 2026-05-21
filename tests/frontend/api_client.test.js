import { describe, it, expect, vi, afterEach } from 'vitest';

import { fetchJSON } from '../../frontend/features/api_client.js';

describe('frontend api client', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('parses valid JSON responses', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      status: 200,
      statusText: 'OK',
      text: () => Promise.resolve('{"ok":true}'),
    });

    await expect(fetchJSON('/api/check')).resolves.toEqual({ ok: true });
  });

  it('reports empty HTTP responses with status instead of JSON parse noise', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      status: 403,
      statusText: 'Forbidden',
      text: () => Promise.resolve(''),
    });

    await expect(fetchJSON('/api/check')).rejects.toThrow('HTTP 403 Forbidden: respuesta vacía');
  });

  it('reports non-JSON HTTP responses with status', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      status: 500,
      statusText: 'Internal Server Error',
      text: () => Promise.resolve('<html>boom</html>'),
    });

    await expect(fetchJSON('/api/check')).rejects.toThrow(
      'HTTP 500 Internal Server Error: respuesta no es JSON',
    );
  });
});
