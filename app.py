# ============================================
# isis-tts/app.py v1.0
# Microserviço TTS para Isis AI Agent
# Deploy: Render.com (free tier)
# Stack: Python + Flask + edge-tts
# Voz: pt-BR-FranciscaNeural (Microsoft Neural)
# ============================================

import os
import base64
import asyncio
import logging
import tempfile
from flask import Flask, request, jsonify
import edge_tts

# ── Configuração ──────────────────────────────
app     = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log     = logging.getLogger(__name__)

# Vozes disponíveis (fallback em ordem de preferência)
VOZES_PT_BR = [
    'pt-BR-FranciscaNeural',   # Feminina — voz principal da Isis
    'pt-BR-ThalitaNeural',     # Feminina alternativa
    'pt-BR-AntonioNeural',     # Masculina (fallback)
]

VOZ_PADRAO = os.environ.get('TTS_VOICE', 'pt-BR-FranciscaNeural')

# ── Gerar áudio com edge-tts ──────────────────
async def gerar_audio_async(texto: str, voz: str) -> bytes:
    """Gera áudio OGG a partir de texto usando edge-tts."""
    # edge-tts gera MP3 por padrão — salvamos em arquivo temp
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        communicate = edge_tts.Communicate(texto, voz)
        await communicate.save(tmp_path)

        with open(tmp_path, 'rb') as f:
            audio_bytes = f.read()

        log.info(f'Áudio gerado: {len(audio_bytes)} bytes | voz: {voz}')
        return audio_bytes

    finally:
        # Limpar arquivo temporário
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

def gerar_audio(texto: str, voz: str) -> bytes:
    """Wrapper síncrono para a função async."""
    return asyncio.run(gerar_audio_async(texto, voz))

# ── Rotas ─────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    """Health check — usado pelo Render e pelo Vercel para warm-up."""
    return jsonify({
        'status':  'ok',
        'service': 'isis-tts',
        'version': '1.0.0',
        'voz':     VOZ_PADRAO
    })

@app.route('/tts', methods=['POST'])
def tts():
    """
    Recebe texto, gera áudio MP3 com edge-tts,
    retorna base64 para o Vercel enviar via Evolution API.

    Body JSON:
        text  (str, obrigatório) — texto a ser sintetizado
        voice (str, opcional)   — voz a usar (padrão: pt-BR-FranciscaNeural)

    Response JSON:
        audio_base64 (str) — áudio MP3 em base64
        bytes        (int) — tamanho do áudio
        voice        (str) — voz usada
    """
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'error': 'Body JSON obrigatório'}), 400

        texto = data.get('text', '').strip()
        if not texto:
            return jsonify({'error': 'Campo "text" obrigatório e não pode ser vazio'}), 400

        # Limite de segurança — WhatsApp não suporta áudios muito longos
        if len(texto) > 1500:
            texto = texto[:1500] + '...'
            log.warning('Texto truncado para 1500 caracteres')

        voz = data.get('voice', VOZ_PADRAO)

        # Validar se a voz solicitada está na lista permitida
        if voz not in VOZES_PT_BR:
            log.warning(f'Voz "{voz}" não suportada, usando padrão')
            voz = VOZ_PADRAO

        log.info(f'TTS request: {len(texto)} chars | voz: {voz} | preview: {texto[:60]}')

        # Gerar áudio
        audio_bytes  = gerar_audio(texto, voz)
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        return jsonify({
            'audio_base64': audio_base64,
            'bytes':        len(audio_bytes),
            'voice':        voz
        })

    except Exception as e:
        log.error(f'Erro no TTS: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/voices', methods=['GET'])
def voices():
    """Lista as vozes disponíveis."""
    return jsonify({'voices': VOZES_PT_BR, 'default': VOZ_PADRAO})

# ── Inicialização ─────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    log.info(f'Isis TTS Service iniciando na porta {port}')
    app.run(host='0.0.0.0', port=port, debug=False)
