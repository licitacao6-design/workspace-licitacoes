import os
import json
from flask import Flask, request, jsonify, send_from_directory
import google.generativeai as genai

app = Flask(__name__, static_folder='.')

# Sua chave de API configurada
GEMINI_API_KEY = "AQ.Ab8RN6IDTHrDNZhB1EnoZ32jp5eWuA2aAxmjWKwWy2u5GpqWMA"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

HISTORICO_FILE = "historico_editais.json"

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_historico(historico):
    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=4)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/processar', methods=['POST'])
def processar_licitacao():
    data = request.json
    texto_bruto = data.get('texto', '')
    if not texto_bruto:
        return jsonify({'error': 'Texto bruto não fornecido'}), 400
    try:
        model = genai.GenerativeModel('gemini-3.6-flash')
        prompt = (
            "Analise o texto da licitação abaixo e retorne estritamente um JSON válido "
            "(sem blocos de código markdown ou texto adicional) contendo exatamente duas chaves:\n"
            "1. \"item\": string com a identificação limpa do item ou lote.\n"
            "2. \"fornecedores\": array de objetos contendo: posicao, fornecedor (sem portes ME/EPP e UFs), "
            "cnpj, marca, lance, situacao.\n\n"
            f"Texto da licitação:\n{texto_bruto}"
        )
        response = model.generate_content(prompt)
        raw_text = response.text.replace('```json', '').replace('```', '').strip()
        return jsonify(json.loads(raw_text))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analisar-edital-pdf', methods=['POST'])
def analisar_edital_pdf():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo PDF enviado'}), 400
    
    file = request.files['pdf_file']
    if file.filename == '':
        return jsonify({'error': 'Nome do arquivo inválido'}), 400

    try:
        pdf_bytes = file.read()
        model = genai.GenerativeModel('gemini-3.6-flash')
        
        prompt = (
            "Analise o documento PDF do edital de licitação em anexo e extraia estritamente um JSON válido "
            "(sem blocos de código markdown ou texto adicional) contendo exatamente as seguintes chaves:\n"
            "1. \"numero_processo\": string com o número identificador do processo ou pregão (ex: 'PE 90062/2025').\n"
            "2. \"pregao_portal\": string informando o número do pregão e o portal (ex: 'PE 90062/2025 PORTAL COMPRASNET').\n"
            "3. \"orgao\": string com o órgão solicitante.\n"
            "4. \"valor_unitario\": string informando o valor estimado unitário (ou 'NÃO DISPONIBILIZADO').\n"
            "5. \"prazo_entrega\": string com o prazo de entrega do objeto.\n"
            "6. \"data_disputa\": string com a data e horário exatos da disputa de lances / sessão pública (ex: '15/10/2026 às 10:00').\n"
            "7. \"data_impugnacao\": string com a data limite de impugnação.\n"
            "8. \"data_esclarecimento\": string com a data limite de pedidos de esclarecimento.\n"
            "9. \"data_sessao\": string com a data e horário da sessão pública.\n"
            "10. \"registro_preco\": string informando se gera registro de preço e o prazo (ex: 'SIM - PRAZO 12 MESES' ou 'NÃO').\n"
            "11. \"gera_adesao\": string informando sobre possibilidade de adesão (Carona).\n"
            "12. \"seguro_garantia\": string informando se precisa de seguro garantia de proposta ou não."
        )

        response = model.generate_content([
            {'mime_type': 'application/pdf', 'data': pdf_bytes},
            prompt
        ])
        
        raw_text = response.text.replace('```json', '').replace('```', '').strip()
        analise_json = json.loads(raw_text)

        historico = carregar_historico()
        processo_id = analise_json.get("numero_processo", "PROCESSO SEM NUMERO")
        
        registro = {
            "id": processo_id,
            "filename": file.filename,
            "dados": analise_json
        }
        
        historico = [h for h in historico if h["id"] != processo_id]
        historico.insert(0, registro)
        salvar_historico(historico)

        return jsonify({"analise": analise_json, "historico": historico})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/historico-editais', methods=['GET'])
def get_historico():
    return jsonify(carregar_historico())

@app.route('/api/excluir-editais', methods=['POST'])
def excluir_editais():
    try:
        data = request.json or {}
        ids_para_excluir = set(str(i) for i in data.get('ids', []))
        
        historico = carregar_historico()
        historico_atualizado = [h for h in historico if str(h.get("id")) not in ids_para_excluir]
        salvar_historico(historico_atualizado)
        
        return jsonify({"success": True, "historico": historico_atualizado})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)