# Kelly Telegram Bot

Bot de Telegram para interactuar con la API KellyBot.

## Requisitos

- Python 3.10+
- Token de Bot de Telegram
- Credenciales para la API KellyBot

## Configuración

1. Copiar `.env.sample` a `.env`:
   ```bash
   cp .env.sample .env
   ```
2. Editar `.env` con tus credenciales:
   ```
   TELEGRAM_BOT_TOKEN=tu_token_aqui
   API_URL=url_api_kellybot
   API_KEY=tu_api_key
   ```

## Instalación

1. Crear entorno virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```
2. Instalar dependencias:
   ```bash
   pip install -e .
   ```

## Uso

Ejecutar el bot:
```bash
python -m bot.main
```

## Estructura del Proyecto
```
kelly_telegram/
├── bot/               # Código fuente
│   ├── core/          # Configuración
│   ├── handlers/      # Manejadores de Telegram
│   └── services/      # Cliente API
└── persistence/       # Datos persistentes# kelly_telegram
