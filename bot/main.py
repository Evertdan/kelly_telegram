# bot/main.py
# -*- coding: utf-8 -*-

"""
Punto de entrada principal para el Bot de Telegram KellyBot.

Inicializa la aplicación, carga la configuración, registra los manejadores (handlers)
y pone en marcha el bot usando polling.
"""

import logging
import sys
from pathlib import Path
from typing import Optional # Para el tipo de persistencia

# Añadir el directorio raíz del bot al path (si es necesario, depende de cómo se ejecute)
# project_root = Path(__file__).parent.parent.resolve()
# if str(project_root) not in sys.path:
#     sys.path.insert(0, str(project_root))

# Importar configuración
try:
    from bot.core.config import settings
    CONFIG_LOADED = True
except ImportError:
    print("[ERROR CRÍTICO main.py bot] No se pudo importar 'settings' desde 'bot.core.config'.")
    print("Verifica la estructura de carpetas y archivos __init__.py.")
    CONFIG_LOADED = False
    # Salir si no podemos cargar la configuración esencial
    sys.exit("Fallo crítico al cargar configuración del bot.")
except Exception as config_err:
    print(f"[ERROR CRÍTICO main.py bot] Error validando settings: {config_err}")
    CONFIG_LOADED = False
    sys.exit("Fallo crítico validando configuración del bot.")

# Importar manejadores (handlers)
# Asegúrate de que estos archivos existan en bot/handlers/
try:
    from bot.handlers import commands, messages #, errors # Descomentar errors si lo creas
    HANDLERS_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR main.py bot] No se pudieron importar los handlers: {e}")
    HANDLERS_AVAILABLE = False
    # Podríamos continuar sin handlers, pero el bot no haría nada. Mejor salir.
    sys.exit("Fallo crítico al importar handlers.")

# Importar tipos y clases de PTB (python-telegram-bot)
try:
    from telegram.ext import (
        Application,
        ApplicationBuilder,
        CommandHandler,
        MessageHandler,
        PicklePersistence,
        filters,
        PersistenceInput, # Para type hint
        CallbackQueryHandler # Ejemplo para futuro
        # InlineQueryHandler # Ejemplo para futuro
    )
    from telegram.constants import ParseMode # Para formato de mensajes
    PTB_AVAILABLE = True
except ImportError:
    print("[ERROR CRÍTICO main.py bot] 'python-telegram-bot' no instalado.")
    print("Ejecuta: pip install python-telegram-bot[ext]")
    PTB_AVAILABLE = False
    sys.exit("Fallo crítico: Falta python-telegram-bot.")


# Configuración básica de logging (puedes mover a core.logging_setup si prefieres)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(settings, 'LOG_LEVEL', 'INFO').upper() # Usar log level de config si está cargada
)
# Silenciar logs muy verbosos de httpx usado por PTB
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada principal para iniciar el bot."""

    if not CONFIG_LOADED or not PTB_AVAILABLE or not HANDLERS_AVAILABLE:
         logger.critical("No se puede iniciar el bot debido a errores previos de importación.")
         return # Salir de main si faltan componentes clave

    # --- Validación de Configuración Esencial ---
    bot_token = settings.TELEGRAM_BOT_TOKEN.get_secret_value() if settings.TELEGRAM_BOT_TOKEN else None
    api_url = str(settings.KELLYBOT_API_URL) if settings.KELLYBOT_API_URL else None
    api_key = settings.API_ACCESS_KEY.get_secret_value() if settings.API_ACCESS_KEY else None

    if not bot_token:
        logger.critical("¡Error Fatal! TELEGRAM_BOT_TOKEN no está configurado en .env")
        return
    if not api_url:
        logger.critical("¡Error Fatal! KELLYBOT_API_URL no está configurada en .env")
        return
    if not api_key:
        logger.critical("¡Error Fatal! API_ACCESS_KEY (para llamar a Kelly API) no está configurada en .env")
        return

    logger.info("Configuración cargada. Iniciando el bot...")

    # --- Configuración de Persistencia (Opcional) ---
    # Guarda datos (como user_data, chat_data) en un archivo para que persistan entre reinicios.
    persistence: Optional[PicklePersistence] = None
    persistence_path_str = getattr(settings, 'PERSISTENCE_FILE_PATH', None)
    if persistence_path_str:
        try:
            persistence_file = Path(persistence_path_str)
            persistence_file.parent.mkdir(parents=True, exist_ok=True) # Crear directorio si no existe
            persistence = PicklePersistence(filepath=persistence_file)
            logger.info(f"Persistencia configurada en: {persistence_file}")
        except Exception as e:
            logger.error(f"No se pudo configurar PicklePersistence en '{persistence_path_str}': {e}. Funcionando sin persistencia.")
            persistence = None # Asegurar que es None si falla
    else:
        logger.warning("Persistencia no configurada (PERSISTENCE_FILE_PATH). Los datos de usuario/chat se perderán al reiniciar.")


    # --- Creación de la Aplicación PTB ---
    try:
        # Usar PersistenceInput para el tipado correcto
        persistence_input = PersistenceInput(bot_data=True, chat_data=True, user_data=True)
        application_builder = ApplicationBuilder().token(bot_token)
        if persistence:
             application_builder = application_builder.persistence(persistence).concurrent_updates(True) # Activar concurrencia es buena idea
        else:
             application_builder = application_builder.concurrent_updates(True)

        application = application_builder.build()

    except Exception as e:
        logger.critical(f"Error fatal creando la aplicación de Telegram: {e}", exc_info=True)
        return

    # --- Registro de Handlers ---
    # Aquí es donde le dices al bot qué hacer cuando recibe ciertos mensajes o comandos.
    logger.info("Registrando handlers...")

    # 1. Handlers de Comandos
    # Llama a la función 'start_command' en commands.py cuando alguien envía /start
    application.add_handler(CommandHandler("start", commands.start_command))
    # Añadir más command handlers aquí (ej. /help)
    # application.add_handler(CommandHandler("help", commands.help_command))

    # 2. Handler de Mensajes de Texto
    # Llama a 'handle_text_message' en messages.py para cualquier mensaje de texto
    # que NO sea un comando (para evitar que responda a /start como si fuera texto normal)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle_text_message))

    # 3. (Opcional) Handler de Errores
    # application.add_error_handler(errors.error_handler)

    # Añadir aquí otros handlers si son necesarios (CallbackQuery, InlineQuery, etc.)

    logger.info("Handlers registrados.")

    # --- Iniciar el Bot ---
    logger.info("Iniciando polling...")
    # run_polling inicia el bot para que reciba updates de Telegram continuamente.
    # allowed_updates puede usarse para optimizar y solo recibir los tipos de update que manejas.
    application.run_polling(allowed_updates=Update.ALL_TYPES)

    # El script se quedará corriendo aquí hasta que lo detengas (Ctrl+C)


if __name__ == "__main__":
    logger.info("Ejecutando bot/main.py")
    main()