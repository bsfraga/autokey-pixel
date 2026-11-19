## Download

| Arquivo | Para quê |
|---|---|
| **`AutoKeyPixel.exe`** | Executável direto — baixe e rode, não precisa instalar. |
| **`AutoKeyPixel-v*-windows.zip`** | O mesmo `.exe` compactado (útil quando o navegador/antivírus bloqueia o download de `.exe`). |

## Funcionalidades
- Captura de pixel por hotkey global (padrão `Ctrl+Shift+C`): X, Y, RGB, HEX, amostra e histórico
- Tecla repetida via SendInput — scan code (jogos) ou virtual key
- Intervalo (100 ms), tempo pressionada (50 ms) e jitter (±15 / ±10 ms), distribuição uniforme ou gaussiana
- `F6` iniciar/parar, `F12` parada de emergência, limite de repetições opcional
- Perfis em JSON, "sempre no topo", reinício como administrador

## Observações
- Antivírus podem acusar falso positivo em executáveis PyInstaller que usam hook de teclado.
- Se o programa alvo roda como administrador, use **Reiniciar como admin**.
