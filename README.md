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
│   ├── timeline_mapper.py   # Âncoras + buffers + fallback + fusão com CV
│   ├── video_detector.py    # CV local 144p: detector 1:39, scan_timeline, thumbnails
│   ├── templates/timer_139_144p.png  # Template do timer para matchTemplate
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
- `--anchors`: Mapeamento por mapa, ex: `"1=192,2=3926"` (sobrescreve `--anchor`).
- `--pre-buffer`: Segundos de buy phase antes do início (padrão: `8`). Aplicado ao `start` do CV/fallback, exceto overrides explícitos.
- `--post-buffer`: Segundos de reação pós-round (padrão: `5`). Aplicado ao `end` do CV/fallback, exceto overrides explícitos.
- `--gap`: Gap usado na estimativa fallback quando o CV falha (padrão: `35`).
- `--output`: Caminho do arquivo JSON gerado (padrão: `timestamps.json`).
- `--format`: Formato de saída (`full` com metadados ou `flat` com array simples).
- `--no-cv`: Desabilita detecção 144p via `yt-dlp`+OpenCV e usa só estimativa por âncora/duração VLR.

Prioridade por round: `round_overrides {"1-1": {"start","end"}}` > detecção CV 1:39 > estimativa fallback (`estimated: true`).

---

## 📋 Especificação do `timestamps.json`

O arquivo estruturado gerado segue a especificação:

> `timestamps.json` está no `.gitignore` (exceto o exemplo commitado `LOUD vs MIBR`). Para versionar um exemplo, copie para `timestamps.example.json`.

```json
{
  "video_id": "B5G9Qpv31_o",
  "video_url": "https://www.youtube.com/watch?v=B5G9Qpv31_o",
  "vlr_url": "https://www.vlr.gg/734312/loud-vs-mibr-vct-2026-americas-stage-2-lr2",
  "match_info": {
    "event": "VCT 2026: Americas Stage 2 Playoffs",
    "team1": {"name": "LOUD", "logo": "https://..."},
    "team2": {"name": "MIBR", "logo": "https://..."},
    "score": "2 : 0"
  },
  "settings": {
    "pre_buffer_seconds": 8,
    "post_buffer_seconds": 5,
    "anchors": {"1": 193, "2": 3926}
  },
  "summary": {
    "total_maps": 2,
    "total_rounds": 46,
    "total_clean_duration_seconds": 3428,
    "total_clean_duration_formatted": "57:08"
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

## 🔌 API REST (FastAPI)

| Método | Rota | Corpo | Retorno |
|---|---|---|---|
| GET | `/api/status` | — | `{status, has_timestamps_file}` |
| GET | `/api/timestamps` | — | `timestamps.json` completo |
| POST | `/api/process` | `{vlr_url, youtube_url, anchor_seconds, anchors, round_overrides, pre_buffer_seconds, post_buffer_seconds, auto_detect_cv}` | `{success, data}` + salva `timestamps.json` |
| POST | `/api/save` | `{data}` | Salva calibração do Producer Mode |
| POST | `/api/scan_storyboards` | `{youtube_url, start_seconds, end_seconds}` | `{intervals: [{round,start,end}]}` via vídeo local 144p |
| POST | `/api/thumbnails` | `{youtube_url, start_seconds, end_seconds, step_seconds}` | `{thumbnails: [{time, formatted, thumbnail base64, is_start_candidate, is_end_candidate}]}` |

## 🤖 Detecção CV local 144p

- Baixa `bestvideo[height<=144]` via `yt-dlp` para `temp_cv_{id}.mp4` (reusa `temp_inspect.mp4` se existir; `KEEP_TEMP_VIDEO=1` impede limpeza).
- `detect_round_starts`: procura `1:39` em `gray[0:14,120:136]` com `matchTemplate + contraste do ":"`, agrupa clusters (`gap<=10s`, `count>=8`, `span>=8s`, `gap>=65s`), fim por `is_hud_active()`.
- Limitações: depende de `yt-dlp`+`ffmpeg` e do template `backend/templates/timer_139_144p.png`; VODs privados/restritos falham → cai no fallback estimado; overlay do broadcast fora do padrão 144p reduz precisão.
- Atalho sem rede: `generate_timestamps.py --no-cv` ou `auto_detect_cv=false`.

## 🧪 Executando os Testes Automatizados

Unitários herméticos (sem rede, sem sobrescrever `timestamps.json` real):

```bash
python -m pytest -v tests/test_all.py
```

Com rede (VLR.gg real):

```bash
RUN_NETWORK_TESTS=1 python -m pytest -v tests/test_all.py
```
