export class ShareManager {
    constructor() {
        this._PARAM = 'p';
        this._SCHEMA_VERSION = 1;
    }

    _encodeUtf8Base64(str) {
        const bytes = new TextEncoder().encode(str);
        let binary = '';
        for (const b of bytes) binary += String.fromCharCode(b);
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }

    _decodeUtf8Base64(encoded) {
        let b64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
        while (b64.length % 4) b64 += '=';
        const binary = atob(b64);
        const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
        return new TextDecoder().decode(bytes);
    }

    encode(state) {
        const payload = { v: this._SCHEMA_VERSION, ...state };
        return this._encodeUtf8Base64(JSON.stringify(payload));
    }

    decode(encoded) {
        try {
            const json = this._decodeUtf8Base64(encoded);
            const payload = JSON.parse(json);
            if (payload.v !== this._SCHEMA_VERSION)
                throw new Error(`Versión incompatible: ${payload.v}`);
            return payload;
        } catch (e) {
            throw new Error(`No se pudo decodificar el estado: ${e.message}`);
        }
    }

    share(state) {
        const encoded = this.encode(state);
        const url = `${location.origin}${location.pathname}?${this._PARAM}=${encoded}`;
        history.pushState(null, '', url);
        if (navigator.clipboard) navigator.clipboard.writeText(url);
        return url;
    }

    loadFromURL() {
        const params = new URLSearchParams(location.search);
        const encoded = params.get(this._PARAM);
        if (!encoded) return null;
        return this.decode(encoded);
    }
}
