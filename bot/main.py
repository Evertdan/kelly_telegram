# bot/main.py
# -*- coding: utf-8 -*-

"""
Punto de entrada principal para el Bot de Telegram KellyBot.
CORREGIDO: Añadida importación de 'Update'.
"""

import logging
import sys
from pathlib import Path
from typing import Optional # Para el tipo de persistencia

# Añadir el directorio raíz del bot al path (si es necesario)
# ...

# Importar configuración
try:
    from bot.core.config import settings
    CONFIG_LOADED = True
except ImportError:
    print("[ERROR CRÍTICO main.py bot] No se pudo importar 'settings'.")
    CONFIG_LOADED = False; sys.exit(1)
except Exception as config_err:
    print(f"[ERROR CRÍTICO main.py bot] Error validando settings: {config_err}")
    CONFIG_LOADED = False; sys.exit(1)

# Importar manejadores (handlers)
try:
    from bot.handlers import commands, messages
    HANDLERS_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR main.py bot] No se pudieron importar handlers: {e}")
    HANDLERS_AVAILABLE = False; sys.exit(1)

# Importar tipos y clases de PTB (python-telegram-bot)
try:
    # --- CORRECCIÓN AQUÍ: Añadir 'Update' ---
    from telegram import Update # <--- AÑADIDO
    # --- FIN CORRECCIÓN ---
    from telegram.ext import (
        Application,
        ApplicationBuilder,
        CommandHandler,
        MessageHandler,
        PicklePersistence,
        filters,
        PersistenceInput,
        CallbackQueryHandler
    )
    from telegram.constants import ParseMode
    PTB_AVAILABLE = True
except ImportError:
    print("[ERROR CRÍTICO main.py bot] 'python-telegram-bot' no instalado.")
    PTB_AVAILABLE = False; sys.exit(1)


# Configuración básica de logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(settings, 'LOG_LEVEL', 'INFO').upper()
)
logging.getLogger("httpx").setLevel(logging.WARNING) # Silenciar httpx
logger = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada principal para iniciar el bot."""

    if not CONFIG_LOADED or not PTB_AVAILABLE or not HANDLERS_AVAILABLE:
         logger.critical("No se puede iniciar bot por errores previos de importación/config.")
         return

    # Validar configuración esencial (sin cambios)
    bot_token = settings.TELEGRAM_BOT_TOKEN.get_secret_value() if settings.TELEGRAM_BOT_TOKEN else None
    api_url = str(settings.KELLYBOT_API_URL) if settings.KELLYBOT_API_URL else None
    api_key = settings.API_ACCESS_KEY.get_secret_value() if settings.API_ACCESS_KEY else None
    if not bot_token: logger.critical("¡Error Fatal! TELEGRAM_BOT_TOKEN no configurado."); return
    if not api_url: logger.critical("¡Error Fatal! KELLYBOT_API_URL no configurada."); return
    if not api_key: logger.critical("¡Error Fatal! API_ACCESS_KEY no configurada."); return

    logger.info("Configuración cargada. Iniciando el bot...")

    # Configuración de Persistencia (sin cambios)
    persistence: Optional[PicklePersistence] = None
    persistence_path_str = getattr(settings, 'PERSISTENCE_FILE_PATH', None)
    if persistence_path_str:
        try:
            persistence_file = Path(persistence_path_str)
            persistence_file.parent.mkdir(parents=True, exist_ok=True)
            persistence = PicklePersistence(filepath=persistence_file)
            logger.info(f"Persistencia configurada en: {persistence_file}")
        except Exception as e:
            logger.error(f"No se pudo configurar PicklePersistence: {e}. Sin persistencia.")
            persistence = None
    else:
        logger.warning("Persistencia no configurada.")


    # Creación de la Aplicación PTB (sin cambios)
    try:
        persistence_input = PersistenceInput(bot_data=True, chat_data=True, user_data=True)
        application_builder = ApplicationBuilder().token(bot_token)
        if persistence:
             application_builder = application_builder.persistence(persistence).concurrent_updates(True)
        else:
             application_builder = application_builder.concurrent_updates(True)
        application = application_builder.build()
    except Exception as e:
        logger.critical(f"Error fatal creando la aplicación de Telegram: {e}", exc_info=True)
        return

    # Registro de Handlers (sin cambios)
    logger.info("Registrando handlers...")
    application.add_handler(CommandHandler("start", commands.start_command))
    application.add_handler(CommandHandler("help", commands.help_command))
    application.add_handler(CommandHandler("debug", commands.debug_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messages.handle_text_message))
    # application.add_error_handler(errors.error_handler) # Opcional
    logger.info("Handlers registrados.")

    # --- Iniciar el Bot (CORREGIDO: 'Update' ahora está definido) ---
    logger.info("Iniciando polling...")
    try:
        # Ahora 'Update' debería estar definido correctamente
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except NameError:
         logger.critical("Error iniciando polling: 'Update' aún no está definido (¡Revisar import!).")
    except Exception as e:
         logger.critical(f"Error fatal durante run_polling: {e}", exc_info=True)


if __name__ == "__main__":
    logger.info("Ejecutando bot/main.py")
    main()