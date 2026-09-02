# 🎮 Auto-Stream Valorant Clean Player (VOD Stream Cleaner)

Aplicação modular (Backend em Python e Frontend em HTML5/JS/CSS) desenvolvida para processar transmissões e VODs oficiais de campeonatos de **VALORANT** no YouTube e exibi-los em um **Player Contínuo Inteligente**, eliminando automaticamente:
- 🚫 Pausas táticas e técnicas
- 🚫 Intervalos comerciais
- 🚫 Telas de contagem regressiva e espera
- 🚫 Intervalos de intervalo/analyst desk entre mapas

Mantendo **exclusivamente as rodadas ativas de jogo**, sincronizadas com as estatísticas oficiais do **VLR.gg**.

---

## 📸 Funcionalidades

- ⚡ **Player Contínuo com YouTube IFrame API:** Ao atingir o tempo final de um round, o player salta instantaneamente via `player.seekTo()` para o início do round seguinte, proporcionando uma experiência de jogo pura e sem interrupções.
- 🎯 **Scraping Completo do VLR.gg:** Extrai automaticamente metadados da partida, times, placar, mapas jogados, duração oficial e detalhes de cada round (vencedor, lado atacante/defensor, método de vitória: eliminação, defuse, detonação do spike ou tempo).
- 📍 **Ponto de Ancoragem Calibrado:** Sincronização temporal flexível por ponto de ancoragem inicial ou por mapa, com buffers configuráveis de fase de compra (buy phase) e comemoração pós-round.
- 🛠️ **Producer Calibration Mode (Calibração Fina em Tempo Real):** Interface no próprio player para ajustar offsets com precisão de segundos (`📍 Usar Atual`, `+5s`, `-5s`, deslocamento de mapa inteiro) e salvar diretamente no arquivo JSON com 1 clique.
- 📊 **Timeline Visual Segmentada:** Barra de progresso multi-segmento que colore cada round com a cor do time vencedor e exibe detalhes ao passar o mouse.
- ⌨️ **Controles e Atalhos de Teclado:** Controle de velocidade (`0.75x` até `2x`), navegação por rounds (`[` e `]`), toggle de auto-skip (`S`), repetição de round (`R`) e tela cheia (`F`).

---

## 📁 Estrutura do Projeto

```
vplayer/
├── backend/
│   ├── __init__.py
│   ├── vlr_scraper.py       # Extração de estatísticas e rounds do VLR.gg
│   ├── timeline_mapper.py   # Algoritmo de mapeamento temporal e cálculo de intervalos
│   └── exporter.py          # Serialização e validação de timestamps.json
├── static/
│   ├── index.html           # SPA responsiva e cinematográfica (tema Valorant)
│   ├── style.css            # Estilos escuros, HUD de placar e timeline
│   └── app.js               # Integração com YouTube API e engine de salto contínuo
├── tests/
│   └── test_all.py          # Testes unitários automatizados
├── app.py                   # Servidor FastAPI com API REST e static files
├── generate_timestamps.py   # Interface de Linha de Comando (CLI) independente
├── timestamps.json          # Matriz de intervalos limpos gerada
├── requirements.txt         # Dependências do projeto
└── README.md                # Documentação completa
```

---

## 🚀 Instalação & Pré-requisitos

1. Certifique-se de possuir o Python 3.10+ instalado.
2. Instale as dependências:

```bash
pip install -r requirements.txt
```

---

## 💻 Como Usar

### Opção 1: Executar o Web Player Completo (Recomendado)

Inicie o servidor local FastAPI:

```bash
python app.py
```

Abra o navegador em: **`http://localhost:8000`**

Na interface você pode:
- Assistir diretamente à partida já sincronizada (ex: *LOUD vs MIBR*).
- Clicar em **"⚙️ Nova Partida"** para inserir qualquer URL do YouTube + VLR.gg e sincronizar instantaneamente.
- Ativar/desativar o **Auto-Skip de Pausas**.
- Ajustar os tempos no painel de **Calibração**.

---

### Opção 2: Gerar `timestamps.json` via Linha de Comando (CLI)

O script `generate_timestamps.py` funciona de forma totalmente independente:

```bash
python generate_timestamps.py \
  --vlr "https://www.vlr.gg/734312/loud-vs-mibr-vct-2026-americas-stage-2-lr2" \
  --yt "https://www.youtube.com/watch?v=B5G9Qpv31_o" \
  --anchor 192 \
  --output timestamps.json
```

#### Parâmetros do CLI:
- `--vlr`: URL ou ID da partida no VLR.gg.
- `--yt`: URL da transmissão oficial no YouTube ou ID de 11 caracteres.
- `--anchor`: Ponto de ancoragem inicial do Round 1 do Mapa 1 em segundos ou `MM:SS` (ex: `192` ou `03:12`).
- `--anchors`: Mapeamento por mapa, ex: `"1=192,2=4250"`.
- `--pre-buffer`: Segundos de buy phase antes do início (padrão: `8s`).
- `--post-buffer`: Segundos de reação pós-round (padrão: `5s`).
- `--output`: Caminho do arquivo JSON gerado (padrão: `timestamps.json`).
- `--format`: Formato de saída (`full` com metadados ou `flat` com array simples).

---

## 📋 Especificação do `timestamps.json`

O arquivo estruturado gerado segue a especificação:

```json
{
  "video_id": "B5G9Qpv31_o",
  "video_url": "https://www.youtube.com/watch?v=B5G9Qpv31_o",
  "vlr_url": "https://www.vlr.gg/734312/loud-vs-mibr-vct-2026-americas-stage-2-lr2",
  "match_info": {
    "event": "VCT 2026: Americas Stage 2 Playoffs",
    "team1": {"name": "LOUD"},
    "team2": {"name": "MIBR"},
    "score": "2 - 0"
  },
  "summary": {
    "total_maps": 2,
    "total_rounds": 48,
    "total_clean_duration_formatted": "73:24"
  },
  "timeline": [
    {
      "map": 1,
      "round": 1,
      "start": 192,
      "end": 277,
      "winner": "LOUD",
      "win_type": "elim",
      "score": "1 - 0"
    },
    {
      "map": 1,
      "round": 2,
      "start": 312,
      "end": 397,
      "winner": "LOUD",
      "win_type": "elim",
      "score": "2 - 0"
    }
  ]
}
```

---

## ⌨️ Atalhos do Teclado no Player

| Tecla | Ação |
|---|---|
| <kbd>Espaço</kbd> ou <kbd>K</kbd> | Play / Pause |
| <kbd>]</kbd> ou <kbd>L</kbd> | Próximo Round |
| <kbd>[</kbd> ou <kbd>J</kbd> | Round Anterior |
| <kbd>R</kbd> | Repetir Round Atual |
| <kbd>S</kbd> | Ativar / Desativar Auto-Skip de Pausas |
| <kbd>C</kbd> | Abrir / Fechar Painel de Calibração |
| <kbd>F</kbd> | Alternar Tela Cheia |
| <kbd>←</kbd> / <kbd>→</kbd> | Voltar / Avançar 5 segundos |

---

## 🧪 Executando os Testes Automatizados

Para rodar a suíte de testes com validação do scraper, gerador de timeline e API:

```bash
python -m pytest -v tests/test_all.py
```
